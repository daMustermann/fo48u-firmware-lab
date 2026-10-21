#!/usr/bin/env python3
"""Read-only F08 audit of the candidate receive-buffer handoff.

All claims are conditional static byte paths. This does not establish the
external transport, the actual value of D8FE, or an accepted service command.
"""

from hashlib import sha256
from pathlib import Path

IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000


def at(data: bytes, bank: int, addr: int, count: int) -> bytes:
    start = bank * BANK_SIZE + addr
    return data[start:start + count]


def expect(data: bytes, bank: int, addr: int, opcodes: str) -> None:
    wanted = bytes.fromhex(opcodes)
    got = at(data, bank, addr, len(wanted))
    assert got == wanted, f"{bank}:{addr:04X}: {got.hex(' ')} != {wanted.hex(' ')}"


def audit() -> None:
    data = IMAGE.read_bytes()
    assert len(data) == 2_031_616
    assert sha256(data).hexdigest() == SHA256

    # Both bank-13 receive-selection and bank-18 copy-test call into logical
    # bank 4, using 0:0BBC -> 0:5010. Both helpers return XDATA D8FE in R7.
    expect(data, 0, 0x2656, "90 fc fe 02 0b bc")
    expect(data, 0, 0x2A58, "90 fe 6d 02 0b bc")
    expect(data, 0, 0x0BBC,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 10")
    expect(data, 0, 0x5010, "78 04 80 6a")
    expect(data, 4, 0xFCFE, "c0 d0 75 d0 10 90 d8 fe e0 ff d0 d0 22")
    expect(data, 4, 0xFE6D, "90 d8 fe e0 ff 22")

    # D8FE is mutable: one bank-4 helper writes incoming R7, a separate
    # initialization branch clears it, and another branch copies C693 to it.
    # This does not identify a live value or a physical transport.
    expect(data, 4, 0xFB1F, "90 d8 fe ef f0")
    expect(data, 4, 0xE6F3, "e4 90 d8 fe f0")
    expect(data, 4, 0xE70B, "90 c6 93 e0 90 d8 fe f0")

    # On the FF23 masked-address branch, a zero R7 selects the CFD8 128-byte
    # receive buffer; a nonzero R7 selects CEE1 with an 80-byte limit.
    # F7C6 loads (CFD2 & FE), then E3D7 ORs the post-DD24 R7 into CFD2.
    # DD24 can overwrite R7 (e.g. reading FF24), so that R7 cannot safely
    # be equated with the original D8FE selector without additional proof.
    expect(data, 13, 0xE3B1, "90 ff 23 e0 54 fe 64 6e 70 32")
    expect(data, 13, 0xE3BB,
           "12 26 56 ef 7b 01 70 08 7a cf 79 d8 7d 80 80 06 "
           "7a ce 79 e1 7d 50 12 dd 24")
    expect(data, 13, 0xE3D4, "12 f7 c6 4f f0")
    expect(data, 13, 0xF7C6, "90 cf d2 e0 54 fe 22")
    expect(data, 13, 0xDD3F, "90 ff 24 e0 ff")

    # Bank 18 examines the low two bits of CFD2, in order. E245 jumps
    # directly to DJNZ so index=0 causes no RRC; index=1 causes one RRC.
    # Only after an enabled bit is found does it call the second D8FE reader.
    expect(data, 18, 0xD6C6, "12 e2 2d 12 2d ac 40 41 12 2d b2")
    expect(data, 18, 0xE22D,
           "e4 90 c5 01 f0 f0 90 c5 01 e0 ff c3 94 02 50 47")
    expect(data, 18, 0xE23D,
           "90 cf d2 e0 fe a8 07 08 80 02 c3 13 d8 fc 30 e0 2e")
    expect(data, 18, 0xE24E, "12 2a 58 ef 60 1f")
    expect(data, 18, 0xE254,
           "90 c5 01 e0 75 f0 50 a4 24 e1 f9 74 ce 35 f0 "
           "fa 7b 01 78 d8 7c cf 7d 01 7e 00 7f 50 12 35 fc")
    expect(data, 18, 0xE273, "90 c5 01 e0 90 cf d1 f0 22")
    expect(data, 18, 0xE27C, "90 c5 01 e0 04 f0 80 af 22")

    # Generic copy arguments: R2:R1 = source XDATA, R4:R0 = destination
    # XDATA, R3=R5=1, R6:R7=0x0050. The (3,3) dispatch index lands at
    # 0:359A (SJMP 35CF), where MOVX reads source and writes destination.
    expect(data, 0, 0x35FC,
           "88 f0 ef 60 01 0e 4e 60 c3 88 f0 ed 24 02 b4 04 00 "
           "50 b9 f5 82 eb 24 02 b4 04 00 50 af 23 23 45 82 "
           "23 90 35 7c 73")
    assert 0x357C + (((3 << 2) | 3) << 1) == 0x359A
    expect(data, 0, 0x359A, "80 33")
    assert 0x359A + 2 + 0x33 == 0x35CF
    expect(data, 0, 0x35CF,
           "89 82 8a 83 ec fa e0 a3 c8 c5 82 c8 cc c5 83 cc "
           "f0 a3 c8 c5 82 c8 cc c5 83 cc df ea de e8 80 db")

    for slot, source in enumerate((0xCEE1, 0xCF31)):
        assert (0xCEE1 + slot * 0x50) == source
        assert source + 0x50 <= 0xCFD8
    assert 0xCFD8 + 2 == 0xCFDA
    assert 0xCFD8 + 3 == 0xCFDB

    # The search chooses the first enabled slot; bits outside 0/1 do not
    # produce an 80-byte copy in this specific loop.
    for mask, first in ((0, None), (1, 0), (2, 1), (3, 0), (4, None)):
        slots = [i for i in (0, 1) if mask & (1 << i)]
        assert (slots[0] if slots else None) == first

    print("PASS: stock-image guarded buffer-selection and generic XDATA copy byte paths")
    print("13:E3BB uses D8FE for buffer selection; 13:E3D4 updates CFD2 using post-DD24 R7")
    print("18:E22D uses CFD2 bits 0/1, re-reads D8FE, conditionally copies 80 bytes")
    print("0:35FC dispatch -> 0:359A -> 0:35CF: CEE1/CF31 -> CFD8")
    print("4:FB1F/4:E6F3/4:E70B: D8FE set from R7, cleared, or copied from C693")
    print("LIMIT: No live D8FE value, frame provenance, acceptance, or hardware result")


if __name__ == "__main__":
    audit()
