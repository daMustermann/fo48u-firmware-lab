#!/usr/bin/env python3
"""Check the UI-only 8051 menu wrapper, including other caller inputs.

This instruction interpreter verifies branches, writes, jumps, and the exact
patch byte range. It is NOT hardware or full-system emulation.
"""

from build_custom import (
    OUT_DIR,
    MENU_UI_CALL_SITE,
    MENU_UI_TRAMPOLINE,
    MENU_TRAMPOLINE_SIZE,
    file_offset,
    load_source,
    patch_menu_actions,
)
import base64
import os
import verify_facts

# Recover the (now consolidated) menu-reachability audit callable.
_audit_src = base64.b64decode(
    verify_facts._AUDITS["audit_menu_reachability.py"]
).decode("utf-8")
_audit_ns = {"__name__": "audit_menu_reachability",
             "__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "audit_menu_reachability.py")}
exec(compile(_audit_src, "audit_menu_reachability.py", "exec"), _audit_ns)
audit = _audit_ns["audit"]


def selector_evidence(source):
    """True service-record selectors, distinct from a physical selection event."""
    bank = source[9 * 65536:10 * 65536]
    assert bank[0xE481:0xE49A] == bytes.fromhex(
        "25 E0 25 E0 24 83 F5 82 E4 34 97 F5 83 E4 93 FB 74 01 93 FA 74 02 93 F9 22")
    assert bank[0xE4B8:0xE4C7] == bytes.fromhex("E0 75 F0 02 A4 F5 82 85 F0 83 12 36 81 FF 22")
    assert bank[0xE4C7:0xE4DA] == bytes.fromhex("ED 75 F0 02 A4 FF E9 2F F9 EA 35 F0 FA 90 00 01 02 36 81")
    pages = []
    for page in range(5):
        record = bank[0x9783 + 4*page:0x9787 + 4*page]
        space, hi, lo, count = record
        assert space == 0xFF
        pointer = hi * 256 + lo
        assert pointer >= 0x9747 and (pointer - 0x9747) % 2 == 0
        first = (pointer - 0x9747) // 2
        pages.append(list(range(first, first + count)))
    assert sorted(item for page in pages for item in page) == list(range(30))
    assert pages[3] == list(range(23, 29))
    for item, handler in ((23, 0xA14C), (24, 0xA1C0)):
        assert bank[0x9747+2*item:0x9749+2*item] == bytes((item, 1))
        assert bank[0x97F0+3*item:0x97F3+3*item] == bytes((2, handler >> 8, handler & 255))
    return {"page": 3, "records": ["9:9775", "9:9777"],
            "page_pointer_selector": "9:E481", "item_id_selector": "9:E4B8",
            "item_flag_selector": "9:E4C7", "dispatcher": "9:97DB",
            "limitation": "page enumeration is reachable; deliberate joystick selection remains unproved"}


def run_wrapper(firmware: bytes, item: int, key: int, event: int, flags: int) -> tuple[int, int]:
    xdata = {0xD12D: flags}
    pc, dptr, a = MENU_UI_TRAMPOLINE, 0, 0
    for _ in range(30):
        opcode = firmware[file_offset(9, pc)]
        if opcode in (0xED, 0xEB, 0xEF):  # mov a,r5 / mov a,r3 / mov a,r7
            a = {0xED: key, 0xEB: event, 0xEF: item}[opcode]
            pc += 1
        elif opcode in (0x60, 0x70):  # jz / jnz rel8
            rel = firmware[file_offset(9, pc + 1)]
            take = (a == 0) if opcode == 0x60 else (a != 0)
            pc = pc + 2 + (rel - 256 if rel >= 128 else rel) if take else pc + 2
        elif opcode == 0xB4:  # cjne a,#imm8,rel8
            imm = firmware[file_offset(9, pc + 1)]
            rel = firmware[file_offset(9, pc + 2)]
            pc = pc + 3 + (rel - 256 if rel >= 128 else rel) if a != imm else pc + 3
        elif opcode == 0x90:  # mov dptr,#imm16
            dptr = int.from_bytes(firmware[file_offset(9, pc + 1):file_offset(9, pc + 3)], 'big')
            pc += 3
        elif opcode == 0xE0:  # movx a,@dptr
            a = xdata[dptr]
            pc += 1
        elif opcode == 0x44:  # orl a,#imm8
            a |= firmware[file_offset(9, pc + 1)]
            pc += 2
        elif opcode == 0xF0:  # movx @dptr,a
            xdata[dptr] = a
            pc += 1
        elif opcode == 0x02:  # ljmp addr16 (stock dispatcher)
            destination = int.from_bytes(
                firmware[file_offset(9, pc + 1):file_offset(9, pc + 3)], 'big'
            )
            return destination, xdata[0xD12D]
        else:
            raise AssertionError(f"unexpected opcode {opcode:02X} at {pc:04X}")
        assert MENU_UI_TRAMPOLINE <= pc < MENU_UI_TRAMPOLINE + MENU_TRAMPOLINE_SIZE, hex(pc)
    raise AssertionError("wrapper did not jump to the stock dispatcher")


def main() -> None:
    source = load_source()
    print("PASS: upstream service selectors:", selector_evidence(source))
    reachability = audit(source)
    assert reachability["reachable_action_ids"] == [11, 14]
    modified = bytearray(source)
    patch_menu_actions(modified, [])
    site = MENU_UI_CALL_SITE[1]
    assert modified[file_offset(9, site):file_offset(9, site + 3)] == bytes.fromhex('12 FE FA')
    # Drawing/host-command dispatcher callers stay on the original code.
    for other in (0xD4D6, 0xD584, 0xF24C):
        assert modified[file_offset(9, other):file_offset(9, other + 3)] == bytes.fromhex('12 97 DB')
    for handler in (0xA161, 0xA1D5):
        assert modified[file_offset(9, handler):file_offset(9, handler + 3)] == bytes.fromhex('90 C6 93')
    assert modified[file_offset(9, 0x97DB):file_offset(9, 0x97DB + 14)] == bytes.fromhex(
        '90 C6 93 EB F0 EF B4 1E 00 40 03 02 A4 9C'
    )
    assert modified[file_offset(9, 0xE0BF):file_offset(9, 0xE0BF + 15)] == bytes.fromhex(
        '90 C6 8F E0 FD B4 01 07 E4 90 C6 92 F0 80 06'
    )
    cases = 0
    for item in (*range(31), 255):
        for key in (0, 1, 255):
            for event in (0, 1, 2, 255):
                for flags in (0, 1, 2, 3, 0x40, 0xFF):
                    dest, updated = run_wrapper(modified, item, key, event, flags)
                    mask = {23: 1, 24: 2}.get(item, 0) if key != 0 and event == 0 else 0
                    assert dest == 0x97DB, (item, key, event, dest)
                    assert updated == flags | mask, (item, key, event, flags, updated)
                    cases += 1

    expected_changed = set(range(file_offset(9, site + 1), file_offset(9, site + 3)))
    expected_changed.update(range(file_offset(9, MENU_UI_TRAMPOLINE),
                                  file_offset(9, MENU_UI_TRAMPOLINE + MENU_TRAMPOLINE_SIZE)))
    actual_changed = {i for i, (before, after) in enumerate(zip(source, modified)) if before != after}
    assert actual_changed == expected_changed
    # When the standalone research image is present, require an exact match
    # against freshly generated bytes (no stale or differently patched image).
    research_image = OUT_DIR / "F08-menu-ui-scoped.bin"
    if research_image.exists():
        assert research_image.read_bytes() == modified, "on-disk UI-scoped image drifted"
    print(f"PASS: isolated wrapper interpreter, {cases} item/key/event/flag cases, "
          "other callers/handlers unchanged, exact patch byte range, image matches")
    print("FAILS REACHABILITY: wrapper cannot receive APCS=23/AOCS=24 through E057. "
          "UNREACHABLE PROTOTYPE / DO NOT FLASH")


if __name__ == "__main__":
    main()
