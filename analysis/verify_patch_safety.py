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


def verify():
    source = bytes(custom.load_source())
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
             "`full-control` changes exactly five bytes and is identical to `unlock_cmd_gate`.",
             "There is no additional XDATA/event-control firmware implementation in that profile.", ""]
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
            before_bank = source[bank * 0x10000:(bank + 1) * 0x10000]
            after_bank = modified[bank * 0x10000:(bank + 1) * 0x10000]
            start, end = (0xFEFA, 0xFF1E) if addr == 0xFEFA else WINDOWS[bank]
            before_points = boundaries(before_bank, start, end)
            after_points = boundaries(after_bank, start, end)
            assert addr in before_points and addr in after_points
            assert addr + len(old) in before_points | {end}
            assert addr + len(new) in after_points | {end}
            if addr != 0xFEFA:
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
                assert op not in (0xC0, 0xD0, 0x22, 0x32), "unexpected stack opcode"
                if op == 0x12:
                    assert old == bytes.fromhex("12 97 DB") and new == bytes.fromhex("12 FE FA")
                assert op in {0x00, 0x02, 0x12, 0x44, 0x60, 0x70, 0x7C, 0x7D,
                              0x90, 0x94, 0xB4, 0xE0, 0xE4, 0xEB, 0xED, 0xEF, 0xF0}, "replacement opcode needs SP review"
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
        if name in ("F08-unlock", "F08-full-control"):
            assert sum(a != b for a, b in zip(source, modified)) == 5
    full_control = bytearray(source)
    custom.patch_unlock(full_control, [])
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
              "Removing CJNE also removes its carry update: an accepted stock AOCS operand",
              "clears C, whereas CLR A; NOP; NOP preserves incoming C. Callee sensitivity",
              "to that difference remains unproven; encoding safety is not semantic equivalence.",
              "Cross-bank synthetic returns and ISR stack depth are outside this local proof.",
              "An unchanged call graph does not prove absence of overflow or balanced runtime SP.", "",
              "All selected ranges end at instruction boundaries; no trailing instruction fragments.",
              "Unchanged bytes are included in the tables. Erased FF bytes decode as MOV R7,A;",
              "that does not prove the erased region is unreachable or available for a trampoline.",
              "Parameter samples cover all named presets and endpoints; arbitrary valid values only",
              "replace immediate operands (94 xx / 7C hi 7D lo), preserving the same boundaries.",
              "Caller-provided JSON for patch.py is unbounded and has no universal byte inventory.",
              "It lacks equal-length, bank, range, image-identity and instruction-layout guards.", "",
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
