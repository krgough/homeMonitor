
"""

Pair the device manually using the command line.  at+pjoin:ff
Grab the EUI of the device, then use this script to set the cicie

"""

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import sys
import logging
from typing import Literal, Optional

from textwrap import dedent

from zigbeetools import threaded_serial as at
from zigbeetools import zigbee_clusters as zcl


LOGGER = logging.getLogger(__name__)


def get_args():
    """ Read command line parameters
    """

    parser = ArgumentParser(
        description=dedent("""
            Siren Setup Tool

            To setup the siren we need to know the Node ID.
            We then write the CICIE EUI to the device and set up the bindings and check-in interval.
        """),
        formatter_class=RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '-d', '--device', choices=['siren', 'wds'], required=True,
        help='Device type to pair.'
    )

    parser.add_argument(
        '-n', metavar="node_id", dest="node_id",
        help='Device Node Id (DUT).  If not provided we open the network and wait for a device to join'
    )
    parser.add_argument(
        '-p', metavar='port', dest="port",
        required=True,
        help='Serial port e.g. /dev/tty.xxxx'
    )
    parser.add_argument(
        '-b', metavar='baud', dest="baud",
        default=115200, type=int,
        help='Baud rate (default is 115200)'
    )
    return parser.parse_args()


def print_simple_descriptor(sd_resp_value, ep_id):
    """ Print simple descriptor response """
    print(f"\nSimple Descriptor, Endpoint={ep_id}:")
    for field in ['ProfileID', 'DeviceID', 'InCluster', 'OutCluster']:
        if field == 'DeviceID':
            device_type = zcl.get_device_type(sd_resp_value[field])
            if device_type is None:
                print(f"DEVICE TYPE NOT LISTED IN ZCL. {sd_resp_value[field]}")
            else:
                print(f"{field:10} = {sd_resp_value[field]}. {device_type}")
        else:
            print(f"{field:10} = {sd_resp_value[field]}")


# def hex_str(value, digits=2):
#     """ Convert to a hex string """
#     return f"{value:0{digits}x}"


# def flush_queue(my_queue):
#     """ Flush the given Queue """
#     while not my_queue.empty():
#         my_queue.get()


def wds_pairing(coordinator: at.ZigbeeDevice, node_id):
    """ Pair the WDS device with the coordinator """
    # Get the EUIs for the co-ordinator and the device under test
    resp_state, resp_code, resp = coordinator.at_cmds.get_eui("0000", "0000")
    if resp_state:
        coo_eui = resp
        print(f"Coordinator EUI: {coo_eui}")
    else:
        print("Coordinator EUI not found")
        sys.exit()

    resp_state, resp_code, resp = coordinator.at_cmds.get_eui(node_id, node_id)
    if resp_state:
        dev_eui = resp
        print(f"Device EUI: {dev_eui}")
    else:
        print("Device EUI was not found")
        sys.exit()

    # Set a binding on the power control cluster so we can get the battery level
    binding = at.bind_object(
        src_addr=dev_eui,
        src_ep="06",
        cluster="Power Configuration Cluster",
        dst_addr=coo_eui,
        dst_ep="01"
    )
    resp_state, resp_code, resp_value = coordinator.at_cmds.set_binding(node_id=node_id, binding=binding)

    # Set an attribute report configiration to get the battery voltage every 20mins
    node = at.NodeObj(node_id, "06", manuf_id=None)
    pc_cluster = at.cluster_object("Power Configuration Cluster")
    bv_attribute = at.attribute_object(
        clust_id=pc_cluster.id,
        attr_id=zcl.get_attribute_name_and_id("Power Configuration Cluster", "batteryVoltage")[0]
    )
    bv_report = at.report_object(min_rep='0001', max_rep=f'{20*60:04x}', change_rep='01')
    resp_state, resp_code, resp_value = coordinator.at_cmds.set_attribute_reporting(
        node=node,
        cluster=pc_cluster,
        attribute=bv_attribute,
        report=bv_report
    )
    if not resp_state or resp_code != zcl.STATUS_CODES['SUCCESS']:
        print(f"Error setting attribute reporting: {resp_value}")
        sys.exit()
    else:
        print("Battery voltage reporting set successfully")

    # Set check-in interval to 20mins
    pc_clust = at.cluster_object("Poll Control Cluster", "server")
    ci_attr = at.attribute_object(
        clust_id="Poll Control Cluster",
        attr_id="checkInInterval",
        value=f'{20*60:04x}'
    )
    resp_state, resp_code, resp_value = coordinator.at_cmds.set_attribute(
        node=node,
        cluster=pc_clust,
        attribute=ci_attr
    )
    if not resp_state or resp_code != zcl.STATUS_CODES['SUCCESS']:
        print(f"Error setting check-in interval: {resp_value}")
        sys.exit()
    else:
        print("Check-in interval set successfully.")

    # Set binding on the poll control cluster
    binding = at.bind_object(
        src_addr=dev_eui,
        src_ep="06",
        cluster="Poll Control Cluster",
        dst_addr=coo_eui,
        dst_ep="01"
    )
    resp_state, resp_code, resp_value = coordinator.at_cmds.set_binding(node_id=node_id, binding=binding)

    print("WDS device paired successfully.")


def siren_pairing(coordinator: at.ZigbeeDevice, node_id):
    """ Send a list of messages """
    # Get the EUIs for the co-ordinator and the device under test
    resp_state, resp_code, resp = coordinator.at_cmds.get_eui("0000", "0000")
    if resp_state:
        coo_eui = resp
    else:
        print("Coordinator EUI not found")
        sys.exit()

    resp_state, resp_code, resp = coordinator.at_cmds.get_eui(node_id, node_id)
    if resp_state:
        dev_eui = resp
        print(f"Device EUI: {dev_eui}")
    else:
        print("Device EUI was not found")
        sys.exit()

    # Get all the endpoints
    resp_state, resp_code, resp = coordinator.at_cmds.disc_endpoints(node_id)
    if resp_state:
        endpoints = resp
        print("EndPoints: ", endpoints)
    else:
        print("Error finding endpoints")
        sys.exit()

    # Get the simple descriptors
    for endpoint in endpoints:
        node = at.NodeObj(node_id, endpoint, manuf_id=None)
        resp_state, resp_code, resp_value = coordinator.at_cmds.get_simple_desc(node=node)
        if resp_state:
            print_simple_descriptor(resp_value, endpoint)
        else:
            print(f"Error getting simple descriptor for endpoint {endpoint}: {resp_value}")
            sys.exit()

    # Get Node description
    resp_state, resp_code, resp_value = coordinator.at_cmds.get_node_desc(node_id, node_id)
    if resp_state and resp_code == zcl.STATUS_CODES['SUCCESS']:
        print(resp_value)
        print(f"\nNode type = {resp_value['type']}, Manufacturer Id = {resp_value['manId']}")
    else:
        print(resp_value)
        sys.exit()

    # Set a binding on poll control and set the checkIn interval to 5mins
    # "at+bind:{},3,{},01,0020,{},01".format(node_id, dev_eui, coo_eui)
    # "at+writeatr:{},01,0,0020,0000,23,000004B0".format(node_id)

    # Set a binding on the IAS ACE cluster - not required to get it working
    # "at+bind:{},3,{},01,0501,{},01".format(node_id, dev_eui, coo_eui)

    # Set the cicie eui - This is required to get it working
    # f"at+writeatr:{node_id},01,0,0500,0010,F0,{coo_eui}"
    resp_state, resp_code, resp_value = coordinator.at_cmds.set_atr(
        clust_id=zcl.get_cluster_name_and_id("IAS Zone Cluster")[0],
        attr_id=zcl.get_attribute_name_and_id("IAS Zone Cluster", "CIE Address")[0],
        value=coo_eui
    )
    if not resp_state or resp_code != zcl.STATUS_CODES['SUCCESS']:
        print(f"Error setting CIE EUI: {resp_value}")
        sys.exit()

    print("CIE EUI set successfully.")


def get_node_id(coordinator:  at.ZigbeeDevice, dev_type: Literal["FFD", "SED"]) -> Optional[str]:
    """ Open the network to allow the device to join and get the node id of the joining device """

    # Open the network
    coordinator.at_cmds.pjoin(duration=120)

    # Wait for a device to join and get the node ID
    result = coordinator.wait_for_message(msgs=[f"{dev_type}:"], timeout=120)
    if result:
        node_id = result.split(",")[1]
    else:
        node_id = None
    return node_id


def main():
    """ Main program """

    args = get_args()
    if args.device == "siren":
        args.dev_type = "FFD"
    else:
        args.dev_type = "SED"

    # Start the serial port Rx and Tx threads
    coordinator = at.ZigbeeDevice(name="zb_home", port=args.port, baud=args.baud)

    if not args.node_id:
        node_id = get_node_id(coordinator=coordinator, dev_type=args.dev_type)
    else:
        node_id = None

    if node_id:
        print(f"NodeId = {node_id}")
    else:
        print("No Node ID found.  Exiting.")
        return

    if args.device == 'siren':
        siren_pairing(coordinator=coordinator, node_id=node_id)
    elif args.device == 'wds':
        wds_pairing(coordinator=coordinator, node_id=node_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
