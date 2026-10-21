#!/usr/bin/env python3
"""Offline F08 audit of the bank-9 menu command / action boundary.

The verified path is command -> table enumeration -> item dispatcher.
It does NOT establish a physical joystick event, selected row, or refresh.
Only stock bytes are read; no firmware or device output is produced.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK = 9


def at(image: bytes, address: int, length: int) -> bytes:
    offset = BANK * 0x10000 + address
    return image[offset:offset + length]


def expect(image: bytes, address: int, hexdump: str) -> None:
    wanted = bytes.fromhex(hexdump)
    actual = at(image, address, len(wanted))
    if actual != wanted:
        raise AssertionError(
            f"9:{address:04X} (file offset 0x{BANK * 0x10000 + address:X}): "
            f"expected {wanted.hex(' ')}, got {actual.hex(' ')}"
        )


def audit() -> None:
    image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Unexpected stock image length"
    assert sha256(image).hexdigest() == SHA256, "Unexpected stock image SHA-256"

    # MOV DPTR,#C501; MOV A,R7; MOVX @DPTR,A. The following command
    # comparisons send 0/1/2/5 to D516, 3/7/8 to D4A0, 4 to D483;
    # other values fall through to D595. This is a bank-local entrypoint,
    # not an identified joystick decoder or proof it is called at runtime.
    expect(image, 0xD45C, "90 c5 01 ef f0 e4 a3 f0 a3 f0 a3 04 f0")
    expect(image, 0xD469, "ef 24 fd 60 32 14 60 12 24 04 24 fa "
                           "40 03 02 d5 16 14 60 23 14 60 20 02 d5 95")

    # In the D516 path C501==2 sets C504=1; other commands set C504=0.
    # C503 (page index) and C502 (row index) are reset and then walked.
    expect(image, 0xD516, "90 c5 01 e0 b4 02 08 90 c5 04 74 01 f0 "
                           "80 05 e4 90 c5 04 f0")
    expect(image, 0xD52A, "e4 90 c5 03 f0 e4 90 c5 02 f0")
    expect(image, 0xD552, "ef 12 e4 fa 12 e4 8c 12 e4 c7 64 01 "
                           "60 05 12 fe f6 50 12")
    expect(image, 0xD565, "12 e4 f6 12 e4 8c 12 e4 b5")
    expect(image, 0xD577, "12 e4 f6 12 e4 8c 12 e4 b5 7b 01 e4 fd")
    expect(image, 0xD584, "12 97 db")
    expect(image, 0xE4B5, "90 c5 02 e0 75 f0 02 a4 f5 82 "
                           "85 f0 83 12 36 81 ff 22")
    expect(image, 0xE4FA, "25 e0 25 e0 24 97 f5 82 e4 34 97 22")
    expect(image, 0xFEF6, "c3 22")  # Stub returns carry=0.

    # Two alternate page-order tables cover the same 30 action records.
    items = [tuple(at(image, 0x9747 + 2 * i, 2)) for i in range(30)]
    assert [item for item, _ in items] == list(range(30))
    assert items[23:25] == [(23, 1), (24, 1)]
    layouts = []
    for start in (0x9783, 0x9797):
        pages = [at(image, start + 4 * page, 4) for page in range(5)]
        spans = []
        for space, high, low, count in pages:
            address = high * 256 + low
            assert space == 0xFF and (address - 0x9747) % 2 == 0
            spans.append(list(range((address - 0x9747) // 2,
                                    (address - 0x9747) // 2 + count)))
        assert sorted(index for span in spans for index in span) == list(range(30))
        layouts.append(spans)
    assert layouts[0][3][:2] == [23, 24]
    assert layouts[1][1][:2] == [23, 24]

    # R7 indexes the bank-9 30-entry LJMP action table. The two targets
    # handle item-local 0BAD/0BAE state, not XDATA D12D requests.
    expect(image, 0x97DB, "90 c6 93 eb f0 ef b4 1e 00 40 03 "
                           "02 a4 9c 90 97 f0 f8 28 28 73")
    expect(image, 0x9835, "02 a1 4c 02 a1 c0")

    # Literal direct-call boundaries only. A raw pattern scan cannot
    # exclude indirect jumps/calls, cross-bank entrypoints or false matches.
    bank = at(image, 0, 0x10000)
    callers = {i for i in range(len(bank) - 2)
               if bank[i:i + 3] == bytes.fromhex("12 97 db")}
    assert callers == {0xD4D6, 0xD584, 0xE0E2, 0xF24C}
    assert bytes.fromhex("12 d4 5c") not in bank
    assert bytes.fromhex("02 d4 5c") not in bank
    e057 = {i for i in range(len(bank) - 2)
            if bank[i:i + 3] == bytes.fromhex("12 e0 57")}
    assert e057 == {0xF77C, 0xF787, 0xF78E}
    for caller, action in ((0xF77C, 11), (0xF787, 11), (0xF78E, 14)):
        expect(image, caller - 2, f"7f {action:02x} 12 e0 57")

    print(f"PASS: stock F08 SHA-256 {SHA256}")
    print("9:D45C: R7 -> XDATA C501; 0/1/2/5 -> 9:D516, 3/7/8 -> 9:D4A0")
    print("9:D516: walks page/row records via XDATA C503/C502")
    print("Page indexes 3 (at 9:9783) and 1 (at 9:9797) contain actions 23/24")
    print("9:E4B5 -> R7, 9:97DB -> 9:A14C/9:A1C0 (table indices 23/24)")
    print("Direct 9:97DB call sites:", ", ".join(f"9:{x:04X}" for x in sorted(callers)))
    print("9:E057 direct callers pass only actions 11/14")
    print("LIMIT: No physical joystick origin, selection event, or D12D request proven")


if __name__ == "__main__":
    audit()
