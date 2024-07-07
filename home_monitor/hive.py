#!/usr/bin/env python3
"""

Hive Api - Get and set device parameters using the Hive API

We need to resgister a device with Hive/cognito to get the device
credentials so we can make api calls.  This is done by logging in with 2FA
and then registering a device. he device credentials are saved to a file and
used to request tokens - we then have a set of ephemeral tokens that can be
used to make api calls.

Device credentials are saved to `.device_creds.json`
We can register and de-register devices using this script.
When we register a device a one time MFA code is sent via sms to the
registered mobile phone.  We use this code to complete the registration.

See some details from these sites:
https://jedkirby.com/blog/hive-home-rest-api
https://github.com/Pyhass/Pyhiveapi/blob/master/pyhiveapi/apyhiveapi/api/hive_api.py


# Plug Off
https://beekeeper-uk.hivehome.com/1.0/nodes/activeplug/61a8564c-1035-476a-9b46-3411cf75a0a2

headers - authorisation: token
data = {"status": "OFF"}

"""

import json
import logging
import sys
import os
from collections import namedtuple
import time
from textwrap import dedent
import urllib3

import dotenv
import pyquery
import requests
from tabulate import tabulate

import hive_auth as HiveAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
LOGGER = logging.getLogger(__name__)

DEVICE_CREDS_FILE = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), ".device_creds.json")
DEVICE_ID = "Traindcator9000"

URLS = {
    "properties": "https://sso.hivehome.com/",
    "base": "https://beekeeper-uk.hivehome.com/1.0",
    "devices": "/devices",
    "all": "all?products=true&devices=true&actions=true",
    "admin_login": "https://beekeeper.hivehome.com/1.0/global/admin-login",
    "activeplug": "activeplug/{}",
    "test_plug": "https://beekeeper-uk.hivehome.com/1.0/nodes/activeplug/{}",
}

SITT_REAR_PLUG_ID = "61a8564c-1035-476a-9b46-3411cf75a0a2"

dotenv.load_dotenv()

# Load the env vars
AUTH_DATA = {
    "HIVE_USERNAME": None,
    "HIVE_PASSWORD": None,
}

for env in AUTH_DATA:
    env_value = os.environ.get(env)
    if env_value:
        AUTH_DATA.update({env: os.environ.get(env)})
    else:
        LOGGER.error("Environment variable not found: %s", env)
        sys.exit(1)

HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "accept-encoding": "gzip, deflate, br",
}

Resp = namedtuple("Resp", ["resp", "error"])

PRODUCT_FIELDS = {
    "name": ["state", "name"],
    "status": ["state", "status"],
    "id": ["id"],
    "type": ["type"],
    "online": ["props", "online"],
    "model": ["props", "model"],
    "firmware": ["props", "upgrade", "version"],
}

DEVICE_FIELDS = {
    "name": ["state", "name"],
    "state": ["props", "state"],
    "id": ["id"],
    "type": ["type"],
}

HOME_FIELDS = {
    "name": ["name"],
    "id": ["id"],
}


class ApiError(Exception):
    """Error from Hive API"""


def get_login_info():
    """Get login properties to make the login request."""
    data = requests.get(url=URLS['properties'], verify=False, timeout=60)
    html = pyquery.PyQuery(data.content)
    json_data = json.loads(
        '{"'
        + (html("script:first").text())
        .replace(",", ', "')
        .replace("=", '":')
        .replace("window.", "")
        + "}"
    )

    login_data = {
        "UPID": json_data["HiveSSOPoolId"],
        "CLIID": json_data["HiveSSOPublicCognitoClientId"],
        "REGION": json_data["HiveSSOPoolId"],
    }
    return login_data


class CogManager:
    """Class to manage Hive Cognito Authorisation
    Use HiveAuth to create a new device and then save the creds to a file
    Use device login to get tokens with the saved creds - tokens are ephemeral
    so do not need to be saved to a file.
    """

    def __init__(self, auth_data) -> None:

        self.auth_data = auth_data

        self.device_creds = {
            "device_key": None,
            "device_group_key": None,
            "device_password": None
        }

        # Load device creds from a file.  Warns user if no file found.
        self.load_device_creds()

        self.auth = HiveAuth.HiveAuth(
            username=AUTH_DATA["HIVE_USERNAME"],
            password=AUTH_DATA["HIVE_PASSWORD"],
            login_data=get_login_info(),
            device_key=self.device_creds["device_key"],
            device_group_key=self.device_creds["device_group_key"],
            device_password=self.device_creds["device_password"],
        )

        self.tokens = {
            "IdToken": None,
            "AccessToken": None,
            "RefreshToken": None,
        }

    def device_login(self):
        """Login using the registered device credentials"""
        LOGGER.info("Logging in with device credentials...")
        tokens = self.auth.device_login()
        self.tokens.update(tokens["AuthenticationResult"])

    def refresh_auth(self) -> None:
        """Refresh Hive auth token
        Refresh operation only returns a new access_token and id_token but
        no refresh_token.
        """
        LOGGER.info("Refreshing authorisation...")
        tokens = self.auth.refresh_token(token=self.tokens["RefreshToken"])
        self.tokens.update(tokens["AuthenticationResult"])
        LOGGER.debug("Check if a new refresh token is returned...")
        LOGGER.debug(tokens)

    def load_device_creds(self, filename=DEVICE_CREDS_FILE) -> None:
        """Load tokens from the token file"""
        if not os.path.exists(filename):
            LOGGER.error("No token file.  Need to authenticate with 2FA.")
            LOGGER.error("Run hive.py manually to generate tokens")
            raise FileNotFoundError("No token file")

        with open(filename, mode="r", encoding="utf-8") as file:
            self.device_creds.update(json.load(file))


class Account:
    """Class to manage Hive Account"""

    def __init__(self, auth_data) -> None:

        self.cog = CogManager(auth_data=auth_data)
        self.cog.device_login()

        self.user = None
        self.devices = []
        self.products = []
        self.homes = []
        self.update()

    def update(self):
        """Get the current status of all devices"""
        resp = self.get_nodes()
        if not resp.error:
            data = resp.resp.json()

            # Extract 'user' information
            self.user = data.get("user", None)

            # Extract 'devices'
            self.parse_devices(data)

            # Extract 'products'
            self.parse_products(data)

            # Extract 'homes'
            self.parse_homes(data)

        else:
            raise ApiError(f"{resp.error}")

    def api_call(
        self,
        method: str,
        url: str,
        payload=None,
        headers=None,
        expected_response=200,
    ):
        """Make the wanted api call.
        If 401 then our token may have expired so try to refresh
        """
        # pylint: disable=too-many-arguments
        if payload:
            payload = json.dumps(payload)

        if not headers:
            headers = HEADERS
            headers["authorization"] = self.cog.tokens["IdToken"]

        resp = requests.request(
            method=method, url=url, data=payload, headers=headers, timeout=60
        )

        # Refresh tokens and Retry if we got a 401
        if resp.status_code in [401, 500]:
            self.cog.refresh_auth()

            # Update headers with new token
            if headers and "authorization" in headers:
                headers["authorization"] = self.cog.tokens["IdToken"]

            # If POST then we may have a token in the payload
            if payload and "token" in payload:
                payload["token"] = self.cog.tokens["IdToken"]

            resp = requests.request(
                method=method, url=url, data=payload, headers=headers, timeout=60
            )

        # Set the error attribute if resp_code not correct
        if resp.status_code != expected_response:
            msg = f"Unexpected response from {url}"
            LOGGER.error(msg)
            error = msg
        else:
            error = None

        return Resp(resp, error)

    def parse_homes(self, data):
        """Parse homes"""
        # Extract our homes
        try:
            homes = data["homes"]["homes"]
        except KeyError:
            homes = []

        # If the home is not in the list already then append it
        # else update the existing home
        for home in homes:
            new_home = {
                name: parse_entry(home, keys) for (name, keys) in HOME_FIELDS.items()
            }
            update_or_append(self.homes, new_home)

    def parse_devices(self, data):
        """Parse devices from the 'Devices' field
        Note there are also 'Products' and 'User' Fields
        """
        # Extract our devices
        for dev in data.get("devices", []):
            new_dev = {
                name: parse_entry(dev, keys) for (name, keys) in DEVICE_FIELDS.items()
            }
            update_or_append(self.devices, new_dev)

    def parse_products(self, data):
        """Parse products from the 'Products' field
        Note there are also 'Devices' and 'User' fields
        """
        for prod in data.get("products", []):
            new_prod = {
                name: parse_entry(prod, keys) for (name, keys) in PRODUCT_FIELDS.items()
            }
            update_or_append(self.products, new_prod)

    def get_nodes(self, fields=None):
        """Get the specified data for the Hive account"""
        # If no fields specified then get them all
        if not fields:
            fields = ["devices", "products", "user", "homes", "actions"]

        # Build the URL
        query = "=true&".join(fields) + "=true"
        url = f"{URLS['base']}/nodes/all?{query}"

        return self.api_call(method="GET", url=url)

    def admin_login(self) -> list:
        """Get a list of all devices
        This api is used by the website but we can also use GET /devices
        Keeping this for info but not using it
        """
        url = URLS["admin_login"]
        payload = {
            "actions": True,
            "devices": True,
            "homes": False,
            "products": True,
            "token": self.cog.tokens["IdToken"],
        }

        return self.api_call(
            method="POST", url=url, headers=HEADERS, payload=payload
        )

    def set_product_state(self, dev, status="ON"):
        """Turn product on/off"""
        url = f"{URLS['base']}/nodes/{dev['type']}/{dev['id']}"
        return self.api_call(
            method="POST", url=url, payload={"status": status}
        )

    # def get_product_state(self, prod):
    #     """Turn product on/off"""
    #     url = f"{URLS['base']}/nodes/{prod.type}/{prod.id}"
    #     resp = self.api_call(method="GET", url=url)
    #     if not resp.error:

    #         pprint(resp.resp.json())
    #         state = "whatevs"
    #     else:
    #         LOGGER.error(resp)
    #         state = None
    #     return state

    def set_alarm_state(self, home_id, alarm_state="home"):
        """Set alarm state to 'home', 'away', 'sleep'"""
        assert alarm_state in ["home", "away", "sleep"]
        url = f"{URLS['base']}/security-lite?homeId={home_id}"
        return self.api_call(
            method="POST", url=url, payload={"mode": alarm_state}
        )

    def get_alarm_state(self, home_id):
        """Get alarm state"""
        url = f"{URLS['base']}/security-lite?homeId={home_id}"
        resp = self.api_call(method="GET", url=url)
        if not resp.error:
            state = resp.resp.json().get("mode", None)
        else:
            LOGGER.error(resp)
            state = None
        return state

    def __str__(self):
        """Print out the state off all devices"""
        device_table = tabulate(self.devices, headers="keys")
        product_table = tabulate(self.products, headers="keys")
        user_table = tabulate(
            {"item": self.user.keys(), "value": self.user.values()},
            headers=["Field", "Value"],
        )
        homes_table = tabulate(self.homes, headers="keys")

        strings = [
            "\nUser Table", user_table,
            "\nDevice Table", device_table,
            "\nProduct Table", product_table,
            "\nHomes Table", homes_table,
        ]

        return "\n".join(strings)


def parse_entry(node, key_list):
    """Parses the field value from arbitraraly
    deeply nested values in a dictionary
    """
    attr_val = node
    try:
        for key in key_list:
            attr_val = attr_val[key]
        return attr_val
    except KeyError:
        # print('KEY ERROR: {}'.format(e))
        return None


def get_by_name(my_list, name):
    """Find and return the wanted Product"""
    return next((item for item in my_list if item["name"] == name), None)


def get_by_id(my_list, my_id):
    """Find and return the wanted device from list of dicts"""
    return next((item for item in my_list if item["id"] == my_id), None)


def update_or_append(my_list, new_item):
    """Update item in a list or append if it's a new item"""
    old_item = next((item for item in my_list if item["id"] == new_item["id"]), None)
    if old_item:
        old_item.update(new_item)
    else:
        my_list.append(new_item)


def test_get_set_state(acct):
    """Modify the state of a device and confirm it changes"""
    # Find the device
    bulb = get_by_name(acct.products, "Luca Bulb")
    assert bulb is not None

    # Turn the device off
    acct.set_product_state(bulb, status="OFF")
    time.sleep(3)

    # Check device state
    acct.update()
    assert bulb["status"] == "OFF"

    # Turn the device on
    acct.set_product_state(bulb, status="ON")
    time.sleep(3)

    # Check device state
    acct.update()
    assert bulb["status"] == "ON"

    # Leave device turned off
    acct.set_product_state(bulb, status="OFF")


def test_arm_disarm_alarm(acct):
    """Modify the arm/disarm state and confirm it has changed"""
    # Find the device
    keypad = get_by_name(acct.devices, "Hallway Keypad")
    assert keypad is not None

    # Set alarm state
    LOGGER.info("Setting Alarm State to AWAY")
    resp = acct.set_alarm_state(acct.homes[0]["id"], alarm_state="away")
    assert resp.error is None

    # Check the alarm state is "away"
    time.sleep(3)
    acct.update()
    assert keypad["state"] == "FULL_ARMED"
    LOGGER.info("Alarm Sate: %s", keypad["state"])

    # Set alarm state
    LOGGER.info("Setting Alarm State to DISARM")
    resp = acct.set_alarm_state(acct.homes[0]["id"], alarm_state="home")
    assert resp.error is None

    # Check the alarm state is "away"
    time.sleep(3)
    acct.update()
    assert keypad["state"] == "DISARM"
    LOGGER.info("Alarm Sate: %s", keypad["state"])


def list_devices(hive_auth, auth_data):
    """List registered devices"""
    devices = hive_auth.list_devices(auth_data["AuthenticationResult"]["AccessToken"])

    devs = []
    for device in devices['Devices']:
        for attr in device['DeviceAttributes']:
            if attr['Name'] == "device_name":
                dev = attr['Value']
        key = device['DeviceKey']
        devs.append({"Device": dev, "Key": key})

    print(tabulate(devs, headers="keys"))


def registration_menu():
    """Allow user to login with 2FA and create/delete a registered device"""

    print("\nHive 2FA and Device Registration:\n")
    print("This will attempt to authenticate with HIVE cognito using 2FA")
    print("Will require you to enter the MFA code sent by SMS to mobile phone")

    inp = input('Proceed y/n? ')
    if inp.upper() == 'Y':

        hive_auth = HiveAuth.HiveAuth(
            username=AUTH_DATA["HIVE_USERNAME"],
            password=AUTH_DATA["HIVE_PASSWORD"],
            login_data=get_login_info(),
        )

        auth_data = hive_auth.login()

        if auth_data.get("ChallengeName") == "SMS_MFA":
            code = input("Enter your 2FA code: ")
            auth_data = hive_auth.sms_2fa(code, auth_data)

        if "AuthenticationResult" not in auth_data:
            LOGGER.error("No AuthenticationResult in auth_data")
            sys.exit()

        menu = dedent("""
        Menu:
        1. List devices
        2. Forget device
        3. Register device
        x. Exit
        """)

        while True:
            print(menu)
            inp = input("Enter option: ")
            if inp == "1":
                list_devices(hive_auth, auth_data)

            elif inp == "2":
                list_devices(hive_auth, auth_data)
                inp = input("Enter device key to forget: (x to skip) ")
                if inp != "x":
                    result = hive_auth.forget_device(
                        access_token=auth_data["AuthenticationResult"]["AccessToken"],
                        device_key=inp,
                    )
                    print()
                    print(result)

            elif inp == "3":
                print("Enter device name to register")
                inp = input(f"'{DEVICE_ID}' should be used for automation): ")
                hive_auth.device_registration(device_name=inp)
                creds = hive_auth.get_device_data()
                print()
                print(creds)
                print(f"\nSaving device credentials to file: {DEVICE_CREDS_FILE}")
                with open(DEVICE_CREDS_FILE, mode="w", encoding="utf-8") as file:
                    json.dump(creds, file, indent=4)

            else:
                break


def main():
    """Main Prog"""

    menu = dedent("""
        Menu:
        1. Manage device registration with 2FA
        2. Using registered device: login and print the account details
        3. Using registered device: turn a device on/off (Luca Bulb)
        4. Using registered device: arm/disarm alarm (Hallway Keypad)
        x. Exit
    """)

    while True:
        print(menu)
        inp = input("Enter option: ")
        if inp == "1":
            registration_menu()
        elif inp == "2":
            acct = Account(auth_data=AUTH_DATA)
            print(acct)
        elif inp == "3":
            acct = Account(auth_data=AUTH_DATA)
            test_get_set_state(acct)
        elif inp == "4":
            acct = Account(auth_data=AUTH_DATA)
            test_arm_disarm_alarm(acct)
        else:
            break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
    print("All done.")
