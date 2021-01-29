'''

Testing API calls via the cognito endpoint - I can't find documentation for
these APIs

Created on 28-Sep-2020

@author: Keith.Gough
'''

import json
import logging
import pprint
import sys

import requests

import config as cfg

LOGGER = logging.getLogger(__name__)


def api_cmd(cmd, url, headers, payload=None, expected_http_response=200):
    """ Send http commands using requests
        Handles unexpected HTTP response codes and ConnectionErrors
    """
    try:
        LOGGER.debug("cmd=%s, url=%s, payload=%s", cmd, url, payload)
        timeout = 60

#         kwargs = {'headers': headers.
#                   'data': payload,
#                   'url': url,
#                   'timeout': timeout}

        kwargs = {'headers': headers,
                  'data': payload,
                  'url': url,
                  'timeout': timeout}

        if cmd == 'GET':
            resp = requests.get(**kwargs)
        elif cmd == 'PUT':
            resp = requests.put(**kwargs)
        elif cmd == 'POST':
            resp = requests.post(**kwargs)

        else:
            LOGGER.error("HTTP Command not recognised: cmd=%s", cmd)
            sys.exit()

        resp_state = bool(resp.status_code == expected_http_response)

    except requests.exceptions.ConnectionError:
        resp_state = False
        resp = "Connection Error"

    LOGGER.debug("resp=%s", str(resp)[:150])

    return resp_state, resp


def main():
    """ Main Program """
    api_url = cfg.URL
    api_username = cfg.USERNAME
    api_password = cfg.PASSWORD

    # Old access point
#     url = api_url + '/omnia/auth/sessions'
#     payload = json.dumps({'sessions': [{'username': api_username,
#                                        'password': api_password}]})
#     old_headers = {'Accept': 'application/vnd.alertme.zoo-6.3+json',
#                    'X-Omnia-Client': 'KG',
#                    'Content-Type': 'application/json'}

    url = 'https://beekeeper.hivehome.com/1.0/global/admin-login'
    payload = json.dumps({'username': api_username,
                          'password': api_password,
                          'actions': False,
                          'devices': False,
                          'homes': False,
                          'products': False})

    headers = {'Accept': '*/*'}

    cmd = 'POST'

    resp_state, resp = api_cmd(cmd, url, headers, payload)
    pprint.pprint(resp.json())

    # Get /nodes
    headers = old_headers
    headers['X-Omnia-Access-Token'] = resp.json()['token']
    url = api_url + '/omnia/nodes/'
    cmd = 'GET'
    resp_status, resp = api_cmd(cmd, url, headers)
    print(resp.json)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
