#!/usr/bin/env python3
"""Verify distinct CFDA packet dispatch families in unmodified FO48U F08.

Literal 8051 bytecode assertions only. These do not determine the physical
transport, packet provenance, write origins, or command authorization.
"""

from hashlib import md5

from build_custom import file_offset, load_source

STOCK_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"

# CFDA is interpreted by multiple bank-local dispatchers.
EVIDENCE = (
    ("bank 7: C0/D0 packet family", 7, 0x6945,
     "90 CF DA E0 FF 64 C0 60 07 EF 64 D0 60 02 C3 22"),
    ("bank 10: 77/AA branch, CFD8=71", 10, 0xF801,
     "90 CF D8 E0 64 71 70 45 90 CF DA E0 FF B4 77 03 A3 80 07 EF B4 AA 0A 90 CF DA E0 90 C5 00 F0"),
    ("bank 12: CFDB=E0 then CFDA=01", 12, 0x53FC,
     "90 CF DB E0 FF 64 E0 60 02 C3 22 90 CF DA E0 64 01"),
    ("bank 12: CFDA=03 alternate path", 12, 0x5D73,
     "90 CF DA E0 64 03 60 03 02 68 D1"),
    ("bank 18: 03/07/0C/F3/01 opcode dispatch", 18, 0xD6D3,
     "90 CF DA E0 24 FD 60 15 24 FC 60 16 24 FB 60 2C 24 19 60 1B 24 F2 70 21"),
    ("bank 7: CFDB..CFDE copied to response buffer", 7, 0xB226,
     "90 CF DB E0 90 CF 84 F0 90 CF DC E0 90 CF 85 F0 90 CF DD E0 90 CF 86 F0 90 CF DE E0 90 CF 87 F0"),
    ("bank 12: APCS operand ==02 guard", 12, 0x68A9,
     "90 CF DE E0 64 02 70 23 90 D1 2D E0 44 01"),
    ("bank 12: AOCS operand ==02 guard", 12, 0x68B9,
     "90 CF DE E0 B4 02 14 90 D1 2D E0 44 02"),
)


def audit() -> list[str]:
    image = bytes(load_source())
    assert md5(image).hexdigest() == STOCK_MD5, "Expected verified stock F08"
    labels = []
    for label, bank, address, opcode_hex in EVIDENCE:
        expected = bytes.fromhex(opcode_hex)
        offset = file_offset(bank, address)
        actual = image[offset:offset + len(expected)]
        assert actual == expected, (
            f"{bank}:{address:04X} {label}: "
            f"expected {expected.hex(' ')}, got {actual.hex(' ')}"
        )
        labels.append(label)
    return labels


if __name__ == "__main__":
    for entry in audit():
        print("PASS:", entry)
    print("CFDA is shared across packet families. Ingress and transport remain unproven.")
    print("Read-only stock bytecode audit; no commands sent to the monitor.")
