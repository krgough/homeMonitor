#!/usr/bin/env python3
'''
Convert a signed hex number to decimal

'''

import sys


def convert_s16(hex_value):
    """ Convert a 16bit signed hex value to decimal
    """
    return -(hex_value & 0x8000) | (hex_value & 0x7fff)


if __name__ == "__main__":
    try:
    	print(convert_s16(int(sys.argv[1], 16)))
    except IndexError:
        print("No hex number provided")

