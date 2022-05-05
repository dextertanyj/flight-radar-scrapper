import typing
import platform
import os
import multiprocessing
import multiprocessing.pool

from collections import OrderedDict
from datetime import datetime, timedelta
from time import sleep

from bs4 import BeautifulSoup, NavigableString, Tag
from pyvirtualdisplay import Display
from undetected_chromedriver import Chrome
from xlsxwriter import Workbook

##
# Global Constants
##

BASE_URL = "https://www.flightradar24.com"

AIRPORT_NAME_HEADER = "AIRPORT NAME"
AIRPORT_CODE_HEADER = "ICAO AIRPORT CODE"
AIRLINE_HEADER = "AIRLINE"
TYPE_NAME_HEADER = "TYPE NAME"
TYPE_CODE_HEADER = "TYPE CODE"
REGISTRATION_HEADER = "REGISTRATION"
DATE_HEADER = "DATE"
GROUND_TIME_HEADER = "GROUND TIME"
FROM_FLIGHT_HEADER = "FROM FLIGHT"
FROM_AIRPORT_HEADER = "FROM AIRPORT"
FROM_AIRPORT_CODE_HEADER = "FROM AIRPORT CODE"
ARRIVAL_TIME_HEADER = "ARRIVAL TIME"
TO_FLIGHT_HEADER = "TO FLIGHT"
TO_AIRPORT_HEADER = "TO AIRPORT"
TO_AIRPORT_CODE_HEADER = "TO AIRPORT CODE"
DEPARTURE_TIME_HEADER = "DEPARTURE TIME"

HEADERS = [AIRPORT_NAME_HEADER, AIRPORT_CODE_HEADER, AIRLINE_HEADER, TYPE_NAME_HEADER,
           TYPE_CODE_HEADER, REGISTRATION_HEADER, DATE_HEADER, GROUND_TIME_HEADER, FROM_FLIGHT_HEADER,
           FROM_AIRPORT_HEADER, FROM_AIRPORT_CODE_HEADER, ARRIVAL_TIME_HEADER, TO_FLIGHT_HEADER,
           TO_AIRPORT_HEADER, TO_AIRPORT_CODE_HEADER, DEPARTURE_TIME_HEADER]


##
# Utility Functions
##


def log(msg: str):
    """Prints a log message to standard output."""
    pid = os.getpid()
    time = datetime.now()
    print("[{time} ({pid})] {msg}".format(time=time.strftime("%Y-%m-%d %H:%M:%S"), pid=str(pid), msg=msg))


def clean_string(string: typing.Union[str, NavigableString]) -> typing.Optional[str]:
    """Removes any surrounding whitespaces and parentheses around the string."""
    trimmed = string.strip()
    if (trimmed.startswith("(") and trimmed.endswith(")")):
        trimmed = trimmed[1:-1]
    return check_string(trimmed)


def check_string(string: typing.Union[str, NavigableString]) -> typing.Optional[str]:
    """Checks if the string represents an empty value."""
    if string == "—":
        return None
    return string


def string_to_delta(string: typing.Optional[str]) -> typing.Optional[timedelta]:
    """Converts the given string to a timedelta object."""
    if (string == None):
        return None
    (hour, minutes) = string.split(":")
    return timedelta(hours=int(hour), minutes=int(minutes))


def timestamp_to_datetime(string: typing.Optional[str]) -> typing.Optional[datetime]:
    """Converts the given string to a datetime object."""
    if (string == None or string == ""):
        return None
    return datetime.utcfromtimestamp(int(string))


##
# Class Definitions
##


class Context:
    """The context of a subprocess."""
    def __init__(self):
        self.display = None
        if (platform.system() != "Windows" and ("DISPLAY" not in os.environ or os.environ["DISPLAY"] == 0)):
            self.display = Display(visible=0, size=(800, 600))
            self.display.start()
        self.driver = Chrome()
        log("Created context")

    def reinitialize(self):
        """Recreates the web driver."""
        self.driver.quit()
        self.driver = Chrome()
        log("Reinitialized context")

    def __del__(self):
        self.driver.quit()
        if self.display is not None:
            self.display.stop()


class Printable:
    """An abstract class that represents entities which can be printed."""
    def get_attribute(self, attribute: str) -> str:
        """Returns the"""
        pass

    def write_info(self, info: typing.Dict[str, str]):
        """Writes to the dictionary the respective values for the given keys if the class contains the information for the key."""
        for attribute in info.keys():
            if self.get_attribute(attribute) == "" or self.get_attribute(attribute) is None:
                continue
            info[attribute] = self.get_attribute(attribute)


class Airport:
    """The class representing an airport."""
    def __init__(self, code: str, name: str):
        self.code = code
        self.name = name

    def __str__(self):
        return "{name} ({code})".format(name=self.name, code=self.code)

    def __eq__(self, other):
        if not isinstance(other, Airport):
            return False
        return self.code == other.code


class AirportDB:
    """A database of Airports keyed on their ICAO code."""
    def __init__(self, airports: typing.Dict[str, Airport]):
        self.airports = airports

    def contains(self, code: str) -> bool:
        """Returns true if the Airport has an existing entry."""
        return code in self.airports

    def get(self, code: str) -> Airport:
        """Retrieves the Airport with the provided ICAO code."""
        return self.airports[code]

    def insert(self, code: str, name: str) -> Airport:
        """Inserts and returns the Aiport with the given name and ICAO code."""
        self.airports[code] = Airport(code, name)
        return self.airports[code]


class Flight:
    """The class representing a flight."""
    def __init__(self,
                 name: str,
                 source: typing.Optional[Airport],
                 destination: typing.Optional[Airport],
                 flight_time: typing.Optional[timedelta],
                 scheduled_departure: typing.Optional[datetime],
                 actual_departure: typing.Optional[datetime],
                 scheduled_arrival: typing.Optional[datetime],
                 actual_arrival: typing.Optional[datetime]):
        self.name = name
        self.source = source
        self.destination = destination
        self.flight_time = flight_time
        self.scheduled_departure = scheduled_departure
        self.actual_departure = actual_departure
        self.scheduled_arrival = scheduled_arrival
        self.actual_arrival = actual_arrival

    def is_extractable(self):
        """Returns true if the flight has the nessecary information for further analysis."""
        return (self.source is not None or self.destination is not None) and (
            self.actual_departure is not None or self.actual_arrival is not None)


class FlightPair(Printable):
    """The class representing two consecutive flights of an aircraft."""
    def __init__(self, incoming: Flight, outgoing: Flight):
        self.incoming = incoming
        self.outgoing = outgoing

    def get_attribute(self, attribute: str) -> str:
        if attribute == AIRPORT_NAME_HEADER:
            return self.incoming.destination.name
        if attribute == AIRPORT_CODE_HEADER:
            return self.incoming.destination.code
        if attribute == DATE_HEADER:
            return self.incoming.actual_arrival.strftime("%d %b %Y")
        if attribute == GROUND_TIME_HEADER:
            delta = self.outgoing.actual_departure - self.incoming.actual_arrival
            return "{hours}:{minutes}:{seconds}".format(
                hours=delta.days * 24 + delta.seconds // 3600,
                minutes=(delta.seconds // 60) % 60,
                seconds=delta.seconds % 60)
        if attribute == FROM_FLIGHT_HEADER:
            return self.incoming.name
        if attribute == FROM_AIRPORT_HEADER:
            return self.incoming.source.name if self.incoming.source is not None else "Unknown"
        if attribute == FROM_AIRPORT_CODE_HEADER:
            return self.incoming.source.code if self.incoming.source is not None else "Unknown"
        if attribute == ARRIVAL_TIME_HEADER:
            return self.incoming.actual_arrival.strftime("%H:%M")
        if attribute == TO_FLIGHT_HEADER:
            return self.outgoing.name
        if attribute == TO_AIRPORT_HEADER:
            return self.outgoing.destination.name if self.outgoing.destination is not None else "Unknown"
        if attribute == TO_AIRPORT_CODE_HEADER:
            return self.outgoing.destination.code if self.outgoing.destination is not None else "Unknown"
        if attribute == DEPARTURE_TIME_HEADER:
            return self.outgoing.actual_departure.strftime("%H:%M")
        return ""



class Aircraft(Printable):
    """The class representing an aircraft."""
    def __init__(self, registration: str, link: str):
        self.registration = registration
        self.link = link
        self.flights: typing.List[Flight] = []
        self.type_name = ""
        self.type_code = ""

    def add_details(self, type_name: str, type_code: str):
        """Insert data about the aircraft's type."""
        self.type_name = type_name
        self.type_code = type_code

    def add_flight(self, flight: Flight):
        """Adds a flight made by this aircraft."""
        self.flights.append(flight)

    def orderable_flights(self) -> typing.List[Flight]:
        """Returns a list of flights with known source or destination airports according to their chornological order."""
        valid_flights = list(filter(lambda flight: flight.is_extractable(), self.flights))
        valid_flights.sort(key=lambda flight: flight.actual_departure if flight.actual_departure is not None else flight.actual_arrival)
        return valid_flights

    def get_attribute(self, attribute: str) -> str:
        if attribute == REGISTRATION_HEADER:
            return self.registration
        if attribute == TYPE_NAME_HEADER:
            return self.type_name
        if attribute == TYPE_CODE_HEADER:
            return self.type_code
        return ""


class Airline(Printable):
    """The class representing an airline."""
    def __init__(self, name: str, link: str):
        self.name = name
        self.link = link
        self.aircrafts: typing.List[Aircraft] = []

    def add_aircraft(self, aircraft: Aircraft):
        """Adds an aircraft operated by this airline."""
        self.aircrafts.append(aircraft)

    def get_attribute(self, attribute: str) -> str:
        if attribute == AIRLINE_HEADER:
            return self.name
        return ""


##
# Global Variables & Initialization
##


CONTEXT = None
AIRPORT_DATABASE = None


def initialize_context(drivers, displays, airports):
    """Initializes the context and links the shared airport database."""
    global CONTEXT
    global AIRPORT_DATABASE
    AIRPORT_DATABASE = AirportDB(airports)
    CONTEXT = Context()


##
# Web Scraping Functions
##


def retrieve_page(url: str) -> BeautifulSoup:
    """Retrives the page at the given url."""
    global CONTEXT
    try:
        CONTEXT.driver.get(url)
        while CONTEXT.driver.page_source.find("Checking your browser before accessing") != -1:
            log("Bot protection triggered")
            sleep(1)
        return BeautifulSoup(CONTEXT.driver.page_source, "lxml")
    except:
        CONTEXT.reinitialize()
        return retrieve_page(url)


def retrieve_airlines() -> typing.List[Airline]:
    """Retrieves the list of all airlines."""
    log("Retrieving airlines")
    airlines: typing.List[Airline] = []
    soup = retrieve_page(BASE_URL + "/data/airlines")
    data = soup.findAll("td", class_="notranslate")
    count = 0
    for entry in data:
        name = clean_string(entry.a.string)
        link = entry.a["href"]
        airline = Airline(name, link)
        airlines.append(airline)
    return airlines


def retrieve_fleet(airline: Airline):
    """Retrieves the aircrafts operated by the given airline."""
    log("Processing airline: {name}".format(name=airline.name))
    soup = retrieve_page(BASE_URL + airline.link + "/fleet")
    data = soup.findAll("a", class_="regLinks")
    for entry in data:
        registration = clean_string(entry.string)
        link = entry["href"]
        aircraft = Aircraft(registration, link)
        airline.add_aircraft(aircraft)
    return airline


def retrieve_aircraft_details(aircraft: Aircraft):
    """Retrieves additional details and flights about the given aircraft."""
    log("Processing aircraft: %s" % aircraft.registration)
    soup = retrieve_page(BASE_URL + aircraft.link)
    type_name = clean_string(soup.find("label", text="AIRCRAFT").parent.find(
        "span", class_="details").string)
    type_code = clean_string(soup.find("label", text="TYPE CODE").parent.find(
        "span", class_="details").string)
    aircraft.add_details(type_name, type_code)
    data = soup.findAll("tr", class_="data-row")
    for entry in data:
        flight = process_flight_details(entry)
        aircraft.add_flight(flight)
    return aircraft


def process_flight_details(row: Tag) -> Flight:
    """Extracts the flight data from the given HTML DOM table row."""
    source_airport = process_airport(row.contents[3])
    destination_airport = process_airport(row.contents[4])
    name = clean_string(row.contents[5].a.string) if row.contents[5].a != None else clean_string(
        row.contents[5].string)

    flight_time_string = clean_string(row.contents[6].string)
    scheduled_departure_string = row.contents[7]["data-timestamp"]
    actual_departure_string = row.contents[8]["data-timestamp"]
    scheduled_arrival_string = row.contents[9]["data-timestamp"]
    actual_arrival_string = None if row.contents[11][
        "data-prefix"] != "Landed " else row.contents[11]["data-timestamp"]

    scheduled_departure = timestamp_to_datetime(scheduled_departure_string)
    actual_departure = timestamp_to_datetime(actual_departure_string)
    scheduled_arrival = timestamp_to_datetime(scheduled_arrival_string)
    actual_arrival = timestamp_to_datetime(actual_arrival_string)

    return Flight(name, 
                  source_airport, 
                  destination_airport, 
                  string_to_delta(flight_time_string), 
                  scheduled_departure, 
                  actual_departure, 
                  scheduled_arrival, 
                  actual_arrival)


def process_airport(container: Tag) -> typing.Optional[Airport]:
    """Extracts the airport from the given HTML DOM component."""
    global AIRPORT_DATABASE
    if container.a is None:
        return None
    code = clean_string(container.a.string)
    airport = AIRPORT_DATABASE.get(code) if AIRPORT_DATABASE.contains(
        code) else AIRPORT_DATABASE.insert(code, clean_string(container['title'].split(",")[0]))
    return airport


##
# Data Extraction Functions
##


def process_aircraft(data: typing.List[typing.List[str]], base_info: OrderedDict, airline: Airline, aircraft: Aircraft):
    """Extracts the necessary data needed from the flights of the given aircraft and stores them in the given data."""
    info = base_info
    airline.write_info(info)
    aircraft.write_info(info)
    flights = aircraft.orderable_flights()
    services = process_flights(flights)
    for service in services:
        service.write_info(info)
        data.append(list(info.values()))


def process_flights(flights: typing.List[Flight]) -> typing.List[FlightPair]:
    """Converts a list of flights into a list of consecutive flight pairs."""
    services = []
    for idx in range(1, len(flights)):
        outgoing = flights[idx]
        if (outgoing.source is None or outgoing.actual_departure is None):
            continue
        incoming_idx = idx - 1
        while (incoming_idx >= 0 and flights[incoming_idx].destination != outgoing.source):
            incoming_idx -= 1
        if incoming_idx < 0:
            continue
        incoming = flights[incoming_idx]
        if incoming.actual_arrival is None:
            continue
        services.append(FlightPair(incoming, outgoing))
    return services


##
# Data Export Functions
##


def write_row(worksheet, row: int, data: typing.List[str]):
    """Writes the values of the given data to a row, based on the order of insertion."""
    col = 0
    for value in data:
        if value == "":
            col += 1
            continue
        worksheet.write(row, col, value)
        col += 1


def write_headers(worksheet):
    """Writes the headers to the given worksheet."""
    write_row(worksheet, 0, HEADERS)


def write_data(data: typing.List[typing.List[str]]):
    """Exports the given data."""
    log("Writing data")
    workbook = Workbook("Output.xlsx")
    worksheet = workbook.add_worksheet()
    row = 1
    write_headers(worksheet)
    for entry in data:
        write_row(worksheet, row, entry)
        row += 1
    workbook.close()
    log("Completed")


##
#  The following classes are necessary to allow the subprocesses to spawn web driver processes.
##

# We monkey patch the multiprocessing pool worker to insert our own cleanup code to prevent orphans.
existing_worker = multiprocessing.pool.worker
def custom_worker(*args, **kwargs):
    existing_worker(*args, **kwargs)
    global CONTEXT
    try:
        CONTEXT.driver.quit()
        if CONTEXT.display is not None:
            CONTEXT.display.stop()
    except:
        pass
multiprocessing.pool.worker = custom_worker


class NoDaemonProcess(multiprocessing.Process):
    @property
    def daemon(self):
        return False

    @daemon.setter
    def daemon(self, value):
        pass


class NoDaemonContext(type(multiprocessing.get_context())):
    Process = NoDaemonProcess


class NestablePool(multiprocessing.pool.Pool):
    def __init__(self, *args, **kwargs):
        kwargs['context'] = NoDaemonContext()
        super(NestablePool, self).__init__(*args, **kwargs)


if __name__ == "__main__":
    manager = multiprocessing.Manager()
    drivers = manager.list()
    displays = manager.list()
    airports = manager.dict()
    data = []
    base_info = OrderedDict()
    pool = NestablePool(initializer=initialize_context, initargs={drivers, displays, airports})
    for header in HEADERS:
        base_info[header] = ""
    try:
        airlines = pool.apply(retrieve_airlines)
        airlines = pool.map(retrieve_fleet, airlines)
        for airline in airlines:
            for aircraft in airline.aircrafts:
                # We capture the airline using a curried lambda to ensure the airline is correct when the callback is executed.
                callback = (lambda airline: lambda aircraft: process_aircraft(data, base_info, airline, aircraft))(airline)
                pool.apply_async(retrieve_aircraft_details, args={aircraft},
                                 callback=callback)
        pool.close()
        pool.join()
    finally:
        pool.terminate()
        write_data(data)
