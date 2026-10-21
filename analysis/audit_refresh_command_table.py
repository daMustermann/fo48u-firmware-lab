#!/usr/bin/env python3
"""Read-only audit of the stock F08 refresh command dispatch and state path.

This establishes static control-flow facts; it does not establish a joystick,
USB, DDC/CI, or other externally reachable command transport. No image is
changed and no monitor command is sent.
"""

from hashlib import md5

from build_custom import file_offset, load_source


STOCK_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"


def at(image: bytes, bank: int, address: int, count: int) -> bytes:
    offset = file_offset(bank, address)
    return image[offset : offset + count]


def expect(image: bytes, bank: int, address: int, pattern: str) -> None:
    wanted = bytes.fromhex(pattern)
    actual = at(image, bank, address, len(wanted))
    assert actual == wanted, (
        f"bank {bank} address {address:04X}: "
        f"wanted {wanted.hex(' ')}, got {actual.hex(' ')}"
    )


def audit(image: bytes | None = None) -> dict[str, object]:
    original = image if image is not None else bytes(load_source())
    assert len(original) == 31 * 65536
    assert md5(original).hexdigest() == STOCK_MD5, "Expected exact original F08"

    # Bank-12 entry accepts the CFDB=E0 protocol family. CFDA=1 selects
    # another table, while CFDA=3 reaches the 3-byte table below.
    expect(original, 12, 0x53FC, "90 cf db e0 ff 64 e0 60 02 c3 22")
    expect(original, 12, 0x5407, "90 cf da e0 64 01 60 03 02 5d 73")
    expect(original, 12, 0x5D73,
           "90 cf da e0 64 03 60 03 02 68 d1 90 cf dc e0 12 3c 49")

    # CALL 3C49 consumes the return address as the pointer to table records:
    # [target_high, target_low, command_id]. No direct CALL targets exist.
    expect(original, 0, 0x3C49, "d0 83 d0 82 f8 e4 93")
    expect(original, 0, 0x3C64,
           "74 02 93 68 60 ef a3 a3 a3 80 df")
    first, end = 0x5D85, 0x5EB1
    assert (end - first) % 3 == 0
    entries: dict[int, int] = {}
    for address in range(first, end, 3):
        hi, lo, command = at(original, 12, address, 3)
        assert command not in entries, f"Duplicate command {command:02X}"
        entries[command] = (hi << 8) | lo
    assert len(entries) == 100
    assert entries[0x80] == 0x68A9
    assert entries[0x82] == 0x68B9
    assert 0x81 not in entries
    expect(original, 12, end, "00 00")

    # Both requests are conditional on CFDE=2 (role of this byte unknown).
    expect(original, 12, 0x68A9,
           "90 cf de e0 64 02 70 23 90 d1 2d e0 44 01 80 0d")
    expect(original, 12, 0x68B9,
           "90 cf de e0 b4 02 14 90 d1 2d e0 44 02 f0")

    # The accepted commands converge at 68C6 (MOVX @DPTR,A), followed by
    # helper calls and a jump to 68D4 (SETB C; RET). Failed CFDE=2 checks
    # branch directly to the same return. Carry alone is not an ACK of a
    # successful refresh request or panel operation.
    expect(original, 12, 0x68C6, "f0 12 2c 50 12 2b 9c 80 05")
    expect(original, 12, 0x68D4, "d3 22")

    # A separate bank-19 state-processing path can set both request bits.
    # 7E3B branches on D8B3 == 0x20 to 7E85, which passes R7=0x20
    # to 8BCF. That handler checks a D8B3/D8B4 transition before CALL 80A4.
    expect(original, 19, 0x7E3B,
           "90 d8 b3 e0 24 fc 60 26 24 fc 60 2d 24 f8 60 34 24 f0 60 36")
    expect(original, 19, 0x7E85, "7f 03 12 7d b5 ad 07 7f 20 80 09")
    expect(original, 19, 0x7E99, "02 8b cf")
    expect(original, 19, 0x8BD4,
           "90 d8 b3 e0 fe a3 e0 6e 60 14 ef b5 06 10 12 80 a4")
    expect(original, 19, 0x80A4, "90 c5 01 ef f0 12 0e 86")
    expect(original, 19, 0x80AF, "90 c5 01 e0 b4 20 13")
    expect(original, 19, 0x80BD, "90 d1 2d e0 44 01 f0 44 02 f0")

    return {
        "bank12_table_records": len(entries),
        "apcs_command": (0x80, entries[0x80]),
        "aocs_command": (0x82, entries[0x82]),
        "bank12_guards": ("CFDB == E0", "CFDA == 3", "CFDE == 2"),
        "bank12_return": "SETB C on guarded write and rejected operand; not a success ACK",
        "bank19_state_path": "D8B3=20 -> R7=20 -> 8BCF -> 80A4 (conditional)",
    }


if __name__ == "__main__":
    result = audit()
    print("PASS: verified stock F08 image, dispatch table, guards and state path")
    for field, value in result.items():
        print(f"{field}: {value}")
    print("No evidence yet that any command is reachable by USB, DDC/CI or OSD input.")
