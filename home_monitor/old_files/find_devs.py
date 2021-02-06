#!/usr/bin/env python3
"""
Keith Gough 07/10/2020

Discover all devices of given types on the ZigBee network.
Use the cluster discover and read the simple descriptor to get the dev type.
Discover the EUI for each device
Allow user the name the device

"""

import zigbeetools.threaded_serial as at

def find_plugs():
    """ Find all my plugs """
    pass


def disc_on_off_devs(device_type_list):
    """ Discover all devices that support on/off cluster
        Get threaded_serialr simple descriptors 

    """
    at.disc_clusters



def main():
    """ Main program  """
    port = '/dev/tty.SLAB_USBtoUART'
    baud = 115200

    # Discover devices that have the on/off cluster.
