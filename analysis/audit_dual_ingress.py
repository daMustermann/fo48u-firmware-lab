#!/usr/bin/env python3
"""Read-only, stock-byte audit of the two F08 receive paths.

This checks conditional CPU paths, not physical interfaces, checksum
acceptance, live buffer contents, or an executed OLED service command.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"


def expect(data: bytes, bank: int, addr: int, sequence: str) -> None:
    expected = bytes.fromhex(sequence)
    offset = bank * 0x10000 + addr
    actual = data[offset:offset + len(expected)]
    assert actual == expected, (
        f"{bank}:{addr:04X}: {actual.hex(' ')} != {expected.hex(' ')}")


def audit() -> None:
    data = IMAGE.read_bytes()
    assert len(data) == 2_031_616
    assert sha256(data).hexdigest() == SHA256

    # Primary ingress: FF23 masked address, FF24 seed, FF25 data, FF27/FF29
    # status, FF2A overflow/acknowledgment. D8FE chooses CFD8 or CEE1.
    expect(data, 13, 0xE3B1, "90 ff 23 e0 54 fe 64 6e 70 32")
    expect(data, 13, 0xE3BB,
           "12 26 56 ef 7b 01 70 08 7a cf 79 d8 7d 80 80 06 "
           "7a ce 79 e1 7d 50 12 dd 24")
    expect(data, 13, 0xDD24,
           "90 c9 c2 eb f0 a3 ea f0 a3 e9 f0 a3 ed f0 90 ff 27 e0")
    expect(data, 13, 0xDD3C,
           "78 58 f6 90 ff 24 e0 ff 12 ef 37 12 ef 43")
    expect(data, 13, 0xDD51,
           "90 ff 27 e0 54 04 64 04 70 66 90 ff 29 e0 54 02 70 5e")
    expect(data, 13, 0xDD63,
           "90 c9 c5 e0 ff 78 58 e6 c3 9f 40 0b 90 ff 2a e0 "
           "44 40 f0 e4 f6 80 47 90 ff 25 e0 90 c9 c2 12 ef 0d")
    expect(data, 13, 0xDDA4,
           "12 ef 37 90 00 03 12 36 81 b4 fc 0e 90 00 02 "
           "12 36 81 b4 03 05 e4 ff 12 f4 b0 7f 01 22 7f 00 22")

    # Secondary ingress: FE87 masked address, FE88 seed, FE89 data, FE8B/
    # FE8D status, FE8E overflow/acknowledgment; source buffer is CF31.
    expect(data, 13, 0xEAF5, "e4 90 cf d5 f0 90 fe 87 e0 54 fe 64 6e")
    expect(data, 13, 0xEB04,
           "7b 01 7a cf 79 31 12 de 63 12 f7 b0 4f f0 e0 a2 e1")
    expect(data, 13, 0xDE63,
           "90 c9 c2 eb f0 a3 ea f0 a3 e9 f0 90 fe 8b e0")
    expect(data, 13, 0xDE6E,
           "90 fe 8b e0 54 02 64 02 70 18 78 58 f6 90 fe 88 "
           "e0 ff 90 c9 c2 12 ef 3a 12 ef 43")
    expect(data, 13, 0xDEA2,
           "78 58 e6 c3 94 50 40 09 a3 e0 44 40 f0 e4 f6 "
           "80 4a 90 fe 89 e0 90 c9 c2 12 ef 0d")
    expect(data, 13, 0xDEB3,
           "90 fe 89 e0 90 c9 c2 12 ef 0d b5 17 da ec "
           "b5 16 d6 90 fe 8e 12 ef 4e")
    expect(data, 13, 0xDEDD,
           "90 c9 c2 12 ef 3a 90 00 03 12 36 81 b4 fc 0e "
           "90 00 02 12 36 81 b4 03 05 7f 01 12 f4 b0 "
           "7f 01 22 7f 00 22")

    # Both receivers return R7=1 on the complete-frame path and R7=0
    # otherwise. Their callers update separate ready flags in CFD2.
    expect(data, 13, 0xE3D1,
           "12 dd 24 12 f7 c6 4f f0 90 cf d2 e0 13 50 15")
    expect(data, 13, 0xF7C6, "90 cf d2 e0 54 fe 22")
    expect(data, 13, 0xE3E0,
           "e4 ff 12 c8 a4 bf 01 0d 12 f7 c6 f0 22")

    # 13:F7B0 doubles the incoming R7 (0/1), clears CFD2 bit 1, and
    # returns the masked byte in A for the caller's OR / MOVX write.
    expect(data, 13, 0xF7B0, "ef 25 e0 ff 90 cf d2 e0 54 fd 22")
    expect(data, 13, 0xEB0D,
           "12 f7 b0 4f f0 e0 a2 e1 50 15 7f 01 12 c8 a4")
    expect(data, 13, 0xEB17,
           "7f 01 12 c8 a4 bf 01 0d 12 f7 b4 f0 22")
    expect(data, 13, 0xF7B4, "90 cf d2 e0 54 fd 22")
    expect(data, 13, 0xE3ED, "12 26 5c 12 f7 c6 4f f0 22")
    expect(data, 13, 0xEB24, "12 26 5c 12 f7 b0 4f f0 22")

    # Both receivers share the byte-indexing writer and frame-length helper.
    expect(data, 13, 0xEF0D,
           "ff e0 fb a3 e0 fa a3 e0 f9 78 58 e6 06 f5 82 "
           "75 83 00 ef 12 36 c0 90 00 01 12 36 81 54 7f 24 03")

    # After completion, 13:C8A4 reads fields from CFD8 when D8FE==0;
    # otherwise 13:C8D4 computes CEE3 + 0x50 * slot for fields at offset 2.
    expect(data, 13, 0xC8A4,
           "90 c9 c2 ef f0 e4 a3 f0 fe 7f 03 fd 7b 01 7a c9 "
           "79 c4 12 3e 86 12 26 56 ef 70 15")
    expect(data, 13, 0xC8BF,
           "90 cf da e0 90 c9 c4 f0 90 cf db e0 90 c9 c5 f0")
    expect(data, 13, 0xC8D4,
           "90 c9 c2 e0 ff 75 f0 50 a4 24 e3 f5 82 e4 "
           "34 ce f5 83 e0 90 c9 c4 f0")

    # The bank-18 consumer reads CFD1 and clears the corresponding CFD2 bit
    # after the guarded dispatch. Its earlier copier accepts both source slots.
    expect(data, 18, 0xE254,
           "90 c5 01 e0 75 f0 50 a4 24 e1 f9 74 ce 35 f0 fa")
    expect(data, 18, 0xD712,
           "90 cf d2 e0 ff 90 cf d1 e0 fe 74 01 a8 06 08 "
           "80 02 c3 33 d8 fc f4 5f 90 cf d2 f0 22")

    assert (0xCEE1, 0xCEE1 + 0x50) == (0xCEE1, 0xCF31)
    assert (0xCEE3, 0xCEE3 + 0x50) == (0xCEE3, 0xCF33)
    for prior in range(256):
        for result in (0, 1):
            assert ((prior & 0xFE) | result) & 0x01 == result
            assert ((prior & 0xFD) | (result * 2)) & 0x02 == result * 2
        for slot in (0, 1):
            assert (prior & ~(1 << slot)) & 0xFF == prior & (0xFF ^ (1 << slot))

    print("PASS: stock-byte guarded dual receive path and independent CFD2 bits")
    print("slot 0: FF23/FF24/FF25 via 13:DD24 -> CFD8 or CEE1 -> CFD2.bit0")
    print("slot 1: FE87/FE88/FE89 via 13:DE63 -> CF31 -> CFD2.bit1")
    print("both receivers use 13:EF0D, return R7=0/1; bank 18 clears selected bit")
    print("LIMIT: transport, acceptance, checksum, live values and OLED effect unknown")


if __name__ == "__main__":
    audit()
