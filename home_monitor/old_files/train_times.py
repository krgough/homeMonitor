#!/usr/bin/env python3
"""

Application to check and display train service data.

Uses the national rail Enquiries API to access live train data.
This API is SOAP based so we use the Huxley service (REST Json wrapper service)
Huxley - UK Live Train Status - https://huxley.unop.uk/

Users should first get a user token from Nation Rail enquiries:
https://realtime.nationalrail.co.uk/OpenLDBWSRegistration/Registration

Token should be saved as an env var called NATIONAL_RAIL_TOKEN
Suggest setting these in /etc/environment as follows...

# KG: National Rail Token for API access
export NATIONAL_RAIL_TOKEN='<TOKEN_HERE>'

25/11/2019 Keith Gough
PEP8 Updates

"""
# import time
import os
import sys
import getopt
import pprint
from textwrap import dedent
import logging
# import json
import requests

LOGGER = logging.getLogger(__name__)

# Get a token here:
# https://realtime.nationalrail.co.uk/OpenLDBWSRegistration/Registration

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

# ACCESS_TOKEN = None
# API_TOKEN_PATH = os.path.join(API_TOKEN_PATH, 'cfg', 'apiTokens.txt')
# if not os.path.exists(API_TOKEN_PATH):
#     print("API TOKEN FILE NOT FOUND: {}".format(API_TOKEN_PATH))
#     sys.exit()
# with open(API_TOKEN_PATH, mode='r') as f:
#     for line in f:
#         name, token = line.strip().split('=')
#         if name == "NATIONAL_RAIL_TOKEN":
#             ACCESS_TOKEN = token
# if ACCESS_TOKEN is None:
#     print("NATIONAL_RAIL_TOKEN was not found in {}".format(API_TOKEN_PATH))
#     sys.exit()

API_URL = "https://huxley.apphb.com"

# CRS = Computer Reservation Service a.k.a. station name
# CRS codes here:
# http://www.nationalrail.co.uk/static/documents/content/station_codes.csv
# win = winchester, wat = waterloo


def get_args():
    """ Read command line parameters
    """
    help_string = dedent(f"""
    USAGE: {os.path.basename(__file__)} [-h] -t to_station -f from_station

    Use these command line options:

    -h                      Print this help
    -t 'to' stationId       CRS code for station e.g. wat for Waterloo
    -f 'from' stationId     CRS code for station
    """)

    my_to_station = None
    my_from_station = None

    opts = getopt.getopt(sys.argv[1:], "ht:f:")[0]

    for opt, arg in opts:
        # print(opt, arg)
        if opt == '-h':
            print(help_string)
            sys.exit()
        if opt == '-t':
            my_to_station = arg
        if opt == '-f':
            my_from_station = arg

    if not my_to_station:
        print("\nError: toStation was not specified")
        print(help_string)
        sys.exit()

    if not my_from_station:
        print("\nError: fromStation was not specified")
        print(help_string)
        sys.exit()

    return my_to_station, my_from_station


def api_call(method, url, expected_resp=200):
    """ Api call handler
    """
    resp = None
    resp_status = False
    try:
        if method == "GET":
            resp = requests.get(url=url)
            resp_status = bool(resp.status_code == expected_resp)
        else:
            LOGGER.error("%s Method not implemented", method)

    except requests.exceptions.RequestException as err:
        LOGGER.error("Exception in api_call. %s", err)

    return resp_status, resp


def get_url(board, crs, filter_type, filter_crs, times=None):
    """ Make the API call
    """
    url = f"{API_URL}/{board}/{crs}"
    # if filter_type: url = url + "/{}/{}/all".format(filter_type,filter_crs)

    if filter_type:
        url = f"{url}/{filter_type}/{filter_crs}"

    # if numRows: url = url + "/{}".format(numRows)
    if times:
        url = f"{url}/10/{times}"

    url = f"{url}?accessToken={ACCESS_TOKEN}"

    # resp = requests.get(url)
    # resp_status = True
    # resp_status = bool(resp.status_code == 200)
    resp_status, resp = api_call('GET', url)
    return resp_status, resp


def get_service(service_id):
    """ GET /service/{Service ID}?accessToken={Your GUID token}
    """
    url = f"{API_URL}/service/{service_id}?accessToken={ACCESS_TOKEN}"
    # resp = requests.get(url)
    # resp_status = bool(resp.status_code == 200)
    resp_status, resp = api_call("GET", url)
    return resp_status, resp


def get_stations(station_name=None):
    """  Returns a list of matching station crs codes
         Returns all stations if station_name is None
    """
    if station_name:
        url = f"{API_URL}/crs/{station_name}?{ACCESS_TOKEN}"
    else:
        url = f"{API_URL}/crs?{ACCESS_TOKEN}"
    # resp = requests.get(url)
    # resp_status = bool(resp.status_code == 200)
    resp_status, resp = api_call("GET", url)
    return resp_status, resp


def get_board(board_name, crs, filter_crs, filter_type,
              times=None, pretty_print=False):
    # pylint: disable=too-many-arguments
    """ Get the wanted board results
    """
    resp_status, resp = get_url(board_name, crs, filter_type,
                                filter_crs, times=times)
    # LOGGER.debug(resp.json())

    if pretty_print:
        print(resp.url)
        pprint.pprint(resp.json())

    results = []
    if resp_status:

        try:
            if board_name == "next":
                services = [resp.json()['departures'][0]['service']]
            else:
                services = resp.json()['trainServices']

            for service in services:
                serv = {}
                if filter_type == "from":
                    serv["to"] = crs
                    serv["from"] = filter_crs
                else:
                    serv["to"] = filter_crs
                    serv["from"] = crs

                serv['eta'] = service['eta']
                serv['sta'] = service['sta']
                serv['etd'] = service['etd']
                serv['std'] = service['std']
                serv['isCancelled'] = service['isCancelled']
                serv['cancelReason'] = service['cancelReason']
                serv['delayReason'] = service['delayReason']
                serv['platform'] = service['platform']
                results.append(serv)
        except (KeyError, TypeError):
            LOGGER.debug('ERROR parsing delays board in get_board(). %s', resp)
    else:
        LOGGER.debug('ERROR parsing delays board in get_board(). %s', resp)
    return results


def get_arrivals(to_station, from_station, pretty_print=False):
    """ GET /arrivals/{CRS|StationName}/{filterType}/{filterCRS|StationName}/
            all/{CRS|StationName}?accessToken={Your GUID token}
    """
    data = get_board("arrivals", to_station, from_station,
                     "from", pretty_print=pretty_print)
    return data


def get_departures(to_station, from_station, pretty_print=False):
    """ GET /departures/crs/filterType/filterCrs/{numRows}/
            {times}?accessToken={Your GUID token}
    """
    data = get_board("departures", to_station, from_station,
                     "to", pretty_print=pretty_print)
    return data


def get_next_trains(to_station, from_station, pretty_print=False):
    """ GET /next/{CRS|StationName}/{filterType}/
            {filterCRSs|StationNames}?accessToken={Your GUID token}
    """
    data = get_board("next", to_station, from_station,
                     "to", pretty_print=pretty_print)
    return data


def get_delays(to_station, from_station, pretty_print=False):
    """ GET /delays/{CRS|StationName}/{filterType}/{filterCRS|StationName}/
            {numRows}/{times}?accessToken={Your GUID token}
    """
    data = get_board("delays", to_station, from_station,
                     "to", pretty_print=pretty_print)
    data = [d for d in data if d['etd'] != "On time"]
    return data


def print_data(board_name, board_data):
    """ Print out the board data
    """
    print(board_name)
    for data in board_data:
        print(data)
    print()


def main():
    """ Main program
    """
    to_station, from_station = get_args()
    print_data("Arrivals:",
               get_arrivals(to_station, from_station, pretty_print=False))

    print_data("Next:",
               get_next_trains(from_station, to_station, pretty_print=False))

    print_data("Departures:",
               get_departures(from_station, to_station, pretty_print=False))

    print_data("Delays:",
               get_delays(from_station, to_station, pretty_print=False))

    print("All done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
