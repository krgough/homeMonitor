#! /usr/bin/env python3
"""

Module for accessing train times from the National Rail SOAP API

Token should be saved as an env var called NATIONAL_RAIL_TOKEN
Suggest setting these in /etc/environment as follows...

# National Rail Token for API access
export NATIONAL_RAIL_TOKEN='<TOKEN_HERE>'

National Rail API Key:
https://realtime.nationalrail.co.uk/OpenLDBWSRegistration/Registration

National Rail API Docs
https://lite.realtime.nationalrail.co.uk/OpenLDBWS/

CRS = Computer Reservation Service a.k.a. station name
CRS codes here:
http://www.nationalrail.co.uk/static/documents/content/station_codes.csv
win = winchester, wat = waterloo

CRS Codes from here:
https://www.nationalrail.co.uk/stations_destinations/48541.aspx

Zeep SOAP Lib for Python:
https://docs.python-zeep.org/en/master/index.html#

Open Rail Group for Info:
https://groups.google.com/g/openraildata-talk
https://github.com/openraildata/openldbws-example-python/blob/main/getDepartureBoardExample.py

"""
from argparse import ArgumentParser
import csv
import logging
import sys
from textwrap import dedent

import dotenv
from io import StringIO
import os
import requests
from tabulate import tabulate
from zeep import Client, Settings, xsd

LOGGER = logging.getLogger(__name__)

dotenv.load_dotenv()

try:
    ACCESS_TOKEN = os.environ["NATIONAL_RAIL_TOKEN"]
    # API_TOKEN_PATH = os.environ['HIVE_API_PATH']
except KeyError:
    print(dedent(f"""
    ERROR: Enviroment variable {NATIONAL_RAIL_TOKEN_NAME} is not set.
    Get a token here:
    https://realtime.nationalrail.co.uk/OpenLDBWSRegistration/Registration
    Put it in an environment variable...
    NATIONAL_RAIL_TOKEN=<insert-token-here>
    """))
    sys.exit()

WSDL = 'http://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx?ver=2021-11-01'


# Try to parse invalid xml as best as possible (even if there are errors)
SETTINGS = Settings(strict=False)

# history = HistoryPlugin()
# client = Client(wsdl=WSDL, settings=settings, plugins=[history])

HEADER = xsd.Element(
    '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken',
    xsd.ComplexType([
        xsd.Element(
            '{http://thalesgroup.com/RTTI/2013-11-28/Token/types}TokenValue',
            xsd.String()),
    ])
)

HEADER_VALUE = HEADER(TokenValue=ACCESS_TOKEN)
CRS_FILE = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "crs.csv")


def get_args():
    """Get the cli arguments"""
    parser = ArgumentParser(description="Get live train data from National Rail")
    subparsers = parser.add_subparsers(help="Subcommands:", dest='command')

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Set logging level to DEBUG"
    )

    subparsers.required = True

    departures = subparsers.add_parser('departures', help="Get departure board")
    departures.set_defaults(func=get_departures)

    departures.add_argument(
        '-f', "--from_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'from' station e.g. WIN for Winchester"
    )
    departures.add_argument(
        '-t', "--to_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'to' station e.g. WAT for London Waterloo"
    )

    arrivals = subparsers.add_parser('arrivals', help="Get arrivals board")
    arrivals.set_defaults(func=get_arrivals)

    arrivals.add_argument(
        '-f', "--from_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'from' station e.g. WIN for Winchester"
    )

    arrivals.add_argument(
        "-t", "--to_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'to' station e.g. WAT for London Waterloo"
    )

    crs_codes = subparsers.add_parser(
        "crs-codes",
        help="Show a list of station CRS codes or find a given CRS",
    )
    crs_codes.set_defaults(func=refresh_crs_codes_csv)
    crs_codes.add_argument(
        "-r", "--refresh",
        type=str,
        help="Refresh the CRS csv file"
    )
    crs_codes.add_argument(
        "-c", "--code",
        type=str,
        help="Find Station Name for a given CRS"
    )

    delays = subparsers.add_parser(
        "delays",
        help="Show departure delays"
    )
    delays.set_defaults(func=get_delays)
    delays.add_argument(
        '-f', "--from_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'from' station e.g. WIN for Winchester"
    )
    delays.add_argument(
        "-t", "--to_crs",
        type=str.upper,
        required=True,
        help="CRS Station code for 'to' station e.g. WAT for London Waterloo"
    )

    return parser.parse_args()


def refresh_crs_codes_csv():
    """Get a list of the crs station codes
    This convoluted csv file read is required because the data
    is in multiple columns and there is at least one station name
    that contains commas
    """
    req = requests.get("https://www.nationalrail.co.uk/station_codes%20(07-12-2020).csv")
    file = StringIO(req.text)
    reader = csv.reader(file, delimiter=',')

    # Ignore the header line
    next(reader)

    crs = ["Station Name"]
    for row in reader:
        for i in range(0, len(row), 2):
            if row[i] != "":
                crs.append(row[i:i+2])
    crs = sorted(crs, key=lambda x: x[0])

    with open(CRS_FILE, mode="w", encoding="UTF-8") as crs_file:
        csv_writer = csv.writer(crs_file, quotechar='"')
        csv_writer.writerow(["Station Name", "CRS"])
        csv_writer.writerows(crs)

    LOGGER.info("CRS file updated: %s", CRS_FILE)


def get_station_name(crs_code):
    """Lookup a station name from a CRS code"""
    with open(CRS_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for line in reader:
            if line['CRS'] == crs_code.upper():
                return line['Station Name']
    return None


def get_arrivals(from_crs, to_crs):
    """Get the arrivals boards for the given station"""
    client = Client(wsdl=WSDL, settings=SETTINGS)
    res = client.service.GetArrivalBoard(
        numRows=10,
        crs=to_crs.upper(),
        filterCrs=from_crs.upper(),
        filterType='from',
        _soapheaders=[HEADER_VALUE]
    )
    LOGGER.debug(res)
    try:
        services = res.trainServices.service
        results = [
            {
                "std": train.std,
                "etd": train.etd,
                "sta": train.sta,
                "eta": train.eta,
                "isCancelled": train.isCancelled,
                "cancelReason": train.cancelReason,
                "delayReason": train.delayReason,
                "platform": train.platform,
                "to": to_crs.upper(),
                "from": from_crs.upper(),
                "origin": [org.locationName for org in train.origin.location],
                "destination": [org.locationName for org in train.destination.location],
            }
            for train in services
        ]

    except AttributeError:
        LOGGER.error("Did not find 'services' key in the soap response: %s", res)
        results = []

    return results


def get_departures(from_crs, to_crs):
    """Get the departure board for the given stations"""
    client = Client(wsdl=WSDL, settings=SETTINGS)
    res = client.service.GetDepartureBoard(
        numRows=10,
        crs=from_crs.upper(),
        filterCrs=to_crs.upper(),
        filterType='to',
        _soapheaders=[HEADER_VALUE]
    )
    LOGGER.debug(res)
    try:
        services = res.trainServices.service
        results = [
            {
                "std": train.std,
                "etd": train.etd,
                "sta": train.sta,
                "eta": train.eta,
                "isCancelled": train.isCancelled,
                "cancelReason": train.cancelReason,
                "delayReason": train.delayReason,
                "platform": train.platform,
                "to": to_crs.upper(),
                "from": from_crs.upper(),
                "origin": [org.locationName for org in train.origin.location],
                "destination": [org.locationName for org in train.destination.location],
            }
            for train in services
        ]

    except AttributeError:
        LOGGER.error("Did not find 'services' key in soap response: %s", res)
        results = []

    return results


def get_delays(from_crs, to_crs):
    """Get Departure Delays"""
    departures = get_departures(from_crs, to_crs)
    delays = [d for d in departures if d['etd'] != "On time"]
    return delays


def main():
    """Entry Point"""
    args = get_args()

    logging.getLogger("zeep").setLevel(level=logging.WARNING)
    logging.getLogger("urllib3").setLevel(level=logging.WARNING)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    results = []

    if args.command == 'departures':
        results = get_departures(to_crs=args.to_crs, from_crs=args.from_crs)
    elif args.command == 'arrivals':
        results = get_arrivals(to_crs=args.to_crs, from_crs=args.from_crs)
    elif args.command == 'delays':
        results = get_delays(to_crs=args.to_crs, from_crs=args.from_crs)

    if results:
        print(tabulate(results, headers='keys'))

    if args.command == 'refresh':
        if args.name:
            refresh_crs_codes_csv()


if __name__ == "__main__":
    main()
