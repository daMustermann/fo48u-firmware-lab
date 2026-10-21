#!/usr/bin/env python3
"""Verify static D8FE source and C693 mapping paths in stock FO48U F08.

Byte assertions only: neither the runtime state nor any external command,
OLED effect, or device transport is established by these instructions.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"


def expect(data: bytes, bank: int, address: int, opcodes: str) -> None:
    expected = bytes.fromhex(opcodes)
    offset = bank * 0x10000 + address
    actual = data[offset:offset + len(expected)]
    assert actual == expected, (
        f"{bank}:{address:04X}: {actual.hex(' ')} != {expected.hex(' ')}")


def audit() -> None:
    data = IMAGE.read_bytes()
    assert len(data) == 2_031_616
    assert sha256(data).hexdigest() == SHA256

    # 3:BF9D -> common trampoline 0:0F52 -> 0:0C08 -> 0:5020
    # selects *bank 8*. The destination is 8:EE5E, not 4:EE5E.
    expect(data, 3, 0xBF98, "90 c5 09 e0 ff 12 0f 52 d2 04 12 a8 23")
    expect(data, 0, 0x0F52, "90 ee 5e 02 0c 08")
    expect(data, 0, 0x0C08,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 20")
    expect(data, 0, 0x5020, "78 08 80 5a")

    # Input R7 is saved to C6A2. 8:FD3B reads D8FE, subtracts 0x10;
    # 8:EE5E branches on D8FE==0x10 or ==0x20 and also tests D8FC.
    expect(data, 8, 0xEE5E,
           "90 c6 a2 ef f0 12 fd 3b 60 11 24 f0 60 2c 80 00")
    expect(data, 8, 0xFD3B, "90 d8 fe e0 24 f0 22")
    expect(data, 8, 0xEE79, "12 14 08 50 0d 90 c6 a2 e0 b4 10 03")
    expect(data, 8, 0xEE98,
           "90 c6 a2 e0 b4 20 15 90 d8 fc e0 14 60 08 14 60 08")
    expect(data, 8, 0xEEB4,
           "90 d8 fc e0 14 60 08 14 60 08")

    # All direct return sites in 8:EE5E..EEC8 set R7 to one of
    # 03/0C/0F/10. Values are state codes, not decoded service opcodes.
    returns = {
        0xEE73: 0x0F, 0xEE76: 0x03, 0xEE85: 0x0F, 0xEE88: 0x10,
        0xEE92: 0x03, 0xEE95: 0x0C, 0xEEAB: 0x03, 0xEEAE: 0x03,
        0xEEB1: 0x0C, 0xEEC0: 0x0C, 0xEEC3: 0x0C, 0xEEC6: 0x03,
    }
    for location, value in returns.items():
        expect(data, 8, location, f"7f {value:02x} 22")
    assert set(returns.values()) == {0x03, 0x0C, 0x0F, 0x10}

    # Caller immediately passes that R7 to 3:A823, which stores it in C693.
    # Later in 3:A823 the code reads C693 and conditionally transforms C696.
    expect(data, 3, 0xA823,
           "90 c6 93 ef f0 e4 a3 f0 12 1b f4")
    expect(data, 3, 0xA87E, "90 c6 93 e0 ff b4 0f 05")

    # A separate bank-4 direct setter takes R7 from C68A.
    expect(data, 4, 0xBA29, "90 c6 8a e0 ff 12 fb 1f")

    # Another direct setter passes selector 0x0C to a bank-3 getter:
    # 0:0FF4 -> 0:0BA9 -> 0:500C selects bank 3, entry 3:A98D.
    # Jump-table index 12 reaches 3:AA07, which returns D83C in R7.
    expect(data, 4, 0xF348, "e4 90 c5 00 f0 7f 0c 12 0f f4 12 fb 1f")
    expect(data, 0, 0x0FF4, "90 a9 8d 02 0b a9")
    expect(data, 0, 0x0BA9,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 0c")
    expect(data, 0, 0x500C, "78 03 80 6e")
    expect(data, 3, 0xA98D,
           "e4 fe ef b4 1f 00 40 03 02 aa f1 90 a9 9f f8 28 28 73")
    expect(data, 3, 0xA9C3, "02 aa 07")
    expect(data, 3, 0xAA07, "90 d8 3c e0 fe 02 aa f1")
    expect(data, 3, 0xAAF1, "af 06 22")

    # The called setter stores R7 in D8FE, then updates bits in D8FD.
    expect(data, 4, 0xFB1F,
           "90 d8 fe ef f0 12 11 32 ef 14 54 03 ff 90 d8 fd "
           "e0 54 fc 4f f0 22")

    # A distinct bank-4 routine first saves *old* D8FE into C693,
    # clears D8FE, then restores it. The restore is not evidence that the
    # bank-3 C693 writer provides a new D8FE value to this routine.
    expect(data, 4, 0xE6D4, "90 d8 fe e0 90 c6 93 f0")
    expect(data, 4, 0xE6F3, "e4 90 d8 fe f0")
    expect(data, 4, 0xE70B, "90 c6 93 e0 90 d8 fe f0")

    print("PASS: D8FE writes from C68A and D83C getter, plus save/clear/restore")
    print("3:BF9D -> bank 8:EE5E reads D8FE and maps R7 into C693")
    print("LIMIT: sources of C68A/D83C, live state, and panel effect unresolved")


if __name__ == "__main__":
    audit()
