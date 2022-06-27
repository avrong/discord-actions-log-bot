from __future__ import annotations

import googleSheet
from googleSheet import GoogleSheetParser

import logging

import re
import io

import datetime
from datetime import datetime, timezone, timedelta

import discord
from discord import File

from settings import BOT_TOKEN, ALLOWED_ROLE, COMMAND_CHANNEL, LOG_CHANNEL, LOGGING_BOT, MIN_TIME_ATTENDANCE, NAME_HELP_COMMAND, NAME_HELP_FILE

# logger configuration (for debug messages in console)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s :: %(levelname)s :: %(message)s')
logger = logging.getLogger(__name__)

# variable for min time attendance
Min_Time_Delta=None

class LogClient(discord.Client):
    async def on_ready(self):
        """
        React on linking   
        """
        logger.info("Logged on as %s!", self.user)

    async def on_message(self, message: discord.Message):
        """
        React on message, if Format is right, than perform actions of attendance
        
        :param message: object of discord.Message, which contain information about current user message
     
        :result: file with attendance range in required format
                  OR sending to Google Sheet result information and file with errors and warnings of sending to Google Sheet        
        """
        
        # set global for using existing variable
        global Min_Time_Delta
        
        # Check if user has required role to speak to the bot
        if (message.channel.name != COMMAND_CHANNEL
                or ALLOWED_ROLE not in map(lambda x: x.name, message.author.roles)):
            return
        
        # message to logger
        logger.info("Message from %s: %s", message.author, message.content)
        
        # if this is help request
        if (isHelp(message.content)):
            await sendHelp(message)
            return 

        # start of compulations
        await message.channel.send("Please, wait for results...")  
        
        # Parse message
        query = ''
        try:
            query = LogQuery.from_message(message.content)
        except Exception as ex:
            await message.channel.send(ex)   
            return
        guild = message.channel.guild
        # Get channel with logs
        log_channel = None
        for channel in guild.channels:
            if channel.name == LOG_CHANNEL:
                log_channel = channel
                break
        
        # check mistakes before parse messages (get massages history - is long process)                    
        if query.output_type == 'tsv':
            sep = '\t'
        elif query.output_type == 'csv':
            sep = ','
        elif query.output_type == 'excel':
            sep = ';'
            query.output_type = 'csv'
        elif query.output_type == 'txt':
            sep = '\t'
            query.output_type = 'txt'
        elif query.output_type == 'google':
            if (query.id_google_sheet==None or query.id_google_sheet.strip() == ''):
                await message.channel.send("Wrong Parameters. For google sheet you need set google sheet ID.")
                await message.channel.send('You can find it in your table url')
                return                
            if f'{query.date_end:%y.%m.%d}'!= f'{query.date_start:%y.%m.%d}':
                await message.channel.send("Not equal start and end dates - can' set atendance to google sheet")
                return 
            if (query.min_attendance_minutes!=None):
                if (query.min_attendance_minutes.isnumeric() and int(str(query.min_attendance_minutes))>0):
                    Min_Time_Delta=timedelta(minutes=int(query.min_attendance_minutes))
                else:
                    await message.channel.send('Min attendance minutes must be an integer value (not a string), larger than 0!') 
                    return
            else:
                Min_Time_Delta=timedelta(minutes=MIN_TIME_ATTENDANCE)
        else:
            logger.error("Unknown output format %s", query.output_type)
            await message.channel.send(f"Unknown output format {query.output_type}")
            return
        
        # Get messages and parse them
        messages = await \
            get_log(log_channel, query)
        logger.info("Retrieved %d messages", len(messages))
        report = parse_log(messages, query, guild)
        
        # standart mode   
        if query.output_type != 'google':
            # TODO: Do we need to optimize user names queries here?
            # render report
            rendered_report = f"\ufeffname{sep}joined_at{sep}left_at{sep}time_spent\n"
            for entry in report:
                member = message.channel.guild.get_member(entry.user_id)
                if member:
                    member_name = member.display_name
                else:
                    member_name = f"Unknown <{entry.user_id}>"
                    logger.error("Unknown user with id %d", entry.user_id)
                rendered_report += entry.render(member_name, sep=sep)
            # Send the report as file
            filename = f"{query.date_start:%Y-%m-%d_%H-%M-%S}--{query.date_end:%Y-%m-%d_%H-%M-%S}--{query.channel_name}.{query.output_type}" #noqa
            await message.channel.send(
                file=File(io.StringIO(rendered_report), filename=filename))
        # google mode
        else:     
            totalErrorsDiscord=[] #  for errors from discord
            totalErrors=[] #  for errors from parser and googleSheet
            totalWarnings=[] # for warning from parser and googleSheet
            totalInfo=[] #  for user, which don't spend enough time
            totalResult='None result'
            renderDict={}
            # convert information to format: name-duration
            for entry in report:            
                member = message.channel.guild.get_member(entry.user_id)   
                if member:
                    member_name = member.display_name
                else:
                    logger.error("Unknown user with id %d", entry.user_id)    
                    totalErrorsDiscord.append("Error: unknown user with id " + str(entry.user_id) + " in discord")
                    # For unknown id - is not neccessary to show errors in result doument
                    continue
                entry.setUniqueFromRenderInDict(member_name, query, renderDict)
            # clear, when not in Time Attendance
            totalInfo, renderDict = compareToArrayRenderDictByMinTimeDelta(renderDict)
            # if don't have any info
            if (len(renderDict)<=0):
                await message.channel.send("Nothing was found according to your request...")
                await message.channel.send("Try to varify name of your channel  or range of dates!")  
                # If errors exists - send errors
                result=('\n'.join(totalErrorsDiscord)+'\n' if len(totalErrorsDiscord)>0 else '') + \
                        ('\n'.join(totalInfo) if len(totalInfo)>0 else '')
                if (result!=''):
                    # name of File
                    filename = f"errors--{query.date_start:%Y-%m-%d_%H-%M-%S}--{query.date_end:%Y-%m-%d_%H-%M-%S}.txt" 
                    await message.channel.send(file=File(io.StringIO(result), filename=filename)) 
                return
            # try to set information to google sheet
            try:
                googleSheetParser = GoogleSheetParser()
                # get results
                totalResult, totalWarnings, totalErrors = googleSheetParser.setAttendanceFromNicksToGoogleSheet(f'{query.date_end:%d.%m}', renderDict, query.id_google_sheet)
            except Exception as ex:
                await message.channel.send(ex)
                return
            # if somethin wrong with result, but not exception
            if (totalResult==False):
                await message.channel.send("Can't update google sheet")
            else:
                try:
                    # embed print of result, if we have permission
                    result_emb=None
                    result_emb = discord.Embed( title = 'RESULT', colour = discord.Color.green())
                    for result in totalResult:
                        result_emb.add_field(name = str(result), value=str(totalResult[result]), inline=False)
                    result_emb.add_field(name = "Total Discord Errors", value=str(len(totalErrorsDiscord)), inline=False)
                    result_emb.add_field(name = "Total not enough time for attendance ", value=str(len(totalInfo)), inline=False)
                    await message.channel.send( embed = result_emb)
                except Exception as ex:
                    # default print of result, if we don't have permission
                    result_simple=''
                    for result in totalResult:
                        result_simple=result_simple+str(result)+' '+ str(totalResult[result])+'\n'            
                    result_simple=result_simple+"Total Discord Errors"+' '+str(len(totalErrorsDiscord))+'\n'
                    result_simple=result_simple+"Total not enough time for attendance "+' '+str(len(totalInfo))
                    await message.channel.send(result_simple+'\n')
                    await message.channel.send("Bot don't have permission for send data in embed. Full text exception: " + str(ex))
                    await message.channel.send("To use embed you need to give bot permissions: SEND MESSAGES, EMBED LINKS, ATTACH FILES")

            # Result for add
            result=('\n'.join(totalErrors)+'\n' if len(totalErrors)>0 else '') + \
                    ('\n'.join(totalWarnings)+'\n' if len(totalWarnings)>0 else '') + \
                    ('\n'.join(totalErrorsDiscord)+'\n' if len(totalErrorsDiscord)>0 else '') + \
                    ('\n'.join(totalInfo) if len(totalInfo)>0 else '')
            if (result!=''):
                # name of File
                filename = f"errors--{query.date_start:%Y-%m-%d_%H-%M-%S}--{query.date_end:%Y-%m-%d_%H-%M-%S}.txt" 
                # send result file
                await message.channel.send(file=File(io.StringIO(result), filename=filename))     

async def get_log(log_channel: discord.TextChannel, query: LogQuery) -> [discord.Message]:
    """
    React on message, if Format is right, than perform actions of atendance
    
    :param log_channel: object of log for channel
    :param query: object of LogQuery, which contain information about user message
    
    :returns: all messages in this channel  between dates in query
    """
    messages = await log_channel.history(
        limit=None,
        after=convert_to_utc(query.date_start),
        before=convert_to_utc(query.date_end),
        oldest_first=True
    ).flatten()

    return [x for x in messages if x.author.name == LOGGING_BOT]

def isHelp(message: discord.Message):
    """
    Help to understand - is it help message or not
    
    :param message: object of discord.Message, which contain information about current user message
    
    :returns: True, if we get help-message and False, if not    
    """
    items = message.replace(',', ';').replace('\n', ';').split(';')
    if (len(items)==1 and items[0].strip().lower() == NAME_HELP_COMMAND.lower()):
        return True
    else:
        return False

async def sendHelp(message: discord.Message):
    """
    Send help information
    
    :param message: object of discord.Message, which contain information about current user message, but need for channel to send message
    
    :returns: Embed message, if we have permission, else error and standart message.
    """
    try:
        arr=[]
        with open(NAME_HELP_FILE, encoding='utf-8') as file:  
            arr = [row.strip() for row in file]      
        print (arr)  
    except Exception  as ex:
        await message.channel.send("Can't open help file.\n Full text of error: " + str(ex))        
    try:   
        # embed print
        index=0 
        # send basic words
        while (index<len(arr) and not arr[index].upper()==arr[index]):
            await message.channel.send(arr[index])
            index+=1
        # send embed message
        while(index < len(arr)):
            # embed title and description
            if (len(arr) - index >=2):
                result_emb=discord.Embed( title = arr[index], description= arr[index+1], colour = discord.Color.blue())
                index +=2
            else:
                break
            # embed fields               
            while(len(arr)-index >=2 and not arr[index].upper() == arr[index] ):
                result_emb.add_field( name = arr[index] ,value=arr[index+1], inline=False)
                index+=2
                
            await message.channel.send( embed = result_emb)
    except Exception  as ex:
        # default print
        await message.channel.send('\n'.join(arr))
        await message.channel.send("You don't have permission for send data or file with help information has bad structure.\n Full text of error: " + str(ex))
        await message.channel.send("To use embed you need to give bot permissions: SEND MESSAGES, EMBED LINKS, ATTACH FILES")


        
def convert_to_utc(dt: datetime) -> datetime:
    """
    Convert time in object datetime to utc format
    
    :param message: object of discord.Message, which contain information about current user message, but need for channel to send message
    
    :returns: Embed message, if we have permission, else error and standart message.
    """
    offset = dt.utcoffset()
    return dt.replace(tzinfo=None) - offset


def parse_log(messages: [discord.Message], query: LogQuery, guild: discord.Guild) -> [ReportEntry]:
    """
    React on message, if Format is right, than perform actions of atendance
    
    :param messages: Array of messages between start and end date
    :param query: object of parse user message info
    :param guild: information about channels

    :returns: array of Objects reportEntry   
    """
    report: [ReportEntry] = []

    for desc, time in list(map(lambda x: (x.embeds[0].description, x.created_at), messages)):
        logger.debug("Parsing message %s sent at %s", desc, time)
        match = re.match(r"\*\*<@!?(.+?)>\s(.+?)\s(.+?)[`<]#(.+?)[`>](?:\s->\s[`<]#(.+?)[`>])?", desc)
        if not match:
            logger.error("Unable to parse message \"%s\" sent at %s", desc, time)
            continue
        groups = match.groups()
        user_id = int(groups[0])
        # check if this log event correspons to the voice channel in question
        channel_list = []
        if groups[3].isnumeric():
            channel_list += [guild.get_channel(int(groups[3])).name]
        else:
            channel_list += [groups[3]]
        if len(groups) > 4 and groups[4] is not None:
            if groups[4].isnumeric():
                channel_list += [guild.get_channel(int(groups[4])).name]
            else:
                channel_list += [groups[4]]
        if query.channel_name not in channel_list:
            continue
        # is user joining or leaving voice channel?
        if groups[1] == 'left' or (groups[1] == 'switched' and channel_list[0] == query.channel_name):
            joined = False
        else:
            joined = True

        if time:
            time = time.replace(tzinfo=timezone.utc)

        if joined:
            entry = ReportEntry(user_id)
            entry.date_start = time
            report.append(entry)
        else:
            entry = next((x for x in reversed(report) if x.user_id == user_id), None)
            if entry is None:
                entry = ReportEntry(user_id)
                report.append(entry)
            entry.date_end = time

    return report


    

# class for parse message from user
class LogQuery:
    channel_name: str
    date_start: datetime | None
    date_end: datetime | None
    output_type: str | None
    id_google_sheet: str | None
    min_attendance_minutes: str | None

    def __init__(self, channel_name: str, date_start: datetime, date_end: datetime, output_type: str, id_google_sheet: str | None, min_attendance_minutes: str | None):
        """
        Initialise params from variables
        
        :param channel_name: name of channel from user message
        :param date_start: date start parsing log in datetime from user message
        :param date_end: date end parsing log in datetime from user message
        :param output_type: format of result file
        :param id_google_sheet: id of google sheet
        :param min_attendance_minutes: optional value of minimem size for attandance student
        
        :returns: init variables in object LogQuery  
        """
        
        self.channel_name = channel_name
        self.date_start = date_start
        self.date_end = date_end
        self.output_type = output_type
        self.id_google_sheet = id_google_sheet
        self.min_attendance_minutes =  min_attendance_minutes

    @classmethod
    def from_message(cls, message: str) -> LogQuery:
        """
        Initialise params from user message parse
        
        :param cls: self value to initialise
        :param message: content of message - string value of message
        
        :returns: init object LogQuery  
        """
        # split to array
        items = message.replace(',', ';').replace('\n', ';').split(';')
        channel_name=''
        date_start=''
        date_end=''
        output_type=''
        # try to parse
        try:
            channel_name = items[0].strip()
            date_start = datetime.fromisoformat(items[1].strip()).astimezone()
            date_end = datetime.fromisoformat(items[2].strip()).astimezone()
            output_type = items[3].strip().lower() if len(items) > 3 else 'txt'
            id_google_sheet = items[4].strip() if len(items) > 4 else None  
            min_attendance_minutes = items[5].strip() if len(items) > 5 else None  
        except Exception as ex:
            raise Exception("Wrong format of message try to use this format: {name channel}, yyyy-mm-dd hh:mm, yyyy-mm-dd hh:mm, {file format}}.")
        return cls(channel_name, date_start, date_end, output_type, id_google_sheet, min_attendance_minutes)

# class for saving info about every log message in format: uesr, date_start - date_end
class ReportEntry:
    date_start: datetime | None
    date_end: datetime | None
    user_id: int
    user_name: str

    def __init__(self, user_id):
        """
        Initialise params from variables
        
        :param date_start: date and time user connect to the channel
        :param date_end: date and time user disconnect from the channel
        :param user_id: id user (which connect and/or disconnect to/from server)
        :param user_name: name of user (which connect and/or disconnect to/from server)
        
        :returns: init variables in object ReportEntry 
        """
        
        self.user_id = user_id
        self.date_start = None
        self.date_end = None

    def elapsed_time_withBorders(self, dateStartMessage, dateEndMessage) -> timedelta: 
        """
        Get time span between connection and disconnection for current object with using date and time start and end parsing
        
        :param dateStartMessage: date and time start parsing
        :param dateEndMessage: date and time end parsing
        
        :returns: time span between date_end and date_start with using date and time start and end parsing 
        """    
        if self.date_start is not None and self.date_end is not None:
            return self.date_end - self.date_start
        elif self.date_start is not None and self.date_end is None:
            return dateEndMessage - self.date_start
        elif self.date_start is None and self.date_end is not None:
            return self.date_end - dateStartMessage       
        else:
            return timedelta(0)
    
    @property            
    def elapsed_time(self) -> timedelta | None:
        """
        Get time span between connection and disconnection for current object
   
        :returns: time span between date_end and date_start or None, if one of them doesn't exists
        """ 
        if self.date_start is not None and self.date_end is not None:
            return self.date_end - self.date_start
        else:
            return None


    def render(self, username: str, sep: str = '\t') -> str:
        """
        With separate sign get from username, end, start and elapced time - row for writing to file 
        
        :param username: usename, which corresponds user id
        :param sep: separator for output_format file
        
        :returns: row of information for object in output_format file (by separator)
        """ 
        
        # interval between start and end
        elapsed_time_s = ''
        if self.elapsed_time is not None:
            elapsed_time_s = ReportEntry.strfdelta(self.elapsed_time, '{hours:02}:{minutes:02}:{seconds:02}')

        # start date in string iso-format
        date_start_s = ''
        if self.date_start is not None:
            date_start_s = self.date_start.astimezone().isoformat(sep=' ', timespec='seconds')

        # end date in string iso-format
        date_end_s = ''
        if self.date_end is not None:
            date_end_s = self.date_end.astimezone().isoformat(sep=' ', timespec='seconds')

        # return row information with file-separator
        return f'{sep}'.join([username, date_start_s, date_end_s, elapsed_time_s]) + '\n'


    # for result query google sheet - set unique:
    # renderDict is changing
    def setUniqueFromRenderInDict(self, username: str, query: LogQuery, renderDict: dict):
        """
        Try to find username - if exist - add interval time, else create new element of dicionary with this interval 
        
        :param username: usename, which corresponds user id
        :param query: object of parse user message info
        :param renderDict: dictionary with information about users with time intervals
        
        :returns: edit dictionary with new time-info about user
        """ 
        if username in renderDict:
            renderDict[username]+=self.elapsed_time_withBorders(query.date_start, query.date_end)
        else:
            renderDict[username]=self.elapsed_time_withBorders(query.date_start, query.date_end)

    @staticmethod
    def strfdelta(tdelta, fmt):
        """
        Convert delta-time to string value
        
        :param tdelta: object of timedelta - value of interval
        :param fmt: format of output in string
        
        :returns: string value from timedelta value
        """ 
        d = {'days': tdelta.days}
        d['hours'], rem = divmod(tdelta.seconds, 3600)
        d['minutes'], d['seconds'] = divmod(rem, 60)
        return fmt.format(**d)

# clear all names in dict, which don't have need Time and compare to array of names
def compareToArrayRenderDictByMinTimeDelta(renderDict:dict):
    """
    Clear all names in dict, which don't have need Time and compare to array of names
    
    :param renderDict: dictionary with information about users with time intervals
    
    :returns:   totalInfo - array of warning for all users, which time less then min_time_attendance
                renderArray - dictionary, which contain only information about nicks, which pass min_time_attendance check
    """ 
    renderArray=[]
    totalInfo=[]
    for username in renderDict:
        if renderDict[username]>=Min_Time_Delta:
            renderArray.append(username)
        else:
            totalInfo.append("Person with nick '" +str(username) + "' was not enough time in lectures: " + \
                ReportEntry.strfdelta(renderDict[username], '{hours:02}:{minutes:02}:{seconds:02}'))
    return totalInfo, renderArray
           
       

# main condition
if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.members = True
    client = LogClient(intents=intents)
    client.run(BOT_TOKEN)
