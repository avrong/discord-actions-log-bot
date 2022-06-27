import re
import math

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from settings import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_PICKLE, NAME_OF_ATTENDANCE
from settings import ROW_START_NAME_ATTENDANCE, ROW_START_Date_ATTENDANCE, COL_START_FIOS, ROW_START_FIOS


class GoogleSheet:
    # If modifying these scopes, delete the file token.pickle.
    # We need write access to the __spreadsheet: https://developers.google.com/sheets/api/guides/authorizing
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    # SETTINGS IN FORMAT ARRAY - FROM 0 (IN SHEET - FROM 1)

    # rows begin in google Sheet with 1, not 0
    _shift_rows=1
    
    # length English Words 26-1
    _len_English_Sub=26
  
    # SET IN INIT
    
    # row, where start name attendance
    _row_start_name_attendance=0
    # row, where start date
    _row_start_date_attendance=0

    # col where start FIOs
    _col_start_FIOs=0

    # row where start FIOs
    _row_start_FIOs=0

    # our Sheets
    __spreadsheet = None
    
    _GOOGLE_SPREADSHEET_ID=''
    

    def __init__(self):
        """
        Performs authentication and creates a __spreadsheet instance. Set values to variables from settings.
        
        """
        # row, where start name attendance
        self._row_start_name_attendance=ROW_START_NAME_ATTENDANCE-self._shift_rows

        # row, where start date
        self._row_start_date_attendance=ROW_START_Date_ATTENDANCE-self._shift_rows

        # col where start FIOs
        self._col_start_FIOs=COL_START_FIOS-self._shift_rows

        # row where start FIOs
        self._row_start_FIOs=ROW_START_FIOS-self._shift_rows
        
        if (self._row_start_name_attendance<0 or self._row_start_date_attendance<0 or self._col_start_FIOs<0 or self._row_start_FIOs<0
            or NAME_OF_ATTENDANCE == '' or GOOGLE_TOKEN_PICKLE=='' or GOOGLE_CREDENTIALS_FILE==''):
            raise Exception('Wrong settings in googleSheetSettings.py')
        
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(GOOGLE_TOKEN_PICKLE):
            with open(GOOGLE_TOKEN_PICKLE, 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_FILE, self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(GOOGLE_TOKEN_PICKLE, 'wb') as token:
                pickle.dump(creds, token)

        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

        # Call the Sheets API
        self.__spreadsheet = service.spreadsheets()

    def _setIdGoogleSheet(self, id_google_sheet):
        self._GOOGLE_SPREADSHEET_ID=id_google_sheet
    
    
    def _get_sheet_names(self):
        """
        Get all sheet names that are present on the spreadsheet
        
        :returns: list with sheet names
        """
        sheets = []
        try:
            result = self.__spreadsheet.get(spreadsheetId=self._GOOGLE_SPREADSHEET_ID).execute()
        except Exception as ex:
            raise Exception("Can't get groups from google sheet. Please check the correctness of the google spreadheet ID.\nYou can find this ID in url of your google Table\nFull text of exception: " + str(ex))
        for s in result['sheets']:
            sheets.append(s.get('properties', {}).get('title'))
        return sheets

    def _getBatchRange(self, nameSheet):
        """
        Convert nameSheet to Range.
        Need to solve the problem, when range convert in form: '4931!M911', which is not correct
        
        :param nameSheet: current name of sheet
        :returns: range from sheet in form 'M911' -> 'M911!A1:AJ1000'
        """
        return f"'{str(nameSheet)}'!A1:AJ1000"

    def _getBatchRanges(self, arrNameSheet):
        """
        Get ranges for list for all arrNameSheet
        
        :param arrNameSheet: array of names of all sheets
        :returns: array of ranges for all sheets to get request
        """
        arrBatchRanges=[]
        for nameSheet in arrNameSheet:
            arrBatchRanges.append(self._getBatchRange(nameSheet))
        return arrBatchRanges

    def _get_multiple_sheets_data(self, sheets, dimension='COLUMNS'):
        """
        Get data from multiple sheets at once with a batchGet request
        
        :param __spreadsheet: a service.__spreadsheets() instance
        :param sheets: a list of sheet names for which the data is to be retrieved
        :param dimension: passed to __spreadsheet.values().batchGet as a value of majorDimension param. Possible values are 'COLUMNS' or 'ROWS'
        :returns: dict with sheet name as key and data as value
        """
        data = {}
        arrBatchRanges = self._getBatchRanges(sheets)
        
        request = self.__spreadsheet.values().batchGet(spreadsheetId=self._GOOGLE_SPREADSHEET_ID, ranges=arrBatchRanges, majorDimension=dimension)
        response = request.execute()
        
        for i in range(0, len(response.get('valueRanges'))):
            data[str(sheets[i])] = response.get('valueRanges')[i].get('values')
        return data
      #for sheet in sheets:
            
      #      request = self.__spreadsheet.values().batchGet(spreadsheetId=self._GOOGLE_SPREADSHEET_ID, ranges=str(sheet)+'!A1:AJ1000', majorDimension=dimension)
      #      response = request.execute()
       #     print(response.get('valueRanges')[0])
       #     data[sheet] = response.get('valueRanges')[0].get('values')
      #  return data

      
    def _find_dates_and_ranges_attendance(self, sheets, multiple_sheets_data):
        """
        Get range array of start and end position lectures for every sheet
        Get array of dates lectures for every sheet
        
        :param sheets: a list of sheet names for which the data is to be retrieved
        :param multiple_sheets_data: a list of data for every sheet in sheets
        :returns:   startattendance - array of horizontal position, where dates start
                    datesattendance - array of arrays of all dates in every sheet
        
        """
        startAttendance=[]
        datesAttendance=[]
        index=0
        for data in multiple_sheets_data:
            index+=1

        for indexSheet in range(len(sheets)):

            datesAttendance.append([])
            sheetData=multiple_sheets_data[sheets[indexSheet]]
            

            # flag of attendance
            isattendance=False
            for indexCol in range(len(sheetData)):
                # if not enough rows
                if (len(sheetData[indexCol])-1<self._row_start_date_attendance):
                    continue
                    
                if (isattendance):
                    if (re.search(r'^[0-3][0-9]\.[0-1][0-9]$', sheetData[indexCol][self._row_start_date_attendance])!=None): 
                        # set exist date
                        datesAttendance[indexSheet].append(sheetData[indexCol][self._row_start_date_attendance])
                    else:
                        break 
                # if wind key-word - is start of attendance
                elif (sheetData[indexCol][self._row_start_name_attendance]==NAME_OF_ATTENDANCE):
                    startAttendance.append(indexCol)
                    isattendance=True
                    # set exist date
                    datesAttendance[indexSheet].append(sheetData[indexCol][self._row_start_date_attendance])    
            if (len(startAttendance)<len(datesAttendance)):
                startAttendance.append(-1)
        return (startAttendance, datesAttendance)
    
    def _find_FIOs(self, sheets, multiple_sheets_data):
        """
        Parse multiple_sheets_data and get array of FIO students for every sheet
        
        :param sheets: a list of sheet names for which the data is to be retrieved
        :param multiple_sheets_data: a list of data for every sheet in sheets
        :returns: array of FIO for every sheet
        """
 
        sheetsFIOs=[]
        for indexSheet in range(len(sheets)):
            sheetData=multiple_sheets_data[sheets[indexSheet]]
            FIOs=sheetData[self._col_start_FIOs]
            
            # delete upper rows
            if (len(FIOs)>self._row_start_FIOs):
                del FIOs[0 : self._row_start_FIOs]
            sheetsFIOs.append(FIOs)
        return sheetsFIOs   
    
    def _get_col_date(self, date, dates, startDate):
        """
        Get col date position in googleSheet
        
        !Attention date format dd.mm
        
        :param date: the date of lecture
        :param dates: all dates, which we have for current sheet
        :param startDate: index col, where start the dates    
        :returns: in dates horizontal position of date
        """
        
        try:
            return dates.index(date)+startDate
        except:
            return -1

    
    def _get_all_col_dates(self, date, dates, startDates, sheets):
        """
        Get col date position in googleSheet for all sheets
        
        :param date: the date of lecture
        :param dates: all dates, which we have for current sheet
        :param startDate: index col, where start the dates    
        :param sheets: a list of sheet names for which the data is to be retrieved
        :returns: in dates horizontal position of all dates
        """

        colPositionDates = []
        for indexSheet in range(len(sheets)):
            colDate=self._get_col_date(date, dates[indexSheet], startDates[indexSheet])
                        # if date not exist for group

            colPositionDates.append(colDate)
        return colPositionDates

    def _get_attendances(self, colPositionDates, sheets, multiple_sheets_data):
        """
        Get array of attendance for All date and sheet
        
        :param colPositionDates: col date position in googleSheet for all sheets
        :param sheets: a list of sheet names for which the data is to be retrieved
        :param multiple_sheets_data: a list of data for every sheet in sheets
        :returns: array of attendance for all sheets, which we have
        """
        
        attendances=[]
        for indexSheet in range(len(sheets)):
            # get sheet Data by name Sheet
            sheetData=multiple_sheets_data[sheets[indexSheet]]
            
            # get col with attandance Data
            attendanceSheet=sheetData[colPositionDates[indexSheet]]
            # delete upper rows, which dont have info about attandance
            for index in range(0, self._row_start_date_attendance+1):
                if (len(attendanceSheet)<=0):
                    break;
                del attendanceSheet[0]
            
            # delete not used info in bottom isn't necessary - check fucntion - _convert_attendances_to_standart  
                
            # save attandance without upper rows
            attendances.append(attendanceSheet)

        return attendances
        
    def _convert_attendances_to_standart(self, attendances, lenArray):
        """
        Convert attendances to similar size with equal by index element in lenArray
        
        :param attendances: array of non convert attendance for ALL sheets
        :param lenArray: FIO arrays for ALL sheets 
        :returns: array of attendance, converted to length of lenArray
        """
        convertAttendances=[]
        for indexSheet in range(len(lenArray)):        
            convertAttendanceSheet = [0]*lenArray[indexSheet]
            for index in range(len(attendances[indexSheet])):
                if (index>=lenArray[indexSheet]):
                    break
                # set value only for 1
                if (attendances[indexSheet][index]=='1'):
                    convertAttendanceSheet[index]=1
            
            convertAttendances.append(convertAttendanceSheet)   
        
        return convertAttendances
    
    def _dropInfoWthoutDate(self, infoArray, colPositionDates):
        """
        Delete all coloumns in infoArray where for current index not exist horizontal position of the date in colPositionDates
        
        :param infoArray: array of info, like arr of groups or array of arrays FIO or attendance
        :param colPositionDates: array of horizontal position of the date - if not exist, than have value -1
        :returns: array with remove cols from infoArray, which have by index in colPositionDates value -1
        """
        actualInfo=[]
        lenArray=len(infoArray)
        for indexSheet in range(len(colPositionDates)):
            if (colPositionDates[indexSheet]>=0):
                if (indexSheet<lenArray):
                    actualInfo.append(infoArray[indexSheet])
        return actualInfo
        
    def _getSizeOfArraysInArray(self, infoArray):
        """
        Find sizes for all arrays in infoArray
        
        !Attention: Not correct result if not array (if string, int...)
        
        :param infoArray: array of info, like arr of groups or array of arrays FIO or attendance
        :returns: array of sizes elements (arrays) in infoArray 
        """   
    
        lenArray=[]
        for array in infoArray:
            lenArray.append(len(array))
        return lenArray

    
    def getGoogleSheetInfoByDate(self, date, id_google_sheet):
        """
        Get all necessary info by googleSheetSettings, static params and date.
        
        !Attention: if we dont have any information, than returns: [] for all param
        
        :param date: non convert attandance for ALL sheets
        :param FIOs: FIO arrays for ALL sheets 
        :returns:   sheets - names of all sheets (equal groups)
                    FIOs - array of array FIO for every group
                    colPositionDates - array of horizontal position of the date and Attendances
                    attendances - array of array attendances for avery group              
        """
        self._setIdGoogleSheet(id_google_sheet)
        # get all sheets
        # sheets are equal groups
        sheets=self._get_sheet_names()
        # get all info in every sheet
        result = self._get_multiple_sheets_data(sheets)

        # get start position of dates and attendance, and also dates
        startAttendance, datesAttendance = self._find_dates_and_ranges_attendance(sheets, result)
        # get horizontal position of date for attandance for all sheets
        colPositionDates = self._get_all_col_dates(date, datesAttendance, startAttendance, sheets)      
        # Convert to actual info
        sheets = self._dropInfoWthoutDate(sheets, colPositionDates)
        colPositionDates = self._dropInfoWthoutDate(colPositionDates, colPositionDates)      
        if (len(sheets)<=0):
            raise Exception("Сan't find the group that studied that day in google sheet. Check your input date or check dates in google sheets!")
        # get FIOs for every sheet
        FIOs = self._find_FIOs(sheets, result)
        lenArray = self._getSizeOfArraysInArray(FIOs)
        # get attandances for every sheet
        attendances = self._get_attendances(colPositionDates, sheets, result)  
        # get convert attendances for every sheet        
        attendances = self._convert_attendances_to_standart(attendances, lenArray)
        return (sheets, colPositionDates, FIOs, attendances)



    # get standart print of range
    def _getRange(self, nameSheet, startCol, startRow, endCol, endRow):
        """
        Get range of region for sending info to google sheet
        
        :param nameSheet: string name of the sheet
        :param startCol: start horizontal position of the region - string word
        :param startRow: start vertical position of the region - integer number
        :param endCol: end horizontal position of region - string word
        :param endRow: end vertical position of the region - integer number
        
        :returns: region in format '{nameSheet}!{startCol}{startRow}:{endCol}{endRow}'           
        """
        return f"'{str(nameSheet)}'!{str(startCol)}{str(startRow)}:{str(endCol)}{str(endRow)}"
    
    
    def _getColNameFromColInt(self, col):
        """
        Get name of col in google sheet from col number
        
        :param col: int horizontal number in google Sheet
     
        :returns: col like in google sheet: 2-> 'C', 27-> 'AB'         
        """
        row=''
        while (col>=0):
            row=chr(ord('A')+int(col%self._len_English_Sub))+row
            col=math.floor(col/self._len_English_Sub)-1
        return row
      
       
    def _convertToSendAttendance(self, rowAtendanse):
        """
        Get attandance in format to send - in col, without 0 (converted to '')
        
        :param rowAtendanse: standart array attandanse for one sheet
     
        :returns: data for sending in col format: [0, 1, 0] -> [[''],[1],['']]         
        """
        colAtendanse=[]
        for attendance in rowAtendanse:
            if (attendance==0):
                colAtendanse.append([''])   
            else:
                colAtendanse.append([attendance])                
        return colAtendanse
    
    
    def _updateAttendanseSheet(self, nameSheet, col, startRow, endRow, atendanse):
        """
        Update region (which is atendanse) in google sheet with using convertation of row atendanse
        
        :param nameSheet: string name of the sheet
        :param col: horizontal position of the atendanse - integer number
        :param startRow: start vertical position of the atendanse - integer number
        :param endCol: end horizontal position of atendanse - string word
        :param aatendanse: row of atendanse for nameSheet (group)
        
        :returns: count of updated cells (all of them, even not changed...)           
        """
        atendanse=self._convertToSendAttendance(atendanse)
        col=self._getColNameFromColInt(col)
        #myRange='self._getRange(nameSheet, col, startRow, col, endRow)'
        data = [{
            'range': self._getRange(nameSheet, col, startRow, col, endRow),
            'values': atendanse
        }]
        
        body = {
            'valueInputOption': 'RAW', # USER_ENTERED
            'data': data
        }
        try:
            result = self.__spreadsheet.values().batchUpdate(spreadsheetId=self._GOOGLE_SPREADSHEET_ID, body=body).execute()
        except Exception as ex:
            raise Exception("Can't send information to google sheet. Please check the correctness of the google spreadheet ID.\nYou can find this ID in url of your google Table.\nFull text of exception: " + str(ex))
        return result.get('totalUpdatedCells')

        
       
    def setAllAttendancesSheet(self, sheets, colPositionDate, attendances, id_google_sheet):
        """
        Update region (which is atendanse) in google sheet for all sheets
        
        :param sheets: array of google sheet (equal group)
        :param colPositionDate: array of horizontal position of the atendanse for every sheet
        :param attendances: array of attandance (which is array too) for every sheet (group)
        
        :returns:   isSendSomething - result of send (did we send somthing?)
                    sendErrors - log of errors, which we get, when send information
        """
        self._setIdGoogleSheet(id_google_sheet)
        isSendSomething=False
        sendErrors = []

        for index in range(len(sheets)):
            if (len(attendances[index])>0):
                try:             
                    if (self._updateAttendanseSheet(sheets[index], 
                        colPositionDate[index], 
                        self._row_start_date_attendance+self._shift_rows+1, 
                        self._row_start_date_attendance+self._shift_rows+len(attendances[index]), 
                        attendances[index])>0):
                        isSendSomething=True                    
                    else:
                        sendErrors.append("For unknown reasons we can't send attendance info to group " + sheets[index] + " (zero updated).")
                except Exception as ex:
                    sendErrors.append("For unknown reasons we can't send attendance info to group " + sheets[index] + " (can't connect to sheet).\n\tFull text of exception: " + str(ex))
            else:
                # we can check this, where we get info - but in main fuction we couldn't find man with empty group (it can help to teacher)
                sendErrors.append('For group ' + sheets[index] + ' length of attendance equal zero')    
        return isSendSomething, sendErrors
            
#googleSheet=GoogleSheet()    
#sheets, colPositionDates, FIOs, attendance=googleSheet.getGoogleSheetInfoByDate('09.04')
#print(sheets)
#print(colPositionDates)
#print(FIOs)
#print(attendance)
     