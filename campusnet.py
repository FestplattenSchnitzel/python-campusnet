# Julian Lemmerich
# 30.06.2022
# Interacting with Campus net
# more specifically DHBW's Campusnet at dualis.dhbw.de

import requests
import re

## Login

email = 's212689%40student.dhbw-mannheim.de' #urlencoded! @ = %40
password = input('Password: ')

headers = {
    'Host': 'dualis.dhbw.de',
    'Content-Type': 'application/x-www-form-urlencoded',
}

data = f'usrname={email}&pass={password}&APPNAME=CampusNet&PRGNAME=LOGINCHECK&ARGUMENTS=clino%2Cusrname%2Cpass%2Cmenuno%2Cmenu_type%2Cbrowser%2Cplatform'

response = requests.post('https://dualis.dhbw.de/scripts/mgrqispi.dll', headers=headers, data=data)

cnsc = response.headers['Set-cookie'][0:38].replace(" ", "") #cookie in format "csnc =FA27B61020C03AA5A83046B13D6CC38D; HttpOnly; secure" broken down to "csnc=FA27B61020C03AA5A83046B13D6CC38D"

# TODO: something is borken with that cnsc. It looks identical to a valid one, but only gives access denied.
# debug:
cnsc = 'cnsc=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

## Get all Semesters

# Prüfungsergebnisse Tab: https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=COURSERESULTS&ARGUMENTS=-N422875220398735,-N000307,
# Semesterlist: <select id="semester" .*> </select>
# then get value from option, display name

headers = {
    'Host': 'dualis.dhbw.de',
    'Cookie': cnsc,
}

response = requests.get('https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=COURSERESULTS&ARGUMENTS=-N591469968597102,-N000307', data="", headers=headers)

print(response.text)

semester = {}

for match in re.findall('<option value=".*</option>', response.text):
    semester[match.split('>')[1].split('<')[0]]=match[15:30] #key=name, value=id

## Get all Prüfungen in Semester

## Get Prüfungen Results