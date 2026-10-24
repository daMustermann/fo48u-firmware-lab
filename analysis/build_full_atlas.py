#!/usr/bin/env python3
"""Build a complete 20-bank firmware atlas for the FO48U F08 image.

Decodes Keil C51 inline switch tables that Ghidra truncated and cross-references
their case targets with bank/function/XDATA information.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BANKS_DIR = REPO / "analysis" / "banks"
DUMPS_DIR = REPO / "analysis" / "dumps"
TRAMPOLINE_PATH = REPO / "analysis" / "trampoline_map.json"
OUT_DIR = REPO / "analysis" / "atlas"

BANK_SIZE = 0x10000
NUM_BANKS = 20


def load_banks() -> dict[int, bytes]:
    banks = {}
    for bank in range(NUM_BANKS):
        path = BANKS_DIR / f"bank_{bank}.bin"
        banks[bank] = path.read_bytes()
    return banks


def load_trampoline_map() -> dict:
    if TRAMPOLINE_PATH.exists():
        return json.loads(TRAMPOLINE_PATH.read_text(encoding="utf-8"))
    return {}


TRAMPOLINE_MAP = load_trampoline_map()


def decode_ccase_table(bank_bytes: bytes, table_offset: int, max_cases: int = 128) -> dict:
    """Decode a Keil C51 ?C?CCASE inline 8-bit switch table starting at call_pc + 3."""
    pos = table_offset
    cases = []
    for _ in range(max_cases):
        if pos + 4 > len(bank_bytes):
            break
        t_hi, t_lo = bank_bytes[pos], bank_bytes[pos + 1]
        if t_hi == 0x00 and t_lo == 0x00:
            def_hi, def_lo = bank_bytes[pos + 2], bank_bytes[pos + 3]
            return {
                "kind": "CCASE_8BIT",
                "table_offset": f"0x{table_offset:04X}",
                "cases": cases,
                "default_target": f"0x{(def_hi << 8) | def_lo:04X}",
                "end_offset": f"0x{pos + 4:04X}",
            }
        case_val = bank_bytes[pos + 2]
        cases.append({
            "case": f"0x{case_val:02X}",
            "case_dec": case_val,
            "target": f"0x{(t_hi << 8) | t_lo:04X}",
        })
        pos += 3
    return {"kind": "CCASE_INCOMPLETE", "cases": cases}


def decode_icase_table(bank_bytes: bytes, table_offset: int, max_cases: int = 128) -> dict:
    """Decode a Keil C51 ?C?ICASE inline 16-bit switch table starting at call_pc + 3."""
    pos = table_offset
    cases = []
    for _ in range(max_cases):
        if pos + 4 > len(bank_bytes):
            break
        t_hi, t_lo = bank_bytes[pos], bank_bytes[pos + 1]
        if t_hi == 0x00 and t_lo == 0x00:
            def_hi, def_lo = bank_bytes[pos + 2], bank_bytes[pos + 3]
            return {
                "kind": "ICASE_16BIT",
                "table_offset": f"0x{table_offset:04X}",
                "cases": cases,
                "default_target": f"0x{(def_hi << 8) | def_lo:04X}",
                "end_offset": f"0x{pos + 4:04X}",
            }
        c_hi, c_lo = bank_bytes[pos + 2], bank_bytes[pos + 3]
        c_val = (c_hi << 8) | c_lo
        cases.append({
            "case": f"0x{c_val:04X}",
            "case_dec": c_val,
            "target": f"0x{(t_hi << 8) | t_lo:04X}",
        })
        pos += 4
    return {"kind": "ICASE_INCOMPLETE", "cases": cases}


def decode_lcase_table(bank_bytes: bytes, table_offset: int, max_cases: int = 128) -> dict:
    """Decode a Keil C51 long (6-byte entry) switch table."""
    pos = table_offset
    cases = []
    for _ in range(max_cases):
        if pos + 6 > len(bank_bytes):
            break
        t_hi, t_lo = bank_bytes[pos], bank_bytes[pos + 1]
        if t_hi == 0x00 and t_lo == 0x00:
            def_hi, def_lo = bank_bytes[pos + 2], bank_bytes[pos + 3]
            return {
                "kind": "LCASE_6BYTE",
                "table_offset": f"0x{table_offset:04X}",
                "cases": cases,
                "default_target": f"0x{(def_hi << 8) | def_lo:04X}",
                "end_offset": f"0x{pos + 6:04X}",
            }
        case_val = int.from_bytes(bank_bytes[pos + 2:pos + 6], "big")
        cases.append({
            "case": f"0x{case_val:08X}",
            "case_dec": case_val,
            "target": f"0x{(t_hi << 8) | t_lo:04X}",
        })
        pos += 6
    return {"kind": "LCASE_INCOMPLETE", "cases": cases}


# Helper classification discovered in bank_0.bin.
SWITCH_HELPERS = {
    0x3C49: ("CCASE", "CCASE_8BIT", decode_ccase_table, 3),
    0x3C6F: ("ICASE", "ICASE_16BIT", decode_icase_table, 4),
    0x3C9C: ("LCASE", "LCASE_6BYTE", decode_lcase_table, 6),
}

INDEXED_HELPERS = {
    0x3F1C: 2,
    0x3F35: 4,
}


def bank_of_absolute(file_offset: int) -> int:
    return file_offset // BANK_SIZE


def resolve_call(bank: int, target: int) -> str:
    key = f"{bank}:{target:04X}" if False else None
    # Trampoline map uses "bank:addr" keys with lowercase hex in existing file.
    for map_key, info in TRAMPOLINE_MAP.items():
        if map_key == f"{bank}:{target:04X}" or map_key.lower() == f"{bank}:{target:04x}":
            if isinstance(info, dict):
                if "target" in info:
                    return info["target"]
                if "type" in info:
                    return f"{info.get('type', '')}"
            return str(info)
    if target == 0x2DB2:
        return "12:539D"
    return f"{bank}:{target:04X}"


def parse_decompiled_functions(bank: int) -> list[dict]:
    path = DUMPS_DIR / f"decompiled_bank{bank}.txt"
    if not path.exists():
        return []
    functions = []
    pattern = re.compile(r"FUNCTION:\s+f_([0-9a-fA-F]+)\s+@\s+CODE:([0-9a-fA-F]+)")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if match:
            addr = int(match.group(2), 16)
            functions.append({"name": f"f_{match.group(1)}", "address": addr, "address_hex": f"0x{addr:04X}"})
    # De-duplicate by address while preserving order.
    seen = set()
    unique = []
    for func in functions:
        if func["address"] in seen:
            continue
        seen.add(func["address"])
        unique.append(func)
    return unique


def containing_function(functions: list[dict], address: int) -> str | None:
    selected = None
    for func in functions:
        if func["address"] <= address:
            selected = func
        else:
            break
    if selected is None:
        return None
    return f"{selected['name']}@0x{selected['address']:04X}"


def scan_xdata_touches(code: bytes, start: int, limit: int = 256) -> dict:
    reads = set()
    writes = set()
    calls = []
    end = min(len(code), start + limit)
    pos = start
    while pos < end:
        op = code[pos]
        if op == 0x90 and pos + 2 < len(code):
            dptr = (code[pos + 1] << 8) | code[pos + 2]
            nxt = code[pos + 3] if pos + 3 < len(code) else None
            if nxt == 0xE0:
                reads.add(dptr)
            elif nxt == 0xF0:
                writes.add(dptr)
            pos += 3
            continue
        if op == 0x12 and pos + 2 < len(code):
            target = (code[pos + 1] << 8) | code[pos + 2]
            calls.append(target)
            pos += 3
            continue
        if op == 0x22:  # RET
            break
        pos += 1
    return {
        "xdata_reads": sorted(f"0x{x:04X}" for x in reads),
        "xdata_writes": sorted(f"0x{x:04X}" for x in writes),
        "calls": [f"0x{x:04X}" for x in calls],
    }


def main() -> None:
    banks = load_banks()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    atlas = {
        "image": {
            "path": "firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin",
            "banks": NUM_BANKS,
            "bank_size": BANK_SIZE,
        },
        "helpers": {f"0x{addr:04X}": name for addr, (name, *_) in SWITCH_HELPERS.items()},
        "banks_summary": {},
        "functions": {},
        "switches": [],
        "indexed_helpers": [],
        "isr_vectors": {},
        "cross_bank_calls": [],
    }

    all_cross_calls = set()

    for bank in range(NUM_BANKS):
        data = banks[bank]
        funcs = parse_decompiled_functions(bank)
        atlas["functions"][str(bank)] = funcs
        atlas["banks_summary"][str(bank)] = {
            "size": len(data),
            "function_count": len(funcs),
        }

        # Cross-bank / helper calls.
        pos = 0
        while pos < len(data) - 2:
            if data[pos] == 0x12:
                target = (data[pos + 1] << 8) | data[pos + 2]
                if target in SWITCH_HELPERS or target in INDEXED_HELPERS:
                    helper_name, kind_name, decoder, entry_size = (
                        (SWITCH_HELPERS[target][0], SWITCH_HELPERS[target][1], SWITCH_HELPERS[target][2], SWITCH_HELPERS[target][3])
                        if target in SWITCH_HELPERS
                        else (f"INDEXED_{INDEXED_HELPERS[target]}", "INDEXED_JUMPTABLE", None, INDEXED_HELPERS[target])
                    )
                    table_offset = pos + 3
                    if decoder is not None:
                        decoded = decoder(data, table_offset)
                    else:
                        # Raw indexed jump table.
                        entries = []
                        p = table_offset
                        for i in range(32):
                            if p + entry_size > len(data):
                                break
                            ptr = int.from_bytes(data[p:p + entry_size], "big")
                            if entry_size == 2 and ptr == 0:
                                break
                            entries.append({"index": i, "target": f"0x{ptr:04X}"})
                            p += entry_size
                        decoded = {
                            "kind": "INDEXED_JUMPTABLE",
                            "table_offset": f"0x{table_offset:04X}",
                            "entry_size": entry_size,
                            "entries": entries,
                            "end_offset": f"0x{p:04X}",
                        }

                    case_targets = []
                    if "cases" in decoded:
                        for case in decoded["cases"]:
                            target_addr = int(case["target"], 16)
                            case_targets.append(target_addr)
                            case["target_function"] = containing_function(funcs, target_addr)
                            analysis = scan_xdata_touches(data, target_addr, 192)
                            case["target_analysis"] = analysis
                    if "default_target" in decoded:
                        default_addr = int(decoded["default_target"], 16)
                        decoded["default_function"] = containing_function(funcs, default_addr)
                        decoded["default_analysis"] = scan_xdata_touches(data, default_addr, 128)

                    atlas["switches"].append({
                        "bank": bank,
                        "call_offset": f"0x{pos:04X}",
                        "helper": f"0x{target:04X}",
                        "helper_kind": helper_name,
                        **decoded,
                    })
                    if target in INDEXED_HELPERS:
                        atlas["indexed_helpers"].append({
                            "bank": bank,
                            "call_offset": f"0x{pos:04X}",
                            "helper": f"0x{target:04X}",
                            "entry_size": entry_size,
                        })
                else:
                    resolved = resolve_call(bank, target)
                    all_cross_calls.add((bank, pos, target, resolved))
                pos += 3
                continue
            pos += 1

    # ISR vectors in bank 0.
    vector_names = {
        0x0003: "IE0 external int 0",
        0x000B: "TF0 timer 0",
        0x0013: "IE1 external int 1",
        0x001B: "TF1 timer 1",
        0x0023: "RI/TI UART0",
        0x002B: "TF2 timer 2 / UART1",
    }
    bank0 = banks[0]
    for vector, name in vector_names.items():
        target = None
        if bank0[vector] == 0x02 and vector + 2 < len(bank0):
            target = (bank0[vector + 1] << 8) | bank0[vector + 2]
        entry = {"name": name, "vector": f"0x{vector:04X}", "raw": bank0[vector:vector + 3].hex(" ")}
        if target is not None:
            entry["target"] = f"0x{target:04X}"
            entry["target_analysis"] = scan_xdata_touches(bank0, target, 512)
        atlas["isr_vectors"][f"0x{vector:04X}"] = entry

    # Cross-bank call summary.
    for bank, pos, target, resolved in sorted(all_cross_calls):
        atlas["cross_bank_calls"].append({
            "bank": bank,
            "offset": f"0x{pos:04X}",
            "target": f"0x{target:04X}",
            "resolved": resolved,
        })

    # Write JSON atlas.
    json_path = OUT_DIR / "firmware_atlas.json"
    json_path.write_text(json.dumps(atlas, indent=2), encoding="utf-8")

    # Write human-readable switch table catalog.
    lines = ["# Keil C51 Inline Switch Tables", "", f"Total decoded switch sites: {len(atlas['switches'])}", ""]
    for sw in atlas["switches"]:
        lines.append(f"## bank {sw['bank']} call {sw['call_offset']} helper {sw['helper']} ({sw['helper_kind']})")
        lines.append(f"- kind: {sw.get('kind')}")
        lines.append(f"- table offset: {sw.get('table_offset')}")
        lines.append(f"- default target: {sw.get('default_target')} ({sw.get('default_function')})")
        lines.append(f"- cases: {len(sw.get('cases', sw.get('entries', [])))}")
        for case in sw.get("cases", []):
            lines.append(
                f"  - case {case['case']} -> {case['target']} "
                f"({case.get('target_function')}) reads={case.get('target_analysis', {}).get('xdata_reads', [])} "
                f"writes={case.get('target_analysis', {}).get('xdata_writes', [])}"
            )
        lines.append("")
    (OUT_DIR / "SWITCH_TABLES.md").write_text("\n".join(lines), encoding="utf-8")

    # Bank summary.
    summary_lines = ["# Bank Summary", ""]
    for bank in range(NUM_BANKS):
        summary_lines.append(f"## Bank {bank}")
        summary_lines.append(f"- size: {BANK_SIZE} bytes")
        summary_lines.append(f"- decoded functions: {atlas['banks_summary'][str(bank)]['function_count']}")
        bank_switches = [s for s in atlas["switches"] if s["bank"] == bank]
        summary_lines.append(f"- switch sites: {len(bank_switches)}")
        if bank_switches:
            summary_lines.append("- switch helpers: " + ", ".join(sorted({s["helper"] for s in bank_switches})))
        summary_lines.append("")
    (OUT_DIR / "BANK_SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Switch sites: {len(atlas['switches'])}")
    print(f"Functions: {sum(len(v) for v in atlas['functions'].values())}")


if __name__ == "__main__":
    main()
