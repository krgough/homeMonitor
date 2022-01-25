#!/usr/bin/env python3
"""
Convert a signed hex number to decimal

"""

import sys


def convert_s16(hex_value):
    """Convert a 16bit signed hex value to decimal"""
    h_val = int(hex_value, 16)
    return -(h_val & 0x8000) | (h_val & 0x7fff)


if __name__ == "__main__":
    try:
        print(convert_s16(sys.argv[1]))
    except IndexError:
        print("No hex number provided")
