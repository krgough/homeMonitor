#! /usr/bin/env python3
"""

Module for accessing train times from the National Rail SOAP API

Token should be saved as an env var called NATIONAL_RAIL_TOKEN
Suggest setting these in /etc/environment as follows...

# KG: National Rail Token for API access
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
import sys
from textwrap import dedent

from io import StringIO
import os
import requests
from tabulate import tabulate
from zeep import Client, Settings, xsd

NATIONAL_RAIL_TOKEN_NAME = "NATIONAL_RAIL_TOKEN"

try:
    ACCESS_TOKEN = os.environ[NATIONAL_RAIL_TOKEN_NAME]
    # API_TOKEN_PATH = os.environ['HIVE_API_PATH']
except KeyError:
    print(dedent("""
    ERROR: Enviroment variable 'HIVE_API_PATH' is not set.
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


def get_args():
    """Get the cli arguments"""
    parser = ArgumentParser(description="Get live train data from National Rail")
    subparsers = parser.add_subparsers(help="Subcommands:", dest='command')
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
    crs_codes.set_defaults(func=get_crs_codes)
    crs_codes.add_argument(
        "-n", "--name",
        type=str,
        help="Find CRS for given station name"
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

    args = parser.parse_args()
    # # Print help if no args supplied
    # if not vars(args):
    #     parser.print_help()
    #     args = None
    #     sys.exit(1)

    return args


def get_crs_codes(name):
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

    crs = []
    for row in reader:
        for i in range(0, len(row), 2):
            if row[i] != "":
                crs.append(row[i:i+2])
    crs = sorted(crs, key=lambda x: x[0])

    if name:
        print(f"Station: {name}, CRS={[station for station in crs if station[0] == name][0][1]}")
    else:
        print(tabulate(crs))


def get_station_name(crs_code):
    """Lookup a station name from a CRS code"""
    with open("crs.csv", mode="r", encoding="utf-8") as file:
        for line in file:
            row = line.strip().rsplit(",", 1)
            if row[1] == crs_code.upper():
                return row[0]
    return ""


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

    services = res.trainServices.service
    print(services)
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
    return results


def get_delays(from_crs, to_crs):
    """Get Departure Delays"""
    departures = get_departures(from_crs, to_crs)
    delays = [d for d in departures if d['etd'] != "On time"]
    return delays


def main():
    """Entry Point"""
    args = get_args()
    results = []

    if args.command == 'departures':
        results = get_departures(to_crs=args.to_crs, from_crs=args.from_crs)
    elif args.command == 'arrivals':
        results = get_arrivals(to_crs=args.to_crs, from_crs=args.from_crs)
    elif args.command == 'delays':
        results = get_delays(to_crs=args.to_crs, from_crs=args.from_crs)

    if results:
        print(tabulate(results, headers='keys'))

    if args.command == 'crs-codes':
        if args.name:
            get_crs_codes(name=args.name)
        if args.code:
            print(get_station_name(crs_code=args.code))


if __name__ == "__main__":
    main()
