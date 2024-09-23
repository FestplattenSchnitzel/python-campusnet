import re
import sys
from typing import Union, List
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
import datetime

VERSION = "0.4"


class LoginError(ValueError):
    pass


@dataclass
class Module:
    num: str
    name: str
    credits: float
    status: str
    semesters: List[str]
    id: str
    grade: Union[float, None] = None


@dataclass
class Exam:
    name: Union[str, None]
    semester: str
    description: str
    grade: Union[float, None] = None


@dataclass
class Document:
    name: str
    date_time: datetime.datetime | None


class CampusNetSession:
    def __init__(
        self,
        username: str = None,
        password: str = None,
        base_url="https://dualis.dhbw.de/",
    ):
        """
        Initialize a new CampusNetSession.
        :param username: The username of the user.
        :param password: The password of the user.
        :raises:
            ValueError: If the username or password is empty.
            LoginError: If the login failed.
        """
        self.username = username
        self.password = password
        self.base_url = base_url
        self._semesters = None
        self._modules = None
        if self.username is None:
            raise ValueError("Username is empty.")
        if self.password is None:
            raise ValueError("Password is empty.")
        self.session = requests.Session()
        self._login()

    @property
    def mgrqispi(self):
        if self.base_url.endswith("/"):
            return self.base_url + "scripts/mgrqispi.dll"
        else:
            return self.base_url + "/scripts/mgrqispi.dll"

    """
    From the CampusNet website:
    ```javascript
    >>> reloadpage.createUrlAndReload.toString()
    function(dispatcher, applicationName, programName, sessionNo, menuId,args){
        [...]
        window.location.href = dispatcher + \"?APPNAME=\" + applicationName + \"&PRGNAME=\" + programName + \"&ARGUMENTS=-N\" + sessionNo + \",-N\" + menuId  + temp_args;
    }
    ```
    """

    def create_url(self, program_name, args="", application_name="CampusNet"):
        # Note: MenuID is purely visual, so it doesn't matter. Always pass the HOME menu id.
        return f"{self.mgrqispi}?APPNAME={application_name}&PRGNAME={program_name}&ARGUMENTS=-N{self.session_number},-N00019{args}"

    def _login(self):
        """
        Login to the CampusNet.
        :raises:
            LoginError: If the login failed.
        """
        response = self.session.post(
            self.mgrqispi,
            data={
                "usrname": self.username,
                "pass": self.password,
                "APPNAME": "CampusNet",
                "PRGNAME": "LOGINCHECK",
                "ARGUMENTS": "clino,usrname,pass,menuno,menu_type,browser,platform",
                "clino": "000000000000001",
                "menuno": "000324",
                "menu_type": "classic",
                "browser": "",
                "platform": "",
            },
        )
        if len(response.cookies) == 0:  # We didn't get a session token in response
            raise LoginError("Login failed.")

        # The header looks like this
        # 0; URL=/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=STARTPAGE_DISPATCH&ARGUMENTS=-N954433323189667,-N000019,-N000000000000000
        # url will be "/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=STARTPAGE_DISPATCH&ARGUMENTS=-N954433323189667,-N000019,-N000000000000000"
        # and arguments will be "-N954433323189667,-N000019,-N000000000000000"
        # 954433323189667 is the session id, 000019 is the menu id and -N000000000000000 are temporary arguments
        self.session_number = re.match(
            r"^.*-N(\d+),-N(\d+),-N(\d+)$", response.headers["Refresh"]
        ).group(1)

    def _get_semesters(self):
        """
        Get the semesters from the CampusNet.
        :return: A list of semesters.
        """
        response = self.session.get(self.create_url("COURSERESULTS"))
        response.encoding = "ISO-8859-1"
        soup = BeautifulSoup(response.text, "html.parser")
        semesters = {}
        for semester in soup.find_all("option"):
            semesters[semester.text] = semester.get("value")
        return semesters

    @property
    def semesters(self):
        """
        Lazily loads the semesters.
        :return: A dictionary of all semesters.
        """
        if not self._semesters:
            self._semesters = self._get_semesters()
        return self._semesters

    def _get_modules(self):
        """
        Get the modules from the CampusNet.
        :return: A list of modules.
        """
        modules = []
        for semester in self.semesters:
            response = self.session.post(
                self.mgrqispi,
                data={
                    "APPNAME": "CampusNet",
                    "semester": self.semesters[semester],
                    "Refresh": "Aktualisieren",
                    "PRGNAME": "COURSERESULTS",
                    "ARGUMENTS": "sessionno,menuno,semester",
                    "sessionno": self.session_number,
                    "menuno": "000307",
                },
            )
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", {"class": "nb list"})
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) == 6:
                    try:
                        grade = float(cells[2].text.strip().replace(",", "."))
                    except ValueError:
                        grade = None
                    # getting id for this module
                    exams_button = cells[4].find("a")
                    exams_id = exams_button.get("href").split(",-N")[-2]
                    num = cells[0].text.strip()
                    if not any(module.num == num for module in modules):
                        modules.append(
                            Module(
                                num=num,
                                name=cells[1].text.strip(),
                                # credits=float(cells[3].text.strip().replace(",", ".")),
                                credits=0,
                                status=cells[3].text.strip(),
                                semesters=[semester],
                                id=exams_id,
                                grade=grade,
                            )
                        )
                    else:
                        for module in modules:
                            if module.num == num:
                                module.semesters.append(semester)
                                break
                elif len(cells) != 0:
                    # FIXME: proper logging
                    print("Unexpected number of cells:", len(cells), file=sys.stderr)
        return modules

    @property
    def modules(self):
        """
        Lazily loads the modules.
        :return: A list of all modules.
        """
        if not self._modules:
            self._modules = self._get_modules()
        return self._modules

    def get_exams_for_module(self, module: Module):
        """
        Get the exams for a module.
        :param module: The module.
        :return: A list of exams.
        """
        response = self.session.get(self.create_url("RESULTDETAILS", f",-N{module.id}"))
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        exam_table = soup.find("table", {"class": "tb"})
        exams = []
        current_heading = None
        for row in exam_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 1 and "level02" in cells[0]["class"]:
                # variable to persist header into the next iteration
                current_heading = cells[0].text.strip()
            if len(cells) == 6 and all("tbdata" in cell["class"] for cell in cells):
                try:
                    grade = float(cells[3].text.strip().replace(",", "."))
                except ValueError:
                    grade = None
                exams.append(
                    Exam(
                        name=current_heading,
                        semester=cells[0].text.strip(),
                        description=cells[1].text.strip(),
                        grade=grade,
                    )
                )
        return exams

    def get_documents(self) -> list[Document]:
        response = self.session.get(self.create_url("CREATEDOCUMENT"))
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"class": "tb"})
        documents: list[Document] = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            name: str = cells[0].text

            try:
                date_time = datetime.datetime.strptime(
                    f"{cells[1].text} {cells[2].text}", "%d.%m.%y %H:%M"
                )
            except ValueError:
                date_time = None

            documents.append(Document(name=name, date_time=date_time))

        return documents
