from __future__ import annotations

import datetime
import re
import io
from datetime import datetime, timedelta

import discord
from discord import File

from settings import BOT_TOKEN, ALLOWED_ROLE, COMMAND_CHANNEL, LOG_CHANNEL, LOGGING_BOT


class LogClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message: discord.Message):
        # TODO: Handle exceptions everywhere

        # Check if user has required role to speak to the bot
        if (message.channel.name != COMMAND_CHANNEL
                or ALLOWED_ROLE not in map(lambda x: x.name, message.author.roles)):
            return

        print(f'Message from {message.author}: {message.content}')

        # Parse message
        query = LogQuery.from_message(message.content)

        guild = message.channel.guild

        # Get channel with logs
        log_channel = None
        for channel in guild.channels:
            if channel.name == LOG_CHANNEL:
                log_channel = channel
                break

        # Get messages and parse them
        messages = await \
            get_log(log_channel, query)
        report = parse_log(messages, query, guild)

        # Render a report
        # TODO: Do we need to optimize user names queries here?
        rendered_report = ''
        for entry in report:
            member_name = message.channel.guild.get_member(entry.user_id).nick
            rendered_report += entry.render(member_name)

        # Send the report as file
        await message.channel.send(
            file=File(io.StringIO(rendered_report), filename=f'{datetime.now().isoformat()}-{query.channel_name}.tsv'))


async def get_log(log_channel: discord.TextChannel, query: LogQuery) -> [discord.Message]:
    messages = await log_channel.history(
        after=convert_to_utc(query.date_start),
        before=convert_to_utc(query.date_end),
        oldest_first=True
    ).flatten()

    return [x for x in messages if x.author.name == LOGGING_BOT]


def convert_to_utc(dt: datetime) -> datetime:
    offset = dt.utcoffset()
    return dt.replace(tzinfo=None) - offset


def parse_log(messages: [discord.Message], query: LogQuery, guild: discord.Guild) -> [ReportEntry]:
    report: [ReportEntry] = []

    for desc, time in list(map(lambda x: (x.embeds[0].description, x.created_at), messages)):
        groups = re.match(r"\*\*<@!(.+?)>\s(.+?)\s(.+?)<#(.+?)>", desc).groups()
        user_id = int(groups[0])
        joined = True if groups[1] == 'joined' else False
        channel_id = int(groups[3])

        if guild.get_channel(channel_id).name != query.channel_name:
            continue

        if joined:
            entry = ReportEntry(user_id)
            entry.date_start = time
            report.append(entry)
        else:
            joined_moment = len(report) - 1 - next(
                (i for i, x in enumerate(reversed(report)) if x.user_id == user_id), None)
            if joined_moment is not None:
                report[joined_moment].date_end = time
            else:
                entry = ReportEntry(user_id)
                entry.date_end = time
                report.append(entry)

    return report


class LogQuery:
    channel_name: str
    date_start: datetime
    date_end: datetime

    def __init__(self, channel_name: str, date_start: datetime, date_end: datetime):
        self.channel_name = channel_name
        self.date_start = date_start
        self.date_end = date_end

    @classmethod
    def from_message(cls, message: str) -> LogQuery:
        lines = message.splitlines()
        channel_name = lines[0].strip()
        date_start = datetime.fromisoformat(lines[1].strip())
        date_end = datetime.fromisoformat(lines[2].strip())
        return cls(channel_name, date_start, date_end)


class ReportEntry:
    date_start: datetime | None
    date_end: datetime | None
    user_id: int
    user_name: str

    def __init__(self, user_id):
        self.user_id = user_id
        self.date_start = None
        self.date_end = None

    @property
    def elapsed_time(self) -> timedelta | None:
        if self.date_start is not None and self.date_end is not None:
            return self.date_end - self.date_start
        else:
            return None

    def render(self, username: str) -> str:
        elapsed_time_s = ''
        if self.elapsed_time is not None:
            elapsed_time_s = ReportEntry.strfdelta(self.elapsed_time, '{hours}:{minutes}:{seconds}')

        date_start_s = ''
        if self.date_start is not None:
            date_start_s = self.date_start.isoformat()

        date_end_s = ''
        if self.date_end is not None:
            date_end_s = self.date_end.isoformat()

        return f'{username}\t{date_start_s}\t{date_end_s}\t{elapsed_time_s}\n'

    @staticmethod
    def strfdelta(tdelta, fmt):
        d = {'days': tdelta.days}
        d['hours'], rem = divmod(tdelta.seconds, 3600)
        d['minutes'], d['seconds'] = divmod(rem, 60)
        return fmt.format(**d)


if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.members = True
    client = LogClient(intents=intents)
    client.run(BOT_TOKEN)
