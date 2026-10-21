#!/usr/bin/env python3
"""Audit upstream C68A/D83C -> D8FE paths in hash-identified stock FO48U F08.

Run: python -B analysis/audit_d8fe_upstream.py

All code addresses are DECIMAL bank:HEX bank-relative address. File offsets
are bank * 0x10000 + address; C68A, D83C, D180 and D8FE are XDATA addresses.
This is a read-only, byte-level audit, not a runtime reachability test.
"""

from hashlib import sha256
from pathlib import Path


FIRMWARE = (
    Path(__file__).resolve().parent.parent
    / "firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin"
)
EXPECTED_SIZE = 2_031_616
EXPECTED_SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
CODE_BANKS = range(20)


def check(data: bytes, bank: int, address: int, hex_bytes: str, meaning: str) -> None:
    expected = bytes.fromhex(hex_bytes)
    offset = bank * 0x10000 + address
    actual = data[offset:offset + len(expected)]
    if actual != expected:
        raise AssertionError(
            f"{bank}:{address:04X}, file 0x{offset:06X}: "
            f"observed {actual.hex(' ')}, expected {expected.hex(' ')}"
        )
    print(f"  {bank}:{address:04X} file 0x{offset:06X} "
          f"[{expected.hex(' ')}] {meaning}")


def check_group(data: bytes, title: str, checks: tuple[tuple[int, int, str, str], ...]) -> None:
    print(title)
    for bank, address, hex_bytes, meaning in checks:
        check(data, bank, address, hex_bytes, meaning)


def literal_dptr_references(data: bytes, xdata: int) -> list[tuple[int, int]]:
    """Find only contiguous MOV DPTR,#xdata byte literals in code banks 0..19.

    Matches may fall in tables or embedded data. Indirect DPTR writes, writes
    after DPTR arithmetic, and dynamic execution are outside this search.
    """
    needle = bytes((0x90, xdata >> 8, xdata & 0xFF))
    found = []
    for bank in CODE_BANKS:
        segment = data[bank * 0x10000:(bank + 1) * 0x10000]
        index = 0
        while (position := segment.find(needle, index)) != -1:
            found.append((bank, position))
            index = position + 1
    return found


def audit() -> None:
    data = FIRMWARE.read_bytes()
    digest = sha256(data).hexdigest()
    if len(data) != EXPECTED_SIZE or digest != EXPECTED_SHA256:
        raise AssertionError(
            f"Unexpected stock image: size={len(data)}, SHA256={digest}"
        )
    print(f"Stock F08: {len(data)} bytes; SHA256 {digest}")

    check_group(data, "D180 state -> R7 -> bank-4 entry:", (
        # Conditional tests and a nearby D180 writer; reaching the writer
        # from every predecessor is not established by this audit.
        (0, 0xA272, "90 d1 80 e0 70 03 02 a3 5d e4 80 37", "D180 test; zero branches to A35D"),
        (0, 0xA286, "90 d1 80 e0 64 01 60 04 74 01 80 23", "D180 comparison with 01"),
        (0, 0xA2AB, "90 d1 80 e0 64 02 60 09 74 02 f0", "conditional 02 write to XDATA D180 at A2B5"),
        (2, 0xFA75, "90 d1 80 e0 60 32", "entry tests XDATA D180"),
        (2, 0xFAC5, "12 fe 80 02 2d 2e", "LCALL FE80; LJMP shared trampoline 2D2E"),
        (2, 0xFE80, "90 d1 80 e0 14 60 08 14 60 08 80 00 "
                     "7f 00 22 7f 10 22 7f 20 22", "D180 -> R7: other=00, 1=10, 2=20"),
        (0, 0x2D2E, "90 b9 d7 02 0b bc", "shared trampoline targets bank-local B9D7"),
        (0, 0x0BBC, "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 10", "dispatch to bank-4 selector"),
        (0, 0x5010, "78 04 80 6a", "R0=04 then shared bank switch at 507E"),
        (0, 0x507E, "c8 90 ff ff f5 52 12 0d d0 f0 e8 22", "shared selector writes XDATA FFFF"),
        (0, 0x0DD0, "c0 d0 25 30 d0 d0 22", "bank selector adjustment helper"),
        (4, 0xB9D7, "90 c6 8a ef f0", "write incoming R7 to XDATA C68A"),
    ))

    check_group(data, "C68A -> D8FE and C68A -> D83C mirror:", (
        # Several helper calls intervene between the initial B9D7 write and
        # these reads. No claim that C68A retains its initial value is made.
        (4, 0xBA03, "12 fe 6d ef 70 06 90 c6 8a e0 70 0c", "conditional C68A read"),
        (4, 0xBA15, "90 c6 8a e0 70 0e 7d 02 7f 04 12 26 6e "
                     "7d 02 7f 05 12 26 6e", "conditional code converges at BA29"),
        (4, 0xBA29, "90 c6 8a e0 ff 12 fb 1f", "C68A -> R7 -> D8FE setter"),
        (4, 0xBA31, "90 c6 8a e0 fd 7f 0c 12 13 00", "C68A -> R5, selector R7=0C"),
        (0, 0x1300, "90 8a 37 02 0b a9", "trampoline to bank-local 8A37"),
        (0, 0x0BA9, "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 0c", "dispatch to bank-3 selector"),
        (0, 0x500C, "78 03 80 6e", "R0=03 then shared switch 507E"),
        (3, 0x8A37, "ef b4 1f 00 40 03 02 8c c3 90 8a 47 f8 28 28 73", "3-byte jump table at 8A47, index R7"),
        (3, 0x8A6B, "02 8a b5", "index 0C selects writer 3:8AB5"),
        (3, 0x8AB5, "90 d8 3c ed f0 22", "R5 -> XDATA D83C; RET"),
    ))
    if 0x8A47 + 0x0C * 3 != 0x8A6B:
        raise AssertionError("Unexpected writer table index")

    check_group(data, "D83C -> R7 -> D8FE:", (
        (4, 0xF348, "e4 90 c5 00 f0 7f 0c 12 0f f4 12 fb 1f", "getter 0C then D8FE setter"),
        (0, 0x0FF4, "90 a9 8d 02 0b a9", "trampoline to bank 3:A98D via 0BA9"),
        (3, 0xA98D, "e4 fe ef b4 1f 00 40 03 02 aa f1 90 a9 9f f8 28 28 73", "3-byte getter jump table at A99F"),
        (3, 0xA9C3, "02 aa 07", "index 0C selects getter 3:AA07"),
        (3, 0xAA07, "90 d8 3c e0 fe 02 aa f1", "XDATA D83C -> R6"),
        (3, 0xAAF1, "af 06 22", "R6 -> R7; RET"),
        (4, 0xFB1F, "90 d8 fe ef f0 12 11 32 ef 14 54 03 ff "
                     "90 d8 fd e0 54 fc 4f f0 22", "R7 -> XDATA D8FE; also updates D8FD"),
    ))
    if 0xA99F + 0x0C * 3 != 0xA9C3:
        raise AssertionError("Unexpected getter table index")

    check_group(data, "Other directly encoded C68A writes (non-exhaustive):", (
        (1, 0xE972, "90 c6 8a ef f0", "R7 -> C68A"),
        (1, 0xEF62, "90 c6 8a e0 04 f0", "increment C68A in place"),
        (2, 0xF7D0, "90 c6 8a ef f0", "R7 -> C68A"),
        (2, 0xFEE2, "90 c6 8a ef f0 22", "R7 -> C68A; RET"),
        (7, 0xC10A, "90 c6 8a ee f0", "R6 -> C68A"),
        (13, 0xABDF, "90 c6 8a f0", "A -> C68A"),
        (13, 0xB5E9, "90 c6 8a ef f0", "R7 -> C68A"),
        (18, 0xDAB0, "90 c6 8a ef f0", "R7 -> C68A"),
        (19, 0x71B8, "90 c6 8a ef f0", "R7 -> C68A"),
    ))

    d83c_sites = literal_dptr_references(data, 0xD83C)
    if d83c_sites != [(3, 0x8AB5), (3, 0xAA07)]:
        raise AssertionError(f"Unexpected literal D83C references: {d83c_sites}")
    c68a_sites = literal_dptr_references(data, 0xC68A)
    if len(c68a_sites) != 80:
        raise AssertionError(f"Unexpected literal C68A reference count: {len(c68a_sites)}")
    print("Literal MOV DPTR references in code banks 0..19: "
          f"D83C={d83c_sites}, C68A={len(c68a_sites)} occurrences")
    print("PASS: stock-byte conditional paths and named writer sites match")
    print("LIMIT: literal scans do not exclude indirect writes or embedded data; "
          "helper side effects, D180 origin, runtime values, physical ingress "
          "and device behavior remain unverified")


if __name__ == "__main__":
    audit()
