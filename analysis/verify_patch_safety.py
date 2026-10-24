#!/usr/bin/env python3
"""Reproducible local patch-layout checks and complete byte/disassembly tables.

No binary is written. Requires radare2 for an independent instruction decoder;
instruction lengths are checked against oplen.OPLEN. This is not a flash-safety
certificate, global CFG recovery, or proof that cross-bank callees return.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import build_custom as custom
import build_variant as variant
from oplen import OPLEN
from control_hook import HOOK_PATCHES, SET_ENTRY, GET_ENTRY, SET_CODE, GET_CODE, verify_control_hook, apply_control_hook

REPO = Path(__file__).resolve().parents[1]
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
# Narrow raw-byte anchors; never start decoding at an arbitrary byte before a patch.
WINDOWS = {12: (0x68A9, 0x68D6), 13: (0xCA4E, 0xCB3B), 9: (0xE0BF, 0xE0F6)}


def boundaries(data, start, end):
    points = set()
    pc = start
    while pc < end:
        points.add(pc)
        pc += OPLEN[data[pc]]
    if pc != end:
        raise AssertionError(f"partial instruction at end {end:04X}")
    return points


def relative_target(data, pc):
    opcode = data[pc]
    if opcode in (0x40, 0x50, 0x60, 0x70, 0x80) or 0xD8 <= opcode <= 0xDF:
        size = 2
    elif opcode in (0x10, 0x20, 0x30, 0xD5) or 0xB4 <= opcode <= 0xBF:
        size = 3
    else:
        return None
    rel = data[pc + size - 1]
    return (pc + size + (rel if rel < 128 else rel - 256)) & 0xFFFF


def bank_crc8(data):
    """RFlash.dll 09586d4b... @10002540: CRC-8 poly 07, init/xorout 0.

    Bank includes all 65536 bytes, including erased tail. This is host flash
    readback verification, not a stored image footer or boot authentication.
    """
    if len(data) != 0x10000:
        raise ValueError("CRC input must be exactly one 64 KiB bank")
    table = []
    for value in range(256):
        for _ in range(8):
            value = ((value << 1) ^ 7) & 255 if value & 128 else (value << 1) & 255
        table.append(value)
    crc = 0
    for byte in data:
        crc = table[crc ^ byte]
    return crc


@lru_cache(maxsize=None)
def disassemble(raw, start):
    # The only writable radare2 target is anonymous memory, never a bank file.
    command = f"wx {raw.hex()} @ {start};pDj {len(raw)} @ {start};q"
    result = subprocess.run([shutil.which("r2"), "-q", "-w", "-n", "-e", "scr.color=0",
                             "-a", "8051", "-b", "8", "-c", command, "malloc://65536"],
                            check=True, capture_output=True, text=True, timeout=20)
    instructions = json.loads(result.stdout)
    reconstructed = b"".join(bytes.fromhex(i["bytes"]) for i in instructions)
    assert reconstructed == raw, "independent decoder did not cover exact input"
    pc = start
    for instruction in instructions:
        assert instruction["addr"] == pc
        assert instruction["size"] == OPLEN[int(instruction["bytes"][:2], 16)]
        pc += instruction["size"]
    return instructions


def operations(source):
    for name, sites in variant.PATCHES.items():
        modified = bytearray(source)
        variant.apply_patch(modified, name)
        yield name, sites, modified
    for function, values, site in (
        (custom.patch_apcs, (0, 1, 2, 4, 8, 36, 255), custom.APCS_SITE),
        (custom.patch_aocs, (0, 1, 750, 1500, 65535), custom.AOCS_SITE),
        (custom.patch_tss, (0, 1, 12, 36, 255), custom.TSS_SITE),
    ):
        for value in values:
            modified = bytearray(source)
            function(modified, value, [])
            bank, addr, old = site
            offset = bank * 0x10000 + addr
            new = bytes(modified[offset:offset + len(old)])
            yield f"{function.__name__}({value})", [(bank, addr, old, new, "parameter sample")], modified
    modified = bytearray(source)
    custom.patch_unlock(modified, [])
    yield "custom unlock / full-control", variant.PATCHES["unlock_cmd_gate"], modified
    modified = bytearray(source)
    custom.patch_menu_actions(modified, [])
    sites = [(9, 0xE0E2, bytes.fromhex("12 97 DB"), bytes.fromhex("12 FE FA"), "call replacement"),
             (9, 0xFEFA, b"\xff" * 36, bytes(modified[0x9FEFA:0x9FF1E]), "wrapper")]
    yield "menu-actions (unreachable prototype)", sites, modified


def verify_aocs_carry(source):
    """Exhaust both incoming carries, all operands and all D12D flag values.

    MOVX at 68C3 reloads A; no instruction up to the first call changes CY.
    Compare patched execution with stock's accepted operand=2 path.
    """
    modified = bytearray(source)
    custom.patch_unlock(modified, [])
    code = bytes(modified[0xC68BD:0xC68C7])
    assert code == bytes.fromhex("C3 74 02 90 D1 2D E0 44 02 F0")
    cases = 0
    for incoming_carry in (0, 1):
        for operand in range(256):
            for flags in range(256):
                a, carry = operand, incoming_carry
                pc, dptr, stored = 0, None, None
                while pc < len(code):
                    op = code[pc]
                    if op == 0xC3:
                        carry = 0; pc += 1
                    elif op == 0x74:
                        a = code[pc + 1]; pc += 2
                        assert (a, carry) == (2, 0)
                    elif op == 0x90:
                        dptr = int.from_bytes(code[pc+1:pc+3], 'big'); pc += 3
                    elif op == 0xE0:
                        assert dptr == 0xD12D
                        a = flags; pc += 1
                    elif op == 0x44:
                        a |= code[pc+1]; pc += 2
                    elif op == 0xF0:
                        stored = a; pc += 1
                    else:
                        raise AssertionError(f"unmodeled opcode {op:02X}")
                assert (a, carry, stored, dptr) == (flags | 2, 0, flags | 2, 0xD12D)
                cases += 1
    return cases


def verify():
    source = bytes(custom.load_source())
    carry_cases = verify_aocs_carry(source)
    hook_cases = verify_control_hook()
    assert hashlib.sha256(source).hexdigest() == SHA256
    for bank in range(20):
        path = REPO / f"analysis/banks/bank_{bank}.bin"
        assert path.read_bytes() == source[bank * 0x10000:(bank + 1) * 0x10000], str(path)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    lines = ["# Patch byte and instruction verification", "",
             f"Audited base commit: `{commit}`. Stock SHA-256: `{SHA256}`.", "",
             "All 20 extracted code banks match the stock image. Remaining 11 banks are covered by the image hash. Mutations below occur only in RAM.",
             "PASS applies to local encoding/layout only. Global stack, interrupts, bank switching,",
             "firmware integrity checks, hardware behavior and recoverability are not certified.", "",
             "`full-control` adds an offline E0/FE allowlisted XDATA/D8FE hook to the carry-safe unlock.",
             f"Injected-code interpreter passes {hook_cases} cases; external runtime reachability and cave ownership remain unproved.", ""]
    count = 0
    unique = set()
    branches = set()
    for name, sites, modified in operations(source):
        assert len(modified) == len(source)
        allowed = set()
        for bank, addr, old, new, _ in sites:
            assert len(old) == len(new)
            offset = bank * 0x10000 + addr
            assert source[offset:offset + len(old)] == old
            assert modified[offset:offset + len(new)] == new
            allowed.update(range(offset, offset + len(old)))
            if bank == 12 and addr in (0x5520, 0x5EB3):
                unique.add((bank, addr, old, new))
                # These are CCASE table DATA words, never 8051 instructions.
                assert int.from_bytes(old, 'big') in (0x5D3D, 0x68CF)
                assert int.from_bytes(new, 'big') in (GET_ENTRY, SET_ENTRY)
                lines += [f"## {name}: {bank}:{addr:04X} (Keil default pointer data)", "",
                          "| Bank:address | Stock | After | Kind |", "|---|---|---|---|",
                          *[f"| {bank}:{addr+i:04X} | {a:02X} | {b:02X} | table data |" for i, (a,b) in enumerate(zip(old,new))], ""]
                continue
            before_bank = source[bank * 0x10000:(bank + 1) * 0x10000]
            after_bank = modified[bank * 0x10000:(bank + 1) * 0x10000]
            hook = bank == 12 and addr in (SET_ENTRY, GET_ENTRY)
            start, end = (addr, addr + len(new)) if hook else (0xFEFA, 0xFF1E) if addr == 0xFEFA else WINDOWS[bank]
            before_points = boundaries(before_bank, start, end)
            after_points = boundaries(after_bank, start, end)
            assert addr in before_points and addr in after_points
            assert addr + len(old) in before_points | {end}
            assert addr + len(new) in after_points | {end}
            if addr != 0xFEFA and not hook:
                # No original entry boundary is lost, including potential incoming edges.
                assert before_points <= after_points
            for version, data, points in (("stock", before_bank, before_points), ("patched", after_bank, after_points)):
                for pc in points:
                    target = relative_target(data, pc)
                    if target is not None:
                        assert target in points, f"{bank}:{pc:04X} -> {target:04X} outside verified boundaries"
                        branches.add((bank, pc, target, version))
            # No new stack operations or direct SP writes occur in replacement blocks.
            for instruction in disassemble(new, addr):
                op = int(instruction["bytes"][:2], 16)
                assert op not in (0xC0, 0xD0, 0x32) and (op != 0x22 or hook), "unexpected stack opcode"
                if op == 0x12:
                    assert old == bytes.fromhex("12 97 DB") and new == bytes.fromhex("12 FE FA")
                assert hook or op in {0x00, 0x02, 0x12, 0x44, 0x60, 0x70, 0x7C, 0x7D,
                              0x74, 0xC3, 0x90, 0x94, 0xB4, 0xE0, 0xE4, 0xEB, 0xED, 0xEF, 0xF0}, "replacement opcode needs SP review"
            key = (bank, addr, old, new)
            if key in unique:
                continue
            unique.add(key)
            lines += [f"## {name}: {bank}:{addr:04X}", "",
                      "| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |",
                      "|---|---|---|---|---|"]
            before = disassemble(old, addr)
            after = disassemble(new, addr)

            def label(instructions, pc):
                item = next(i for i in instructions if i["addr"] <= pc < i["addr"] + i["size"])
                return f"`{item['addr']:04X}: {item['opcode']}` +{pc - item['addr']}"

            for i, (a, b) in enumerate(zip(old, new)):
                lines.append(f"| {bank}:{addr+i:04X} | {a:02X} | {b:02X} | {label(before, addr+i)} | {label(after, addr+i)} |")
            lines.append("")
        changed = {i for i, (a, b) in enumerate(zip(source, modified)) if a != b}
        assert changed <= allowed
        count += 1
    # Verify every named variant composition without calling file-writing builders.
    for name, (patches, _) in variant.VARIANTS.items():
        modified = bytearray(source)
        for patch in patches:
            variant.apply_patch(modified, patch)
        if name == "F08-unlock":
            assert sum(a != b for a, b in zip(source, modified)) == 5
        if name == 'F08-full-control':
            unlocked = bytearray(source)
            custom.patch_unlock(unlocked, [])
            assert modified != unlocked
            assert all(modified[b*65536+a:b*65536+a+len(new)] == new for b,a,old,new,_ in HOOK_PATCHES)
    full_control = bytearray(source)
    custom.patch_unlock(full_control, [])
    apply_control_hook(full_control, [])
    begin, end = 0xC68A9, 0xC68D6
    old_context = {i['addr']: i for i in disassemble(source[begin:end], 0x68A9)}
    new_context = {i['addr']: i for i in disassemble(bytes(full_control[begin:end]), 0x68A9)}
    lines += ["## Full-control surrounding disassembly", "",
              "| Bank:address | Stock bytes / instruction | After bytes / instruction |",
              "|---|---|---|"]
    for pc in sorted(old_context.keys() | new_context.keys()):
        def cell(context):
            i = context.get(pc)
            return f"`{i['bytes']}` {i['opcode']}" if i else "operand of preceding instruction"
        lines.append(f"| 12:{pc:04X} | {cell(old_context)} | {cell(new_context)} |")
    lines += ["", "## Relative branches in the audited windows", "",
              "Computed from signed rel8 and OPLEN, including JB/JNB/JBC and both DJNZ forms.",
              "Both outcomes are checked structurally even when a patched predicate is constant.", "",
              "| Bank:source | Target | Image |", "|---|---|---|"]
    for bank, pc, target, version in sorted(branches):
        lines.append(f"| {bank}:{pc:04X} | {bank}:{target:04X} | {version} |")
    lines += ["", "## Stack and scope", "",
              "Unlock and threshold replacements contain no PUSH, POP, call, RET or SP write.",
              "The menu call remains LCALL (SP +2), returning to 9:E0E5; every wrapper path",
              "tail-jumps to 9:97DB with no additional stack use. Stock dispatcher return consumes",
              "that same address (SP -2), conditional on the unchanged dispatcher/callees returning.",
              "The APCS/AOCS handlers retain calls 0:2C50 and 0:2B9C and RET at 12:68D5.",
              f"AOCS CLR C; MOV A,#2 matches the accepted stock A=2/CY=0 state; {carry_cases} cases pass.",
              "MOVX at 12:68C3 reloads A before the request update; CY remains zero at 12:68C7.",
              "Cross-bank synthetic returns and ISR stack depth are outside this local proof.",
              "An unchanged call graph does not prove absence of overflow or balanced runtime SP.", "",
              "New SET hook paths consume the existing return address once (RET); GET paths tail-jump",
              "to stock checksum/send code at 12:5D5A. No injected PUSH/POP/LCALL or SP write occurs.",
              "Unknown commands tail-jump to their original defaults. FE requests require exact length,",
              "51 header and XOR=00. SET writes only D8FE values 00/10/20; GET reads only D12D/D13D/D13E/D8FE.",
              "All selected ranges end at instruction boundaries; no trailing instruction fragments.",
              "Unchanged bytes are included in the tables. Erased FF bytes decode as MOV R7,A;",
              "that does not prove the erased region is unreachable or available for a trampoline.",
              "Parameter samples cover all named presets and endpoints; arbitrary valid values only",
              "replace immediate operands (94 xx / 7C hi 7D lo), preserving the same boundaries.",
              "patch.py validates stock identity, length, bounds, overlaps, bank selection and outputs.",
              "Arbitrary JSON still requires its own instruction/semantic audit.", "",
              "## Host per-bank verification CRC", "",
              "RFlash.dll SHA-256 09586d4b2cfd5d80b20ad3bf2ee2b01fd080260f0753e83c8ec32eaf3b0ec652",
              "implements CRC-8 (poly 07, init 00, refin/refout false, xorout 00) over each 65536-byte bank.",
              "The native comparison at 10002CFD compares this with the scaler CRC result (register 75).",
              "No stored trailer is repaired. All stock banks end in FFFF at FFFE; boot checks remain open.", "",
              "| Bank | Stock CRC-8 | Full-control prototype CRC-8 |", "|---|---|---|",
              *[f"| {b} | {bank_crc8(source[b*65536:(b+1)*65536]):02X} | {bank_crc8(full_control[b*65536:(b+1)*65536]):02X} |" for b in range(31)], "",
              f"Verified {count} transformations and {len(unique)} distinct site/replacement combinations.",
              "DO NOT FLASH. Local verification is not a finding of zero brick risk.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="also save the printed Markdown tables")
    args = parser.parse_args()
    if not shutil.which("r2"):
        parser.error("radare2 (r2) is required for independent disassembly")
    report = verify()
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
