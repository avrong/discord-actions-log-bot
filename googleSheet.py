import re
import enum

from googleSheetDefault import GoogleSheet
import googleSheetDefault
# Предусловия:
# ФИО - каждая составляющая ФИО начинается с большой буквы, остальные маленькие
# Нет чувствительности к отчеству (в случае, если нет инициалов)
# Допускается форматы записи:
# Фамилия Имя Отчество, Имя Отчество Фамилия, Фамилия И О, И О Фамилия, Фамилия Имя, Имя Фамилия
# Группа может быть встроена в любое место
# ФИО обязательно должно быть русскоязычным
# Допускаются несовпадения по схожестям букв. Главное, чтобы введенная группа совпадала с наименованием таблицы.
# Везде предполагается, что в качестве пробельных знаков используются только пробелы (не табуляции и т.п.)

#Замену английских в именах на русские не производим. т.к. Если кто-то напишет Петров А. В. z 
# - то мы не можем воспринять, что это Петров А. В.
# Алгоритм пытается соотнести содержимое никнейма и результата
  
# Класс, определяющий парсинг информации с гугл sheet
class GoogleSheetInfo:
    
    def __init__(self, group, positionInGoogleList, arrayOfPartsFIOs, attendanceArray):
        self.__group = group # example: '4933'
        self.__positionInGoogleList = positionInGoogleList # horizontal position in google Sheet - example: 15
        self.__arrayOfPartsFIOs = arrayOfPartsFIOs # array of FIO from group (FIO in array too)
        self.__attendanceArray = attendanceArray # attendance for group - array like: [0, 0, 1, 1, 0]
        
    
    def getGroup(self):
        return self.__group
    
    def getPositionInGoogleList(self):
        return self.__positionInGoogleList
    
    def getArrayOfPartsFIOs(self):
        return self.__arrayOfPartsFIOs
    
    def getArrayOfPartsFIOByIndex(self, index):
        if (index>=0 and index<len(self.__arrayOfPartsFIOs)):
            return self.__arrayOfPartsFIOs[index]
        else:
            return ''
    
    def getAttendanceArray(self):
        return self.__attendanceArray    
        
    def getAttendanceArrayByIndex(self, index):
        return self.__attendanceArray[index]    
    
    def setGroup(self, group):
        self.__group = group
    
    def setPositionInGoogleList(self, positionInGoogleList):
        self.__positionInGoogleList = positionInGoogleList
    
    def setArrayOfPartsFIOs(self, arrayOfPartsFIOs):
        self.__arrayOfPartsFIOs = arrayOfPartsFIOs
    
    def setAttendanceArray(self, attendanceArray):
        self.__attendanceArray = attendanceArray

    def setAttendanceArrayByIndex(self, index, attendanceArrayElement=1):
        if index in range(len(self.__attendanceArray)):
            self.__attendanceArray[index] = attendanceArrayElement

# defaul variants, which is similar in lower and in upper? or only an upper (for exceptions variants) 
fromEngToRusDefault={'K':'К', 'M':'М', 'E':'Е', 'C':'С', 'X':'Х', 'Y':'У', 'O':'О', 'A':'А', 'T':'Т', 'B':'В', 'P':'Р', 'H':'Н',
'k':'к', 'm':'м', 'e':'е', 'c':'с', 'x':'х', 'y':'у', 'o':'о', 'a':'а', 'p':'р'}

# symbols, which need to be converted
convertSymb={'Ё':'Е', 'ё':'е'} # 'Й':'И', 'й':'и'

# класс перечислений вариантов алгоритма
class variantsOfAlgoritm(enum.Enum):
        withSpace = 1 # приводим к пробелам
        withUpperBegin = 2 # приводим к верхнему регистру начало
        withUpperBeginAndLowerAnother = 3 # приводим к верхнему регистру начало, остальное к нижнему
        withConvertToRussian = 4 # переводим все английские буквы в русские

# dictionary of variants for parse name
dictVariantsOfAlgoritm = {
    0 : [variantsOfAlgoritm.withSpace],
    1 : [variantsOfAlgoritm.withSpace, variantsOfAlgoritm.withUpperBegin],
    2 : [variantsOfAlgoritm.withSpace, variantsOfAlgoritm.withUpperBeginAndLowerAnother],
    3 : [variantsOfAlgoritm.withUpperBegin],
    4 : [variantsOfAlgoritm.withUpperBeginAndLowerAnother],
    5 : [variantsOfAlgoritm.withConvertToRussian],
    6 : [variantsOfAlgoritm.withConvertToRussian, variantsOfAlgoritm.withSpace],
    7 : [variantsOfAlgoritm.withConvertToRussian, variantsOfAlgoritm.withSpace, variantsOfAlgoritm.withUpperBegin],
    8 : [variantsOfAlgoritm.withConvertToRussian, variantsOfAlgoritm.withSpace, variantsOfAlgoritm.withUpperBeginAndLowerAnother],
    9 : [variantsOfAlgoritm.withConvertToRussian, variantsOfAlgoritm.withUpperBegin],
    10 : [variantsOfAlgoritm.withConvertToRussian, variantsOfAlgoritm.withUpperBeginAndLowerAnother]
}       

# State of successful result
class successState(enum.Enum):
    SuccessfulCompare = 1
  
# State of warning result  
class warningState(enum.Enum):
    CompareButNotEqual = 1 # мало информации, но уникален - Петров А или Петров, Петров А В, или Петров Андр
    # корректный вариант - Петров Андрей, Петров Андрей Владимирович
    AlreadySetAttendance = 2 # уже стоит не 0 в google sheet

# State of error result  
class errorState(enum.Enum):
    UnknownGroup = 1 # не удалось извлечь группу
    NotExist = 3 # не нашли совпадения
    NotUnique = 4 # не уникален в группе
    NotUniqueByGroup = 2 # при парсинге нашлось несколько групп, в которые можно проставить посещаемость


class GoogleSheetParser:

    # Предупреждения
    __resultErrors=[]
    # Ошибки
    __resultWarnings=[]

    __googleSheetInfoArray=[]

    __dictResult={
        'alreadyUpdated' : 0,
        'updated' : 0,
        'notUpdated' : 0,
        'errors' : 0,
        'warnings' : 0,
    }


    def __init__(self):
        self.__resultErrors = []
        self.__resultWarnings=[] 
        self.__googleSheetInfoArray=[]
        self._clearDictResult()
        

    # очистка результата
    def _clearDictResult(self):
        for result in self.__dictResult:
            self.__dictResult[result] = 0
    
    # инкрементация результата
    def _incDictResult(self, result):
        if (result in [successState.SuccessfulCompare, warningState.CompareButNotEqual]):
            self.__dictResult['updated']+=1
        elif (result == warningState.AlreadySetAttendance):

            self.__dictResult['alreadyUpdated']+=1
        else:
            self.__dictResult['notUpdated']+=1

            
        if result in warningState:
             self.__dictResult['warnings']+=1
        elif result in errorState:
             self.__dictResult['errors']+=1

    # перобразовать результат словаря в сообщение
    def __dictResultToMessage(self):
        return "Total already updated: " + str(self.__dictResult['alreadyUpdated']) + '\n' + \
            "Total updated: " + str(self.__dictResult['updated']) +'\n' + \
            "Total not updated: " + str(self.__dictResult['notUpdated']) +'\n' + \
            "Total google errors: " + str(self.__dictResult['errors']) +'\n' + \
            "Total google warnings: " + str(self.__dictResult['warnings']) +'\n'


    # преобразует массив вида [group, [arrfio, arrfio]] в строку вида "'group': 'f i o' 'f i o'; "
    def _getStringForErrorsAndWarnings(self, info):
        groupFIO=info[0]
        FIOs=info[1]
        # set group
        result = "'" + info[0]+ "'" + ": "
        # для каждого arrfio
        for index in range(len(FIOs)):
            if (index!=0):
                result+=' '
            result+="'"+' '.join(FIOs[index])+"'"
        result+=';'
        return result

    # Получить предупреждение или ошибку        
    def _getErrorOrWarning(self, enumValue, nick, info=[]):
        nick=str(nick)
    # info =[[group, [arrfio, arrfio]]...] - NotUniqueByGroup
    # info =[group, [arrfio, arrfio]] - errorState.NotUnique
    # info =[group, [arrfio]] - warningState.CompareButNotEqual
        if (enumValue == errorState.UnknownGroup):
            return "Error: '" + nick + "' have wrong group or group doesn't exists in google sheet"
        elif (enumValue ==  enumValue == errorState.NotUniqueByGroup):
            result = "Error: '" + nick + "' have more than one coincidence in different groups - "
            for indexGroupFIO in range(len(info)):
                result+= " in group " +  self._getStringForErrorsAndWarnings(info[indexGroupFIO])
            return result
        elif (enumValue == errorState.NotExist):
            return "Error: nick '" + nick + "' not Exist in google sheet;"
        elif (enumValue == errorState.NotUnique):
            return "Error: nick '" + nick + "' not unique in google sheet - in group " + self._getStringForErrorsAndWarnings(info)       
        elif (enumValue == warningState.CompareButNotEqual):
            return "Warning: nick '" + nick + "' is short, but we find an unique - in group " + self._getStringForErrorsAndWarnings(info)
        elif (enumValue == warningState.AlreadySetAttendance):
            return "Warning: for nick '" + nick + "' attendance has been already set - in group " + self._getStringForErrorsAndWarnings(info)
        else:
            return ''


    # привести к пробелам знаки
    def _turnToSpacesSigns(self, stroka):
        return re.sub(r'[^a-zA-Zа-яА-ЯёЁ]', " ",  stroka)
        
    # удаляем все, кроме букв, чисел
    def _delSigns(self, stroka):
        return re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]', "",  stroka)


    # заменяем все на русские буквы и пробелы
    # Петров А.В. -> ПетровАВ
    def _turnToSpacesAllWthoutName(self, stroka):
        return re.sub(r'[^а-яА-ЯёЁ\s]', " ",  stroka)

    # оставляем только буквы русского алфавита
    def _delAllWthoutName(self, stroka):
        return re.sub(r'[^а-яА-ЯёЁ]', "",  stroka)    

    # получить индекс первого числа в строке
    def _getIndexFirstDigit(self, stroka, startPosition = 0):
        # если начальная позиция находится за границами
        if (startPosition>=len(stroka) or startPosition<0):
            return -1
        for index in range(startPosition, len(stroka)):
            if (stroka[index].isdigit()):
                return index
        # иначе нет нет чисел - возвращаем -1
        return -1



    # приводим к нижнему регистру и к английскому алфавиту подобные
    def _toGroupStandartSymb(self, symbGroup):
        # to Up register   
        symbGroup = symbGroup.upper()
        if symbGroup in fromEngToRusDefault:
            return fromEngToRusDefault[symbGroup].upper()
        else:
            return symbGroup.upper()
    
    def _fromEnglishToRussianName(self, name):
        newName=''
        for index in range(len(name)):
            if name[index] in fromEngToRusDefault:
                newName+=fromEngToRusDefault[name[index]]
            else:
                newName+=name[index]
        return newName
        
        # to Up register   
        symbGroup = symbGroup.upper()
        if symbGroup in fromEngToRusDefault:
            return fromEngToRusDefault[symbGroup]
        else:
            return symbGroup
    
    
    # Конвертация русских символов - ё, й
    def _convertSymb(self, name):
        newName=''
        for index in range(len(name)):
            if name[index] in convertSymb:
                newName+=convertSymb[name[index]]
            else:
                newName+=name[index]
        return newName
            
    
    # сравниваем формат символов и их значения - для всех символов группы
    def _compareFormatSymb(self, group, groupNick):
        # если размеры не равны
        if (len(group)!=len(groupNick)):
            return False
            
        # для каждого элемента производим проверку
        for index in range(len(group)):
            if (group[index].isdigit()):
                if (group[index]!=groupNick[index]):
                    return False
            else:
                # здесь нужна более жестка функция проверки
                if (self._toGroupStandartSymb(group[index])!=self._toGroupStandartSymb(groupNick[index])):
                    return False
        # если дошли до сюда, то они равны по признаку значений
        return True
        
        
        
    # все символы начала приводим к верхнему регистру (т.е. после пробелов)
    # позволяет решить проблему петров андрейВладимирович-> Петров АндрейВладимирович, а далее парсинг по большим буквам
    def _beginOfWordToUpRegister(self, stroka, toLower=False):
        # убираем крайние пробелы
        stroka=stroka.strip()
        if (len(stroka)<1):
            return ''
        parseStroka=''
        isSpace = True
        for index in range(len(stroka)):
            # если пробел
            if (stroka[index]==' '):
                isSpace=True
                parseStroka+=stroka[index]
            # если есть тригер на увлеичение
            elif (isSpace==True):
                    parseStroka+=stroka[index].upper()
                    isSpace=False
            elif (toLower==True):
                parseStroka+=stroka[index].lower()
            else:
                parseStroka+=stroka[index]
        # возвращаем результат парсинга
        return parseStroka

        
    # получаем составные части    
    def _parseNameToParts(self, name):
        # убираем все символы, кроме ФИО (пробелы также удаляются)
        name=self._delAllWthoutName(name)
        name=self._convertSymb(name)
        if (len(name)<=0):
            return []
        # парсим и получаем части ФИО
        parseArr=[name[0].upper()]
        currentName=0
        for index in range(1, len(name)):
            # если в верхнем регистре
            if (name[index].upper()==name[index]):
                #добавляем в конец
                parseArr.append(name[index])
                # текущий индекс - следующий
                currentName+=1
            else:
                #добавляем в конец текущего - нет смысла в lower
                parseArr[currentName]+=name[index]
        return parseArr
        
    # получить массив нумерации массива по индексам без пробелов относительно начального     
    def _getIndicesNickWithoutSignes(self, nick):
        resultArr=[]
        for index in range(len(nick)):
            if (self._delSigns(nick[index])!=''):
                resultArr.append(index)
        return resultArr
        
            
        
    # получить группу из имени          
    # на вход - получаем стандартную группу, nick и nick без спец. символов, массив соответствия индексов последних двух
    def _getNickWthoutGroupFromNick(self, group, nick, parseNick, indices):
        # получаем индекс начала для группы - группа обязательно должна содержать числа, иначе может возникнуть очень много неточностей парсинга
        startDigitGroup=self._getIndexFirstDigit(group)
        if (startDigitGroup<0):
            return errorState.UnknownGroup
        
        # для никнейма получаем индекс начала числа
        startDigitNick=self._getIndexFirstDigit(parseNick)
        
        # пока не конец
        while (startDigitNick>=0 and startDigitNick<len(parseNick)):
            # левая граница группы в нике
            leftBorder=startDigitNick-startDigitGroup
            # правая граница группы в нике
            rightBorder=leftBorder+len(group)-1
            
            # если в никнейме не помещется искомая группа слева
            if  (leftBorder<0 or
                    # если в никнейме не помещется искомая группа справа
                    rightBorder>=len(parseNick)):
                # то пытаемся пойти дальше - сдвигаемся на величину до начала группы
                startDigitNick=self._getIndexFirstDigit(parseNick, startDigitNick+startDigitGroup+1)
            # если группа равна
            else:
                # извлекаем группу срезом строки для никнейма
                parseGroup = parseNick[leftBorder:rightBorder+1]
                # если группы равны
                if (self._compareFormatSymb(group, parseGroup)):
                    # находим соответствие левой границы для стандартного ника
                    leftBorder=indices[leftBorder]
                    # находим соответствие правой границы для стандартного ника
                    rightBorder=indices[rightBorder]
                    # возвращаем срез никнейма без группы:
                    # срез не чувствителен к превышению лимита - возвращает пустоту
                    return nick[:leftBorder]+' '+ nick[rightBorder+1:]
                else:
                    # иначе пытаемся пойти дальше - сдвигаемся на величину до начала группы
                    startDigitNick=self._getIndexFirstDigit(parseNick, startDigitNick+startDigitGroup+1)
        
        # если мы здесь, значит не нашли совпадение для группы
        return errorState.UnknownGroup

    # получаем группу, которая соответствует и строку, которая записана в качестве группы в нике
    # [исходная группа, ник] or errorState.UnknownGroup
    def _getGroupAndNickWthoutGroup(self, group, nick):
        # получаем массив для случая удаления всех знаков nick
        indices=self._getIndicesNickWithoutSignes(nick)
        # получаем никнейм без спец. символов и пробелов
        parseNick = self._delSigns(nick)
        # пытаемся сопоставить группу с ником
        nickWthoutGroup=self._getNickWthoutGroupFromNick(group, nick,  parseNick, indices)
        # если группу получили (она равна искомой)
        if (nickWthoutGroup!=errorState.UnknownGroup):
            return [group, nickWthoutGroup]
        # если мы не нашли группу
        return errorState.UnknownGroup

    # TO DO: можно также перед всеми действиями (но группа должна быть удалена) если начало дальше идет русская буква,
    #, то мы приводим её к верхнему регистру



    # сопоставляем ФИО и полученные фрагменты никнейма
    # принимаем FIO и Nick в формате массивов
    def _compareFIOandNick(self, FIOArr, nickArr, isEqual=False):
        compareResult=[]
        # создаем массив заполненный нулями - нальчальное значение эквиваленты сравнения
        compareResult = [[0] * len(nickArr) for i in range(len(FIOArr))]
        for indexFIO in range(len(FIOArr)):
            for indexNick in range(len(nickArr)):
                # равно ли FIO строке nick - сравнение в одинаковом регистре (необзательно приведение)
                if (isEqual==True 
                    and nickArr[indexNick].lower() == FIOArr[indexFIO].lower()):
                    compareResult[indexFIO][indexNick]=1
                # начинается ли FIO со строки nick - сравнение в одинаковом регистре (необзательно приведение)
                elif (isEqual==False
                     and re.match(nickArr[indexNick].lower(), FIOArr[indexFIO].lower())!=None):
                    compareResult[indexFIO][indexNick]=1
        # проверяем - существует ли комбинация, при которой возможна идентичность        
        return self._isExistFioCombination(compareResult)       

    def _isExistFioCombination(self, compareResult):
        # если в фио всего один элемент - рассматриваем отдельно
        sumResultFIO=[]

        # считаем все суммы по каждому элемнту ФИО
        for indexFIO in range(len(compareResult)):
            sumResultFIO.append(sum(compareResult[indexFIO][i] for i in range(len(compareResult[indexFIO]))))
        # никнейм
        sumResultNick=[]
        # считаем все суммы по каждому элементу никнейма  
        for indexNick in range(len(compareResult[0])):
            sumResultNick.append(0)
            for indexFIO in range(len(compareResult)):
                sumResultNick[len(sumResultNick)-1]+=compareResult[indexFIO][indexNick]
        
        cntNonZero=0
        
        if (len(sumResultFIO)<len(sumResultNick)):
            if 0 in sumResultFIO:
                return False
            elif sumResultNick.count(1)<len(sumResultFIO):
                return False
            else:
                return True
        else:
            if 0 in sumResultNick:
                return False
            elif sumResultFIO.count(1)<len(sumResultNick):
                return False
            else:
                return True
       
       
    # Функция, которая пытается найти сопоставления путем приведения к Верхнему регистру начальных символов,
    # остальных к нижнему регистру, а также путем дальнейшего удаления знаков
    def _getPartsFormNickAlgoritm(self, nick, variants):
        # приводим к русскому языку подобные английские символы
        if variantsOfAlgoritm.withConvertToRussian in variants:
            nick=self._fromEnglishToRussianName(nick)
        # приводим к пробелам все знаки
        if variantsOfAlgoritm.withSpace in variants:
            nick=self._turnToSpacesSigns(nick)
        # все символы начала приводим к верхнему регистру (т.е. после пробелов), остальные к нижнему
        if variantsOfAlgoritm.withUpperBeginAndLowerAnother in variants:
            nick=self._beginOfWordToUpRegister(nick, True)   
        # все символы начала приводим к верхнему регистру (т.е. после пробелов), остальные к нижнему
        elif variantsOfAlgoritm.withUpperBegin in variants:
            nick=self._beginOfWordToUpRegister(nick)  
        # Получаем составные части никнейма
        return self._parseNameToParts(nick)
       
       
    # Функция сопоставления никнейма по массиву фамилий
    # Получаем посещаемость для ускорения работы
    def _compareNickAndFIOs(self, group, nickArr, FIOs):
        resultArray=[] # массив результата - записывает индексы ФИО
        isEqual=False # Флаг - было ли равенство
        # Сопостоавляем для каждого ФИО
        for indexFIO in range(len(FIOs)):
            if (len(FIOs[indexFIO])<=0):
                continue
             # если никнейм существует по равенству - добавляем в конец рассматриваемого массива
            if (self._compareFIOandNick(FIOs[indexFIO], nickArr, True)):
                isEqual=True
                resultArray.append(indexFIO)
            # если никнейм существует по вхождению   
            elif (self._compareFIOandNick(FIOs[indexFIO], nickArr)):
                resultArray.append(indexFIO)
        # рассматриваем различные случаи результата
        # если единственное -> уникально, записываем его
        if (len(resultArray)==1):
            
            # если найден по равенству и размер больше 1
            if (isEqual and len(nickArr)>1):
                # возвращаем успешное выполнение
                return successState.SuccessfulCompare, resultArray
            # иначе недостаточно уникален по данным   
            else:
                return warningState.CompareButNotEqual, resultArray   
            
            # возвращаем ФИО
            return successState.SuccessfulCompare, resultArray
        # если не существует
        elif (len(resultArray)<=0):
            return errorState.NotExist, resultArray
        # если не уникален
        else:
            return errorState.NotUnique, resultArray
     
    # вспомогательная функция сравнения двух массивов на равенство (без учета регистров)
    def _compareArrsWthoutRegister(self, arr1, arr2):
        # если размеры не равны:
        if (len(arr1)!=len(arr2)):
            return False
        # по каждому элементу
        for index in range(len(arr1)):
            # если элементы не равны
            if (arr1[index].lower()!=arr2[index].lower()):
                return False
        # списки равны
        return True  
        
       
    # производит поиск по всем ФИО
    # Принимает на вход массив массив групп, массив класса данных, никнейм
    # Возвращает результат обработки, массив значений расстановки оценок
    # результатом возвращает 
    def _findFIOfromFIOsToNick(self, group, nick, FIOs):  
        # получаем группу и никнейм с вырезанной группой
        groupAndNick=self._getGroupAndNickWthoutGroup(group, nick)
        # если группа неизвестная
        if (groupAndNick == errorState.UnknownGroup):
            return (errorState.UnknownGroup, [])
        
        # извлекаем соответствующую группу
        group=groupAndNick[0]
        
        # извлекаем никнейм без группы из самого массива
        parseNick=groupAndNick[1]

        prevNickArrs=[]
        nickArr=[]
        indexFIOs=[]
        # пробегаемся по всем вариантам словаря
        for variantIndex in range(len(dictVariantsOfAlgoritm)):
            nickArr = self._getPartsFormNickAlgoritm(parseNick, dictVariantsOfAlgoritm[variantIndex])
            # если количество элементов, полученных из ника слишком большое или слишком малое
            if (len(nickArr)>3 or len(nickArr)<1):
                continue
            for prevNick in prevNickArrs:
                if (self._compareArrsWthoutRegister(prevNick, nickArr)):
                    prevNickArrs.append(nickArr)
                    continue
            # если здесь, то не было одинаковых
            # получаем результат   
            result, indexFIOs = self._compareNickAndFIOs(group, nickArr, FIOs)
            # Если результат не Not exist - возвращаем результат
            if (result != errorState.NotExist):
                return result, indexFIOs
            indexFIOs=[]
        # если здесь, то не нашли
        return errorState.NotExist, indexFIOs

    # функция, которая проставляет посещения
    #def setActualAttendance(groups, group, self.__googleSheetInfoArray, indexFIO):
        # проставляем посещаемость
    #    self.__googleSheetInfoArray[groups.index(group)].setAttendanceArrayByIndex(indexFIO)

    # заменить в результате все индексы ФИО на ФИО
    def _changeIndexOfFIOsResultToFIOs(self, groups, result):
        # get group from result
        group=result[0]
        # get FIO from result
        FIOs=result[1]
        # For all FIOs get from index - FIO
        for indexFIO  in range(len(FIOs)):
            # заменяем индекс ФИО на ФИО
            FIOs[indexFIO]=self.__googleSheetInfoArray[groups.index(group)].getArrayOfPartsFIOByIndex(FIOs[indexFIO])
        result[1]=FIOs
        return result

        
        
    # from ['group', [fio, fio]] set attendance to self.__googleSheetInfoArray
    def _setAttendanceByResult(self, groups, results):
            group = results[0][0]
            indexFIO=results[0][1][0]
            if (self.__googleSheetInfoArray[groups.index(group)].getAttendanceArrayByIndex(indexFIO)!=0):
                return False
            else:
                self.__googleSheetInfoArray[groups.index(group)].setAttendanceArrayByIndex(indexFIO)  
                return True
     
    # TODO пока что возвращаем, но возможно лучше здесь же проставлять посещаемость, записывать ошибки и предупреждения
    # основная функция поиска ника серди всех групп и всех фамилий
    def _findNickFromGroupAndFIO(self, groups, nick):
        isCompareButNotEqual = False # для случая нехватки данных
        isExistGroup = False # если группа существует
        results=[] # содержит группу и ФИО

        # пробег по всем группам
        for indexGroup in range(len(groups)):
            result, indexFIOs = self._findFIOfromFIOsToNick(groups[indexGroup], 
            nick,
            self.__googleSheetInfoArray[indexGroup].getArrayOfPartsFIOs()
            )
            # если не уникален
            if (result==errorState.NotUnique):
                # clear all, that we have before and set not unique result
                results=[groups[indexGroup], indexFIOs]
                # convert result to string
                results = self._changeIndexOfFIOsResultToFIOs(groups, results)
                self.__resultErrors.append(self._getErrorOrWarning(errorState.NotUnique, nick, results))
                # increase result counter
                self._incDictResult(errorState.NotUnique)
                return 
            
            # Если резльтат успешное совпадение, то добавляем в конец
            if (result==successState.SuccessfulCompare):
                results.append([groups[indexGroup], indexFIOs])
                
            # Если резльтат "уникально и совпало, но не равно"
            if (result==warningState.CompareButNotEqual):
                isCompareButNotEqual=True
                results.append([groups[indexGroup], indexFIOs])
                
            if (result!=errorState.UnknownGroup):
                isExistGroup = True
       
        # если ровно одно совпадение
        if (len(results)==1):      
            # проставляем посещаемость
            # если посещаемость уже была проставлена
            if (self._setAttendanceByResult(groups, results) == False):
                results=self._changeIndexOfFIOsResultToFIOs(groups, results[0])
                self.__resultWarnings.append(self._getErrorOrWarning(warningState.AlreadySetAttendance, nick, results))  
                # increase result counter
                self._incDictResult(warningState.AlreadySetAttendance)
            else:
                # преобразум все индексы ФИО в ФИО
                results=self._changeIndexOfFIOsResultToFIOs(groups, results[0])
                # increase result counter
                self._incDictResult(successState.SuccessfulCompare)
            
            # случаи равенства
            if (isCompareButNotEqual):
                self.__resultWarnings.append(self._getErrorOrWarning(warningState.CompareButNotEqual, nick, results))
                
            return

        for indexResult in range(len(results)):
            results[indexResult]=self._changeIndexOfFIOsResultToFIOs(groups, results[indexResult])      
        
        # если не найдено совпадений
        if (len(results)<=0):
            # если группа существует
            if (isExistGroup):
                self.__resultErrors.append(self._getErrorOrWarning(errorState.NotExist, nick, results))
                # increase result counter
                self._incDictResult(errorState.NotExist)
            # если же не существует
            else:
                self.__resultErrors.append(self._getErrorOrWarning(errorState.UnknownGroup, nick))
                # increase result counter
                self._incDictResult(errorState.UnknownGroup)
                
        # если найдено больше двух совпадений (поиск по двум группам)
        else:
            self.__resultErrors.append(self._getErrorOrWarning(errorState.NotUniqueByGroup, nick, results))
            # increase result counter
            self._incDictResult(errorState.NotUniqueByGroup)

    # функция, которая пробегается по каждому нику
    def _findAllNicksFromGroupAndFIO(self, groups, nicks):
        for indexNick in range(len(nicks)):
            # в качестве результата принимаем строку ошибки либо пустую строку, если все хороошо
            self._findNickFromGroupAndFIO(groups, nicks[indexNick])

    def _convertFIOsToPartFIOs(self, FIOs):
        for index in range(len(FIOs)):
            FIOs[index]=self._parseNameToParts(FIOs[index])
        return FIOs

    # TODO функция формирования для группы объекта класса GoogleSheetInfo 
    def _convertFromGoogleSheet(self, groups, startAttendances, arrayFIOs, attendances):
        if (len(groups)!=len(startAttendances)
            or len(groups)!=len(arrayFIOs)
            or len(groups)!=len(attendances)):
            self.__resultErrors.append("Data from google sheet is not correct - parts have different length!")
            return False
        # convert info:
        for index in range(len(groups)):     
            self.__googleSheetInfoArray.append(
                GoogleSheetInfo(groups[index], startAttendances[index], self._convertFIOsToPartFIOs(arrayFIOs[index]), attendances[index]))
        return True
        
        
    # функция, которая записывает информацию из googleSheet в массив класса GoogleSheetInfo - возвращает этот массив
    # Причем, при записи ФИО сразу преобразует в формат частей ФИО
    # также заносит все никнеймы в гугл таблицу - принимает массивы
    # date - дата, по которой и будет происходить запись
    def _getAndConvertGoogleSheetInfo(self, date, googleSheet, id_google_sheet):
        try:
            groups, startAttendances, arrayFIOs, attendances = googleSheet.getGoogleSheetInfoByDate(date, id_google_sheet)
        except Exception as ex:
            raise ex

        return self._convertFromGoogleSheet(groups, startAttendances, arrayFIOs, attendances), groups


    # получить массив начальных позаций
    def _getStartAttendancesForGoogleSheet(self):
        startAttendances=[]
        for index in range(len(self.__googleSheetInfoArray)):
            startAttendances.append(self.__googleSheetInfoArray[index].getPositionInGoogleList())
        return startAttendances 

    # получить массив посещений
    def _getAttendancesForGoogleSheet(self):
        attendances=[]
        for index in range(len(self.__googleSheetInfoArray)):
            attendances.append(self.__googleSheetInfoArray[index].getAttendanceArray())
        return attendances  
        

    # функция, которая проставляет новую информацию по посещениям
    def setAttendanceFromNicksToGoogleSheet(self, date, nicks, id_google_sheet):
        # Обнуляем предупреждения и ошибки
        self.__resultWarnings=[]
        self.__resultErrors=[]
        # очищаем основной массив
        self.__googleSheetInfoArray.clear()
        # очищаем результат
        self._clearDictResult()
        
        googleSheet=None
        if (len(nicks)<=0):
            raise Exception("Don't have a nick to parse")
            
        try:
            googleSheet = GoogleSheet()
        except Exception as ex:
            raise ex
        
        try:
            result, groups = self._getAndConvertGoogleSheetInfo(date, googleSheet, id_google_sheet)
        except Exception as ex:
            raise ex
        #print(len(self.__googleSheetInfoArray))
        #for element in self.__googleSheetInfoArray:
        #    print(element.getGroup())
        #    print(element.getPositionInGoogleList())        
        #    print(element.getArrayOfPartsFIOs())
        #    print(element.getAttendanceArray())    
            
        if (result==False):
            return result, self.__resultWarnings, self.__resultErrors
        
        self._findAllNicksFromGroupAndFIO(groups, nicks)
        
        startAttendances=self._getStartAttendancesForGoogleSheet()
        
        attendances=self._getAttendancesForGoogleSheet()      
        
        
        result, sendErrors = googleSheet.setAllAttendancesSheet(groups, startAttendances, attendances, id_google_sheet)
        #print(groups)
        #print(startAttendances)
        #print(attendances)
        # объединяем списки ошибок
        self.__resultErrors+=sendErrors
        if (result == False):
            return result, self.__resultWarnings, self.__resultErrors
        else:
            return self.__dictResultToMessage(), self.__resultWarnings, self.__resultErrors
         
"""
Name_File = 'test.txt'  
def getNicksFromFile(nameFile):
    with open(nameFile, encoding='utf-8') as file:
        nicks = [row.strip() for row in file]
    while '' in nicks:
        nicks.remove('')
    return nicks
     
#get nicks from file
nicks=getNicksFromFile(Name_File)


googleSheetParser=GoogleSheetParser()
print(nicks)
#try:
messageResult, resWarnings, resErrors = googleSheetParser.setAttendanceFromNicksToGoogleSheet('19.02', nicks, '1mcc1xCHx02vXaGjXLmcNNP2VTIk_XrbeJfcYNBg-6Wg')
print(messageResult)
print(resWarnings)
print(resErrors)
#except Exception as ex:
#    print(ex)
"""



