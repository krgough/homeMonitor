'''
Minimal API methods for adjusting bulb levels or controlling plugs

@author: keith
'''
import json
import time
import sys
# import pprint
import logging
import requests
import config

# pylint: disable=logging-format-interpolation
LOGGER = logging.getLogger(__name__)

API_HEADERS = {'Accept': 'application/vnd.alertme.zoo-6.3+json',
               'X-Omnia-Client': 'KG',
               'Content-Type': 'application/json'}


def api_cmd(cmd, url, headers, payload=None, expected_http_response=200):
    """ Send http commands using requests
        Handles unexpected HTTP response codes and ConnectionErrors
    """
    try:
        LOGGER.debug("cmd=%s, url=%s, payload=%s", cmd, url, payload)
        timeout = 60

        kwargs = {'url': url,
                  'headers': headers,
                  'data': payload,
                  'timeout': timeout}

        if cmd == 'GET':
            resp = requests.get(**kwargs)
        elif cmd == 'PUT':
            resp = requests.put(**kwargs)
        elif cmd == 'POST':
            resp = requests.post(**kwargs)

        else:
            LOGGER.error("HTTP Command not recognised: cmd={}".format(cmd))
            sys.exit()

        resp_state = bool(resp.status_code == expected_http_response)

    except requests.exceptions.ConnectionError:
        resp_state = False
        resp = "Connection Error"

    LOGGER.debug("resp={}".format(str(resp)[:150]))

    return resp_state, resp


class ApiClass():
    """ Class for managing api sessions
        Intended for use as a base class for device control
        Includes the base http call methods

    """
    username = config.USERNAME
    password = config.PASSWORD
    api_url = config.URL
    headers = None

    def __init__(self):

        if ApiClass.headers is None:
            self.get_session_token()

#         resp_status, resp = self.get_node(node_name)
#         if resp_status:
#             self.node_id = resp['id']
#         else:
#             LOGGER.error("ERROR: Node ID was not found")
#             LOGGER.error("node_name = {}".format(node_name))
#             LOGGER.error(resp)
#             sys.exit()

    def api_call(self, cmd, url, payload=None, expected_http_response=200):
        """ Make the API call and handle re-freshing the session token """
        resp_state, resp = api_cmd(cmd, url, ApiClass.headers,
                                   payload, expected_http_response)

        # If we get a 401 then get a new session token and then retry
        if resp.status_code == 401:
            self.get_session_token()
            resp_state, resp = api_cmd(cmd, url, ApiClass.headers,
                                       payload, expected_http_response)

        return resp_state, resp

    def get_session_token(self):
        """ Get an access token
            Call this before any API call.  Session may have timed out between
            API calls if the delay is long enough.
        """
        url = ApiClass.api_url + '/omnia/auth/sessions'
        payload = json.dumps({'sessions': [{'username': ApiClass.username,
                                           'password': ApiClass.password}]})

        # We use dict() here to make a copy rather than creating a new
        # reference to original dict
        # This is because we don't want to modify the original when we add the
        # sessionId header.
        api_headers = dict(API_HEADERS)

        resp_state, resp = api_cmd("POST", url, api_headers, payload)

        if resp_state:
            # Extract the session Id token, this must be added to headers as
            # 'X-Omnia-Access-Token' for any subsequent API calls
            session = resp.json()['sessions'][0]
            api_headers['X-Omnia-Access-Token'] = session['sessionId']
            ApiClass.headers = api_headers
        else:
            self.headers = None
            LOGGER.error(resp, resp.text)

    def get_node(self, node_name):
        """  Get /nodes and return the wanted node that matches the node name
             Respstate = True/False = did the call succeed
             resp = whatever the call returned or a string error
        """
        # Make the call
        resp_status, resp = self.get_nodes()
        if resp_status:
            for node in resp.json()['nodes']:
                if node['name'] == node_name:
                    # if DEBUG: pprint.pprint(node)
                    resp = node

        return resp_status, resp

    def get_nodes(self):
        """ Get /nodes
            Return nodes json and resp_status
        """
        url = ApiClass.api_url + '/omnia/nodes/'
        resp_status, resp = self.api_call("GET", url)
        return resp_status, resp

    def set_attribute(self, node_id, attribute, target_value):
        """ Set the given node attribute target_value

            PUT /omnia/nodes/{node_id}
            payload = {"nodes":[{"attributes": {"attributeId":
                         {"target_value":target_value}}}]}
        """
        # Make the call
        payload = json.dumps({"nodes":
                              [{"attributes":
                                {attribute: {"target_value": target_value}}}]})
        url = ApiClass.api_url + '/omnia/nodes/{}'.format(node_id)
        resp_status, resp = self.api_call("PUT", url, payload=payload)
        return resp_status, resp

    def set_attributes(self, node_id, attribute_value_dict):
        """ Set the given attributes to the given values
            {"attr1":"val1", "attr2":"val2" ...}
        """
        # Make the call
        attributes = {attr: {"targetValue": targetValue} for
                      attr, targetValue in attribute_value_dict.items()}
        payload = json.dumps({"nodes": [{"attributes": attributes}]})
        url = ApiClass.api_url + '/omnia/nodes/{}'.format(node_id)

        resp_status, resp = self.api_call("PUT", url, payload=payload)
        return resp_status, resp


class BulbObject(ApiClass):
    """ Class for managing bulb objects
    """
    def __init__(self, bulb_name):
        super().__init__()

        self.node_name = bulb_name
        resp_status, resp = self.get_node(self.node_name)
        if resp_status:
            self.node_id = resp['id']
        else:
            LOGGER.error("ERROR: Node ID was not found")
            LOGGER.error("node_name = {}".format(self.node_name))
            LOGGER.error(resp)
            sys.exit()

        # If the bulb is red when we are initialising then likely this means we
        # crashed out and left it red so we make set the alert state now and it
        # will be cleared later if app confirms no alert state
        resp_status, resp = self.bulb_is_red()
        self.alert_active = resp_status and resp

    def set_bulb_red(self):
        """ Turn bulb on and set it to red
        """
        return self.set_attributes(self.node_id,
                                   {"state": "ON",
                                    "brightness": 50,
                                    "hsvHue": 0}
                                   )

    def set_bulb_white_off(self):
        """ Turn bulb off and reset to white
        """
        return self.set_attributes(self.node_id,
                                   {"state": "OFF",
                                    "colourTemperature": 2700})

    def get_bulb_state(self):
        """ Return bulb state
        """
        resp_status, resp = self.get_node(self.node_name)

        on_off_state = None
        colour_mode = None
        colour = None
        brightness = None

        if resp_status:
            try:
                on_off_state = resp['attributes']['state']['reportedValue']
                colour_mode = resp['attributes']['colourMode']['reportedValue']
                colour = resp['attributes']['hsvHue']['reportedValue']
                brightness = resp['attributes']['brightness']['reportedValue']
            except KeyError:
                resp_status = False

        resp = (on_off_state,
                colour_mode,
                colour,
                brightness)

        return resp_status, resp

    def set_bulb_state(self, on_off_state, colour_mode, colour, brightness):
        """ Set the given state
        """
        if colour_mode == "COLOUR":
            resp_status, resp = self.set_attributes(self.node_id,
                                                    {"hsvHue": colour,
                                                     "brightness": brightness,
                                                     "state": on_off_state})
        else:
            resp_status, resp = self.set_attributes(self.node_id,
                                                    {"colourTemperature": 2700,
                                                     "brightness": brightness,
                                                     'state': on_off_state})
        return resp_status, resp

    def bulb_is_red(self):
        """ Return True if bulb is on red, and brightness=50
        """
        resp_status, resp = self.get_node(self.node_name)

        if resp_status:
            try:
                state = resp['attributes']['state']['reportedValue']
                colour_mode = resp['attributes']['colourMode']['reportedValue']
                colour = resp['attributes']['hsvHue']['reportedValue']
                brightness = resp['attributes']['brightness']['reportedValue']

                resp = (state == "ON" and
                        colour_mode == "COLOUR" and
                        colour == 0 and
                        brightness == 50.0)
            except KeyError:
                resp_status = False

        return resp_status, resp


class Group(ApiClass):
    """ Class for managing a group of devices """
    def __init__(self, device_name_list):
        super().__init__()

        self.node_names = device_name_list
        self.node_ids = {node_name: None for node_name in self.node_names}

        for node in self.node_names:
            resp_status, resp = self.get_node(node)
            if resp_status:
                # self.node_id = resp['id']
                self.node_ids[node] = resp['id']
            else:
                LOGGER.error("ERROR: Node ID was not found")
                LOGGER.error("node_name = {}".format(node))
                LOGGER.error(resp)
                sys.exit()

    def get_state(self):
        """ Get the group state
            If any single device is present and ON then whole group in classed
            as ON.
        """
        state = False
        resp_status, resp = self.get_nodes()
        if resp_status:
            for node in resp.json()['nodes']:
                if node['id'] in self.node_ids.values():
                    presence = node['attributes']['presence']['reportedValue']
                    on_off = node['attributes']['state']['reportedValue']

                    if presence == 'PRESENT' and on_off == 'ON':
                        state = True
        return state

    def toggle(self):
        """ Toggle the group state on/off
        """
        if self.get_state():
            LOGGER.info("Turning group off")
            self.group_off()
        else:
            LOGGER.info("Turning group on")
            self.group_on()

    def group_on(self):
        """ Turn group on """
        for node_id in self.node_ids.values():
            self.set_attributes(node_id, {'state': 'ON'})

    def group_off(self):
        """ Turn goup off """
        for node_id in self.node_ids.values():
            self.set_attributes(node_id, {'state': 'OFF'})


def log_bulb_state(colour_bulb):
    """ Gets and Returns the bulb state
    """
    resp_status, resp = colour_bulb.get_bulb_state()
    LOGGER.info("BULB STATE = %s, %s", resp_status, resp)
    return resp_status, resp


def bulb_tests(colour_bulb, sitt_group):
    """ Test some bulb api calls
    """

    # Turn the sitt-group on then off
    LOGGER.info("Turning the sitting room group on...")
    sitt_group.group_on()
    time.sleep(5)
    LOGGER.info("Turning the sitting room group off...")
    sitt_group.group_off()

    # Get original state
    LOGGER.info("Getting original bulb state...")
    _, original_state = log_bulb_state(colour_bulb)

    delay = 10

    # Set bulb on/white
    LOGGER.info("Turning bulb on/white...")
    colour_bulb.set_bulb_state("ON", "TUNABLE", 0, 50)
    time.sleep(delay)
    _, bulb_state = log_bulb_state(colour_bulb)
    assert bulb_state == ('ON', 'TUNABLE', 0, 50.0)

    # Set bulb on/red
    LOGGER.info("Turning bulb on/red...")
    colour_bulb.set_bulb_red()
    time.sleep(delay)
    _, bulb_state = log_bulb_state(colour_bulb)
    # logString = "BULB IS RED = {}".format(colour_bulb.bulb_is_red())
    LOGGER.info("BULB IS RED = %s", colour_bulb.bulb_is_red())
    assert bulb_state == ('ON', 'COLOUR', 0, 50.0)

    # Set bulb off/white
    LOGGER.info("Turning bulb off/white...")
    colour_bulb.set_bulb_white_off()
    time.sleep(delay)
    _, bulb_state = log_bulb_state(colour_bulb)
    assert bulb_state == ('OFF', 'TUNABLE', 0, 50.0)

    # Return to orignial state
    LOGGER.info("Resetting bulb to original state...")
    colour_bulb.set_bulb_state(*original_state)
    time.sleep(delay)
    _, bulb_state = log_bulb_state(colour_bulb)
    assert bulb_state == original_state


def main():
    """ Main Program
    """
    LOGGER.info("Initialising the colour bulb and sitt-group objects...")
    colour_bulb = BulbObject(config.INDICATOR_BULB)
    sitt_group = Group(config.SITT_GROUP)

    for _ in range(5):
        sitt_group.toggle()
        time.sleep(5)

    bulb_tests(colour_bulb, sitt_group)

    print(colour_bulb.set_bulb_white_off())
    time.sleep(30 * 60)
    print(colour_bulb.set_bulb_red())

    LOGGER.info('All done')


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
