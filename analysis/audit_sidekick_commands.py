#!/usr/bin/env python3
"""Verify the official Sidekick APCS/AOCS UI method bytes offline.

Requires a local copy of OSD Sidekick 1.21.0707.1. The executable is not
redistributed by this repository; this script performs no device I/O.
"""

import argparse
from hashlib import sha256
from pathlib import Path


EXPECTED_SHA256 = "a384156924593d88d6c32c141db5b6858923a927ac82971858888a719e42dac0"
APCS_OFFSET = 0x2A34
AOCS_OFFSET = 0x2A70


def audit(executable: Path) -> None:
    blob = executable.read_bytes()
    digest = sha256(blob).hexdigest()
    assert digest == EXPECTED_SHA256, f"Unexpected Sidekick SHA-256: {digest}"

    # Each method is a 12-byte fat method header followed by 47 bytes of IL.
    # Both click handlers read the same field (token 04000055) at IL_0001,
    # then build the SetOSD request with byte argument 0x80/0x82.
    common = bytes.fromhex(
        "13 30 03 00 2f 00 00 00 13 00 00 11 "
        "02 7b 55 00 00 04 17 2e 01 2a 1f 0a 8d a5 00 00 "
        "01 0a 06 16 20 e0 00 00 00 9c 06 17 20"
    )
    suffix = bytes.fromhex("00 00 00 9c 06 18 18 9c 02 19 06 28 82 00")

    for name, offset, selector in (
        ("APCS", APCS_OFFSET, 0x80),
        ("AOCS", AOCS_OFFSET, 0x82),
    ):
        expected = common + bytes([selector]) + suffix
        assert blob[offset:offset + len(expected)] == expected, (
            f"{name}: click handler changed at file offset 0x{offset:X}"
        )
        # Check native Realtek HID frame checksum from the decoded command.
        message = [0x51, 0x85, 0x03, 0xE0, selector, 0x00, 0x02]
        checksum = 0
        for byte in message:
            checksum ^= byte
        print(f"PASS {name}: UI byte selector {selector:02X}; Realtek HID "
              f"prefix {bytes(message + [checksum]).hex(' ')}")

    print("PASS: installed Sidekick executable hash and IL click handlers")
    print("LIMIT: method bytes alone do not prove device execution or transport")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="path to official osdsidekick.exe")
    args = parser.parse_args()
    audit(args.executable)
