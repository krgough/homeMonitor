
"""

Pair the device manually using the command line.  at+pjoin:ff
Grab the EUI of the device, then use this script to set the cicie

"""

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import time
import sys
import logging

from textwrap import dedent

from zigbeetools import threaded_serial as at_cmd
from zigbeetools import zigbee_clusters as zcl


# SIREN_EP_ID = '01'

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

    # node_id = None
    # port = None
    # baud = 115200

    # opts = getopt.getopt(sys.argv[1:], "hn:p:b:")[0]

    # for opt, arg in opts:
    #     # print(opt, arg)
    #     if opt == '-h':
    #         print(help_string)
    #         sys.exit()
    #     if opt == '-n':
    #         node_id = arg
    #     if opt == '-p':
    #         port = arg
    #     if opt == '-b':
    #         baud = arg

    # if not node_id:
    #     print("Error: Node ID (DUT) was not specified")
    #     print(help_string)
    #     sys.exit(1)

    # if not port:
    #     print("ERROR: port was not specified")
    #     sys.exit(1)

    # return node_id, port, baud


def get_node_eui(node_id):
    """ Get the device EUI
    """
    resp_state, resp_code, resp = at_cmd.get_eui(node_id, node_id)
    if resp_state and resp_code == zcl.STATUS_CODES['SUCCESS']:
        eui = resp
    else:
        print("EUI not found")
        print(resp)
        sys.exit()
    return eui


def active_endpoint_request(node_id):
    """  Get the device endpoints """
    resp_state, resp_code, endpoints = at_cmd.disc_endpoints(node_id)
    if resp_state and resp_code == zcl.STATUS_CODES['SUCCESS']:
        print(f"Endpoints: {endpoints}")
    else:
        print('Error finding endpoints')
        sys.exit()
    return endpoints


def simple_descriptor_request(node_id, ep_id):
    """ Send simple descriptor request """
    node = at_cmd.NodeObj(node_id, ep_id, manuf_id=None)
    resp_state, resp_code, resp_value = at_cmd.get_simple_desc(node)
    if resp_state and resp_code == zcl.STATUS_CODES['SUCCESS']:
        print(f"\nSimple Descriptor, Endpoint={ep_id}:")
        for field in ['ProfileID', 'DeviceID', 'InCluster', 'OutCluster']:
            if field == 'DeviceID':
                device_type = zcl.get_device_type(resp_value[field])
                if device_type is None:
                    print("DEVICE TYPE NOT LISTED IN ZCL. {resp_value[field]}")
                else:
                    print(f"{field:10} = {resp_value[field]}. {device_type}")
            else:
                print(f"{field:10} = {resp_value[field]}")

    else:
        print(f"get_simple_desc Error: {resp_value}")
        sys.exit()


def node_descriptor_request(node_id):
    """ Send node descriptor request
    """
    resp_state, resp_code, resp_value = at_cmd.get_node_desc(node_id, node_id)
    if resp_state and resp_code == zcl.STATUS_CODES['SUCCESS']:
        print(resp_value)
        print(f"\nNode type = {resp_value['type']}, Manufacturer Id = {resp_value['manId']}")
    else:
        print(resp_value)
        sys.exit()


def hex_str(value, digits=2):
    """ Convert to a hex string """
    return f"{value:0{digits}x}"


def flush_queue(my_queue):
    """ Flush the given Queue """
    while not my_queue.empty():
        my_queue.get()


def initialise_siren(node_id):
    """ Send a list of messages """
    # Get the EUIs for the co-ordinator and the device under test
    coo_eui = get_node_eui("0000")
    print("Coordinator EUI: ", coo_eui)
    if coo_eui is None:
        print("Co-ordinator EUI was not found")
        sys.exit()

    dev_eui = get_node_eui(node_id)
    print("Device EUI: ", dev_eui)
    if dev_eui is None:
        print("Device EUI was not found")
        sys.exit()

    # Active endpoint request
    # Get all the endpoints
    endpoints = active_endpoint_request(node_id)
    print("EndPoints: ", endpoints)

    # Get the simple descriptors
    for endpoint in endpoints:
        simple_descriptor_request(node_id, endpoint)

    # Get Node description
    node_descriptor_request(node_id)

    # Messages to be sent
    # Set EUI of CICIE
    set_cicie = f"at+writeatr:{node_id},01,0,0500,0010,F0,{coo_eui}"
    # setPolBinding = "at+bind:{},3,{},01,0020,{},01".format(node_id,
    #                                                        dev_eui,
    #                                                        coo_eui)

    # Setup poll control so we get checkIns
    # Set a binding and set the checkIn interval to 5mins
    # setPolBinding = "at+bind:{},3,{},01,0020,{},01".format(node_id,
    #                                                        dev_eui,
    #                                                        coo_eui)
    # setCiInt = "at+writeatr:{},01,0,0020,0000,23,000004B0".format(node_id)

    # Set a binding on the IAS ACE cluster - not required to get it working
    # setIasAceBinding = "at+bind:{},3,{},01,0501,{},01".format(node_id,
    #                                                           dev_eui,
    #                                                           coo_eui)

    # Send the intial setup messages
    # cmd_list = [set_cicie, setPolBinding, setCiInt ] #, setIasAceBinding]
    cmd_list = [set_cicie]

    for cmd in cmd_list:
        print(cmd)
        at_cmd.TX_QUEUE.put(cmd)
        time.sleep(1)


def siren(node_id, initialise):
    """ Send messages to the device and log the resposnses """
    if initialise:
        initialise_siren(node_id)

    # Respond to commands from siren
    flush_queue(at_cmd.RX_QUEUE)

    while True:
        if not at_cmd.RX_QUEUE.empty():
            msg = at_cmd.RX_QUEUE.get()
            print(msg)

        time.sleep(0.1)


def get_siren_node_id():
    """ Open the network to allow the siren to join """

    # Open the network to allow the siren to join
    at_cmd.pjoin(duration=120)

    # Wait for a device to join and get the node ID
    result = at_cmd.wait_for_message(msgs=["FFD:"], timeout=120)
    if result:
        node_id = result.split(",")[1]
    else:
        node_id = None
    return node_id


def main():
    """ Main program """

    args = get_args()
    node_id = args.node_id
    port = args.port
    baud = args.baud

    # Turn on debugging so we see message logging on the console
    at_cmd.DEBUG = True

    # Start the serial port Rx and Tx threads
    at_cmd.start_serial_threads(port, baud, print_status=True, rx_q=True)

    if not node_id:
        node_id = get_siren_node_id()

    if node_id:
        print(f"NodeId = {node_id}")
    else:
        print("No Node ID found.  Exiting.")
        return

    # Queue up and send the setup messages
    siren(node_id, initialise=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
