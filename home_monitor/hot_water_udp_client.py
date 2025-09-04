#!/usr/bin/env python3

""" UDP Client

Keith Gough, 01/05/2020

Send a Broadcast UDP message and wait for a reply.
This one sends a message to the rpi on my local net asking for the hot water level
as measured from the sensors on the hot water cylinder.

Message:
uwl? = What is the usable water level

Expected Response:
uwl=xx.x%

"""

import socket
import logging
import time

LOGGER = logging.getLogger(__name__)

ADDRESS = ("255.255.255.255", 10000)
UWL_MESSAGE = "uwl?"
UWL_RESP = "uwl="

SOCK_TIMEOUT = 0.5
SOCK_RETRIES = 3  # 20 retries takes too long


def send_with_retries(sock, msg, expected_resp, addr):
    """Send the message with retry attempts if necessary"""
    for attempt in range(SOCK_RETRIES):
        # Send data
        LOGGER.debug("sending %s", msg)
        sock.sendto(msg.encode(), addr)

        # Receive response
        LOGGER.debug("Attempt %s. Waiting to receive...", attempt)

        try:
            data, server = sock.recvfrom(1024)
            if data.decode().startswith(expected_resp):
                data = data.decode()[len(expected_resp):]
        except socket.timeout:
            data = None
            server = None

        if data:
            return data, server
    return None, None


def send_cmd(msg, expected_resp, addr):
    """Send UDP message and wait for the expected response"""
    # Create a UDP socket
    # Setup to use the broadcast address
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # Set the timeout
    sock.settimeout(SOCK_TIMEOUT)
    LOGGER.debug("Socket timeout set to %s", sock.gettimeout())
    LOGGER.debug("socket using address: %s", ADDRESS)

    # Send the command
    data, server = send_with_retries(sock, msg, expected_resp, addr)

    LOGGER.debug("received '%s', from %s", data, server)
    LOGGER.debug("closing socket")
    sock.close()
    return data


def test_client():
    """Count how many attempts before no reply"""
    count = 0
    while count < 100:
        data = send_cmd(UWL_MESSAGE, UWL_RESP, ADDRESS)
        LOGGER.debug("Count = %s", count)
        time.sleep(0.5)
        count += 1
        if not data:
            break

    LOGGER.debug("Test stopped at count = %s", count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    send_cmd(UWL_MESSAGE, UWL_RESP, ADDRESS)
    # test_client()
