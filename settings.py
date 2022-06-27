# Discord bot token. Can be retrieved at https://discord.com/developers/applications/
# by creating a new bot for an application.
# Credential token. Can be retrieved at https://console.cloud.google.com/apis
# by crating a new API and getting OAth.
import os
BOT_TOKEN = os.environ['BOT_TOKEN']

# Log channel name
LOG_CHANNEL = 'лог-посещений'

# Channel to listen to for command
COMMAND_CHANNEL = 'посещаемость'

# Role to which bot is allowed to respond to
# TODO: Make it a list
ALLOWED_ROLE = 'your_role'

# Bot name that makes a log
LOGGING_BOT = 'Dyno'

# name of command for call help
NAME_HELP_COMMAND='help-attendance'

# name of file, where help information is
NAME_HELP_FILE='help.txt'

# Min time in minutes for setting attendance
MIN_TIME_ATTENDANCE=60

# path to crefential file
GOOGLE_CREDENTIALS_FILE = 'credentials.json'

# path to token.pickle
GOOGLE_TOKEN_PICKLE='token.pickle'

# name of part, where attendance in google sheet - on 0 zero row!
NAME_OF_ATTENDANCE = 'Посещаемость лекций'

# row, where start name attendance (from 1)
ROW_START_NAME_ATTENDANCE=1

# row, where start date (from 1)
ROW_START_Date_ATTENDANCE=2

# col where start FIOs (from 1)
COL_START_FIOS=2

# row where start FIOs (from 1)
ROW_START_FIOS=3