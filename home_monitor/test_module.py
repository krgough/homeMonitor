#!/usr/bin/env python3
'''
Created on 21 Feb 2021

@author: keithgough
'''

import logging
from collections import namedtuple

LOGGER = logging.getLogger(__name__)
BindObj = namedtuple('Bind', ['src_addr', 'src_ep', 'cluster', 'dst_addr', 'dst_ep'])


class Bulb():
    """ Class to control a Zigbee bulb """

    def __init__(self, node_id):
        self.node_id = node_id
        self.state = 'OFF'
        self.color = 'WHITE'

    def set_state(self, state, color):
        """ Set the state of the bulb """
        self.state = state
        self.color = color
        LOGGER.info("Bulb %s set to %s, %s", self.node_id, self.state, self.color)


def main():
    """ Main Program """

    my_bind = BindObj(
        src_addr="00124B00160561DE",
        src_ep="01",
        cluster="Power Configuration Cluster",
        dst_addr="0000",
        dst_ep="01"
    )

    another_bind = BindObj(
        src_addr="00124B00160561DE",
        src_ep="01",
        cluster="On/Off Cluster",
        dst_addr="0000",
        dst_ep="01"
    )

    print(f"Binding created: {my_bind}")
    print(f"Binding created: {another_bind}")
    print(f"Binding created: {my_bind}")

    v2_bind = BindObj(
        src_addr="00124B00160561DE",
        src_ep="01",
        cluster="On/Off Cluster",
        dst_addr="0000"
    )
    print(f"Binding created: {v2_bind}")
    exit()



    my_bulb = Bulb("00124B00160561DE")
    events = [
        {"event_name": "BIT FAT FRIDAY", "func": my_bulb.set_state, "args": ["ON", "RED"]},
        {"event_name": "BIT FAT SATURDAY", "func": my_bulb.set_state, "args": ["OFF", "WHITE"]},
    ]

    for event in events:
        event["func"](*event["args"])


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
