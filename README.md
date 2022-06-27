# Discord Access Log Export Bot

Export voice channel access logs from Dyno in a TSV format with a simple command.

Settings are located in `settings.py`.

Bot responds to a message containing three params: name of an audio channel to search info about, start and end dates
of log to search in (iso format specified in UTC currently).

Current implementation is pretty rough and mostly MVP. To be improved in the future

## Setting up bot

Required: Python 3.10 and dependencies listed in `requirements.txt`.

1. Register your new application at https://discord.com/developers/applications
2. Create a bot for your application
3. Turn on `SERVER MEMBERS INTENT` in your bot. This will allow it to see members of discord channel, which is needed
   to determine people's server nicknames by id
4. Go to `OAuth2 > URL Generator` and generate a link for your bot to add it to channel
   * Check `bot` in `SCOPES`
   * Check in `BOT PERMISSIONS`: `Send Messages`, `Attach Files`, `Read Message History`, and `Read Messages/View Channels`.
   I'm not sure whether we need all of them, it worked for me even without all of them, but I did not test it precisely.
5. Adjust settings to yours. You will need to provide bot token from Discord developer portal (`Bot > Token`), log channel,
   command channel (to communicate with bot) and authorized group to which it will respond to only.
6. Run the bot and set up necessary channels, roles
7. Send a message in the `COMMAND_CHANNEL` containing channel name to take logs from, and two iso datetimes of start and end.
8. Structure: <i>name-of-channel, date-time-start, date-time-end, file-format</i>
   * name-of-channel - the name of the channel for which you want to receive attendance
   * date-time-start- date and time start of lecture in format: yyyy-mm-dd hh:mm
   * date-time-end - date and time start of lecture in format: yyyy-mm-dd hh:mm
   * file-format - format of result file, which contains information about attendance of your query. Formats: tsv, txt, csv, excel
9. Result - file in selected format with attendance (with start and finish time for every student and interval between this times)
10. Examples:
   ```
   General, 2022-02-18 09:30, 2022-02-18 11:00, csv
   OOP, 2022-02-18 11:10, 2022-02-18 12:40, excel
   Operating systems, 2022-02-18 11:10, 2022-02-18 12:40, txt
   Computer graphics, 2022-02-18 11:10, 2022-02-18 12:40, tsv
   ```
   
   Timezone is optional (<i>Example: </i><b>2022-02-18T02:00:00+03:00</b>). Timezone of output is currently always UTC.

## Setting up google sheet modification

Required: Python 3.10 and dependencies listed in `requirements.txt`.
Required: setting up bot stage <i>(see upper)</i>.

1. In settings you should set variable MIN_TIME_ATTENDANCE - integer in minutes. This variable can help to understand - was the person at the lecture enough time - if not, then we left him, but he will be set in result file in format txt
2. You should create new sheet in Google sheet, if you don't have now. And save id of this sheet in GOOGLE_SPREADHEET_ID in googleSheetSettings.py. 
<i>Condition of the structure:</i>
   + all FIO should be in one column
   + all dates should be in one row
   + all attendance should be in one column for every date
   + Dates must start in col with the cell with text in variable NAME_OF_ATTENDANCE 
   + Format of attendance '1' if attend else everything besides '1'
2. Determine settings in settings.py:
   + Format of dates should be determine in variable GOOGLE_FORMAT_DATE
   + Set default minimum time in minutes, which student needs attend the lecture in order to set attendance, in variable MIN_TIME_ATTENDANCE (if not enough, then we left him, but he will be set in result file in format txt)
   + FIO column start with variables:
      * COL_START_FIO - determine column where starts FIOs (count from 1)
      * ROW_START_FIOS - determine row where start FIOs (count from 1)
   + ROW_START_NAME_ATTENDANCE - row, where we can find start of the dates - signal for column is key word variable NAME_OF_ATTENDANCE
   + ROW_START_DATE_ATTENDANCE - variable, which determine row position of dates (in what row we should search the dates?)
4. After that you need to create google API and get credentials. You can make it at https://console.cloud.google.com/apis. You need to get credentials json, after you registration api. After that you need to set names on variables in set in settings.py:
   + GOOGLE_CREDENTIALS_FILE - path to your credential file for google API.
   + GOOGLE_TOKEN_PICKLE - variable of refresh key. After first connection you can forget about refresh token on API every weak - you just need to delete this file, when token get old - program will automaticly refresh token and create pickle file(set in googleSheet)
5. For call this mode in format file you need to set mode <i><b>google</b></i> in place of text format
6. Structure: name-of-channel, date-time-start, date-time-end, <i><b>google</b></i>, min-attendance-minutes
   * name-of-channel,  date-time-start, date-time-end - same as standart mode
   * <i><b>google</b></i> - special key word for google mode
   * min-attendance-minutes - minimum time in minutes for understand - was student on lecture or not (Students who do not pass this threshold will be displayed in the error file). This is optional parameter (in standart 60 minutes). You can change it in settings.py in variable MIN_TIME_ATTENDANCE, but don't forget change it in help.txt!
7. Result - count of successful operations, count of errors and warnings; and txt-file with description of warnings and errors
8. Examples:
   ```
   General, 2022-02-18 9:30, 2022-02-18 11:00, google
   OOP, 2022-02-18 11:00, 2022-02-18 12:30, google, 90
   ```

<b>Important:</b> for embed messages you need to give permissions to bot:  `SEND MESSAGES`, `EMBED LINKS`, `ATTACH FILES`.

## Help attendance
1. You can change name command for help menu in variable NAME_HELP_COMMAND
2. In varible NAME_HELP_FILE you should write the path to the file, which contain help information (txt-format)
3. Structure of help informetion:
   * Simple information, not embed - everu row, while this row is not UPPER
   * Then cycle for every embed message (starts with UPPER register)
      + First row (upper row) - embed title
      + Second row - embed description
      + Then cycle for every embed field
         * First row - name field
         * Second row - value field

<i> If you need to add help - please, set it in this structure.</i> 

<b>Important:</b> <i>every field always have two rows - if you want to add field, than set two rows of information.</i>
      
