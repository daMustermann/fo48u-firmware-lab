#!/usr/bin/env python3
"""Prove why F08's E0E2 dispatcher hook cannot handle APCS/AOCS.

This is a deliberately narrow audit of direct calls in the ORIGINAL bank-9
image, their immediate arguments, the menu table and the comparison gate.
It is not a global 8051 control-flow analysis or proof about indirect calls.
"""

from build_custom import file_offset, load_source

BANK = 9
TARGET = 0xE057
CALLERS = {0xF77C: 0x0B, 0xF787: 0x0B, 0xF78E: 0x0E}


def at(data: bytes, addr: int, size: int) -> bytes:
    off = file_offset(BANK, addr)
    return bytes(data[off:off + size])


def expect(data: bytes, addr: int, expected: str) -> None:
    want = bytes.fromhex(expected)
    got = at(data, addr, len(want))
    assert got == want, (f"9:{addr:04X}", got.hex(" "), want.hex(" "))


def audit(source: bytes | None = None) -> dict[str, object]:
    data = source if source is not None else bytes(load_source())
    bank = bytes(data[file_offset(BANK, 0):file_offset(BANK + 1, 0)])
    direct_calls = {i for i in range(len(bank) - 2)
                    if bank[i:i + 3] == bytes.fromhex("12 E0 57")}
    assert direct_calls == set(CALLERS), sorted(direct_calls)
    for site, action in CALLERS.items():
        expect(data, site - 2, f"7F {action:02X} 12 E0 57")

    # The routine saves the caller's R7 as the requested action ID.
    expect(data, 0xE057, "90 C6 8E EF F0")
    # Candidate low byte of the little-endian string ID comes from the page's
    # 2-byte menu table (E4B8). The helper ends with MOV R7,A; RET.
    expect(data, 0xE4B8, "E0 75 F0 02 A4 F5 82 85 F0 83 12 36 81 FF 22")
    # Mismatched candidates skip the later dispatcher call at E0E2.
    expect(data, 0xE08C, "90 C6 8E E0 6F 70 66")
    expect(data, 0xE0D7, "90 C6 90 12 E4 B8 90 C6 92 E0 FB 12 97 DB")

    # 30 little-endian string IDs; the low bytes index service actions too.
    entries = [at(data, 0x9747 + 2 * i, 2) for i in range(30)]
    assert [pair[0] for pair in entries] == list(range(30))
    assert entries[23] == b"\x17\x01"
    assert entries[24] == b"\x18\x01"
    reachable = sorted(set(CALLERS.values()))
    assert 23 not in reachable and 24 not in reachable
    return {"direct_callers": CALLERS, "reachable_action_ids": reachable,
            "unreachable_items": [23, 24]}


if __name__ == "__main__":
    evidence = audit()
    print("PASS: direct E057 caller inputs:", evidence["direct_callers"])
    print("E0E2 dispatcher can receive only these action IDs via direct E057 calls:",
          evidence["reachable_action_ids"])
    print("APCS=23/AOCS=24 are unreachable through the E0E2 prototype hook.")
    print("F08-menu-ui-scoped.bin: INERT PROTOTYPE / DO NOT FLASH")
