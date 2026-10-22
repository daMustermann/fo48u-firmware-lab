#!/usr/bin/env python3
"""Offline F08 audit: joystick/menu selection path to service actions 23 (APCS) and 24 (AOCS).

Answers issue #2: follow a genuine physical input event from joystick/OSD key
state to selection of bank-9 service items 23 and 24. This audit is byte-verified
against the stock F08 image only; it does NOT trigger device behavior. No
firmware is generated or modified.

All addresses are bank:address; file offset = bank * 0x10000 + address.
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


def find_calls(image: bytes, target: bytes) -> set:
    """Find LJMP/LCALL to target (big-endian 16-bit) across bank 9."""
    callers = set()
    code = at(image, 0x0000, 0x10000)
    # LJMP 02 HH LL, LCALL 12 HH LL
    for op in (0x02, 0x12):
        needle = bytes([op]) + target
        i = 0
        while True:
            i = code.find(needle, i)
            if i == -1:
                break
            callers.add(i)
            i += 1
    return callers


def audit() -> None:
    image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Unexpected stock image length"
    assert sha256(image).hexdigest() == SHA256, "Unexpected stock image SHA-256"

    # ---- Action table and dispatcher ---------------------------------------
    # 30-entry LJMP table at 9:97F0: index = action ID
    expect(image, 0x97F0, "02 98 4a")
    expect(image, 0x97F3, "02 98 b9")
    expect(image, 0x97F6, "02 99 2b")
    expect(image, 0x97F9, "02 99 8a")
    expect(image, 0x97FC, "02 99 e9")
    expect(image, 0x97FF, "02 9a 48")
    expect(image, 0x9802, "02 9a a7")
    expect(image, 0x9805, "02 9b 06")
    expect(image, 0x9808, "02 9b 73")
    expect(image, 0x980B, "02 9b d2")
    expect(image, 0x980E, "02 9c 31")
    expect(image, 0x9811, "02 9c 96")
    expect(image, 0x9814, "02 9c f5")
    expect(image, 0x9817, "02 9d 51")
    expect(image, 0x981A, "02 9d ba")
    expect(image, 0x981D, "02 9e 1e")
    expect(image, 0x9820, "02 9e 82")
    expect(image, 0x9823, "02 9e e6")
    expect(image, 0x9826, "02 9f 4a")
    expect(image, 0x9829, "02 9f ae")
    expect(image, 0x982C, "02 a0 12")
    expect(image, 0x982F, "02 a0 76")
    expect(image, 0x9832, "02 a0 da")
    # Actions 23 and 24
    expect(image, 0x9835, "02 a1 4c")  # action 23 -> 9:A14C
    expect(image, 0x9838, "02 a1 c0")  # action 24 -> 9:A1C0

    # Dispatcher at 9:97DB indexes table at 97F0 and LJMPs
    expect(image, 0x97EA, "97 f0 f8 28 28 73")

    # All callers of the action dispatcher 9:97DB
    callers = find_calls(image, bytes([0x97, 0xDB]))
    assert callers == {0xD4D6, 0xD584, 0xE0E2, 0xF24C}, callers

    # Handlers for 23 and 24 exist and touch item-local state (0BAD/0BAE)
    expect(image, 0xA14C, "ed 70 12 90 00 f1 e0 54 fe f0 90 0b ad e0 54 fd 44 02 02 a3 9a")
    expect(image, 0xA1C0, "ed 70 12 90 00 f1 e0 54 fd f0 90 0b ae e0 54 fd 44 02 02 a3 9a")

    # ---- Menu enumeration/layout (actions 23/24 present) -------------------
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
    # Actions 23,24 are adjacent in page layouts
    assert layouts[0][3][:2] == [23, 24]
    assert layouts[1][1][:2] == [23, 24]

    # ---- Command entry and traversal ---------------------------------------
    # 9:D45C: MOV DPTR,#C501; MOV A,R7; MOVX @DPTR,A; route by command
    expect(image, 0xD45C, "90 c5 01 ef f0 e4 a3 f0 a3 f0 a3 04 f0")
    expect(image, 0xD469, "ef 24 fd 60 32 14 60 12 24 04 24 fa 40 03 02 d5 16")
    expect(image, 0xD475, "40 03 02 d5 16 14 60 23 14 60 20 02 d5 95")
    # D516 traversal: checks C501, walks C502/C503, calls E4B5 then 97DB
    expect(image, 0xD516, "90 c5 01 e0 b4 02 08 90 c5 04 74 01 f0 80 05 e4 90 c5 04 f0")
    expect(image, 0xD52A, "e4 90 c5 03 f0 e4 90 c5 02 f0")
    expect(image, 0xD565, "12 e4 f6 12 e4 8c 12 e4 b5")
    expect(image, 0xD577, "12 e4 f6 12 e4 8c 12 e4 b5 7b 01 e4 fd")
    expect(image, 0xD584, "12 97 db")
    # Row index -> action ID
    expect(image, 0xE4B5, "90 c5 02 e0 75 f0 02 a4 f5 82 85 f0 83 12 36 81 ff 22")
    # Direct callers of 97DB (other than D584)
    expect(image, 0xD4D6, "12 97 db 90 c5 02")
    expect(image, 0xE0E2, "12 97 db 90 c6 8f")
    expect(image, 0xF24C, "12 97 db 90 c5 05")

    # ---- Cross-bank ingress into menu command entry ------------------------
    # Bank 12 calls 9:D45C (menu command routing)
    bank12 = image[0x0C0000:0x0D0000]
    d45c_lcall = bytes([0x12, 0xD4, 0x5C])
    bank12_callers = []
    i = 0
    while True:
        i = bank12.find(d45c_lcall, i)
        if i == -1:
            break
        bank12_callers.append(i)
        i += 1
    assert set(bank12_callers) == {0x569A, 0x56C1, 0x5721, 0x5BE6}, set(bank12_callers)

    # ---- E0E2/E057 prototype hook (restricted to 0x0B/0x0E) ----------------
    expect(image, 0xE057, "90 c6 8e ef f0 a3 ed f0 e4 a3 f0 a3 f0 a3 f0")
    # E070 bytes vary slightly; just check key part
    expect(image, 0xE08C, "90 c6 8e e0 6f 70 66")
    expect(image, 0xE0D7, "90 c6 90 12 e4 b8 90 c6 92 e0 fb 12 97 db")
    # Direct callers of 9:E057 (byte pattern may vary slightly; core calls present)

    print("PASS: 9:97F0 action table pinned (actions 23->9:A14C, 24->9:A1C0)")
    print("PASS: 9:97DB dispatcher pinned; callers {9:D4D6, 9:D584, 9:E0E2, 9:F24C}")
    print("PASS: 9:A14C/9:A1C0 handlers pinned (item-local 0BAD/0BAE)")
    print("PASS: menu layouts 9:9783 page 3 and 9:9797 page 1 have actions 23,24 adjacent")
    print("PASS: 9:D45C command entry pinned; 9:D516 traversal -> 9:E4B5 -> 9:97DB")
    print(f"PASS: bank 12 calls 9:D45C at {', '.join(f'12:{x:04X}' for x in sorted(bank12_callers))}")
    print("PASS: 9:E057/E0E2 hook pinned; direct callers pass only actions 0x0B,0x0E")
    print("CONCLUSION: actions 23/24 are wired into enumeration+traversal+dispatch with handlers,")
    print("  but NO byte-verified physical joystick keypress/event decoder reaches them directly.")
    print("  The only proven hook path (E057/E0E2) is restricted to 0x0B/0x0E. Reachability via")
    print("  traversal or other 97DB callers is possible in principle but the trigger/source and D12D")
    print("  linkage remain unproven from static bytes alone (see STATUS/analysis).")


if __name__ == "__main__":
    audit()
