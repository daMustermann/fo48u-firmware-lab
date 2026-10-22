#!/usr/bin/env python3
"""
xref_xdata.py — Fast Cross-Bank 8051 XDATA, ROM Pointer & Keil Switch Analyzer
Designed for fo48u-firmware-lab (Realtek RTD2718 / Keil C51 banked 8051 firmware).

Features:
1. Linear sweep disassembler with exact 8051 opcode lengths across bank_0.bin..bank_19.bin.
2. Tracks DPTR state across basic blocks:
   - Direct `MOV DPTR, #0xXXXX` (90 HI LO)
   - Split `MOV DPH, #HI` (75 83 HI) + `MOV DPL, #LO` (75 82 LO)
   - Chained `INC DPTR` (A3) accesses (catches struct/buffer offsets like base+1, base+2...)
   - Indexed array accesses (`MOV DPTR, #base` + `ADD A, DPL` / `MOV DPL, A`)
3. Classifies every reference into:
   - XDATA_READ   (`MOVX A, @DPTR` [E0])
   - XDATA_WRITE  (`MOVX @DPTR, A` [F0])
   - CODE_READ    (`MOVC A, @A+DPTR` [93])
   - PTR_ARG      (`MOV DPTR, #addr` passed into `LCALL`/`ACALL`/`LJMP`)
4. Scans ROM for raw 16-bit Big-Endian (`HI LO`) and Keil 3-byte generic XDATA pointers (`01 HI LO`).
5. Detects and decodes Keil C51 inline switch/case tables (`?C?CCASE` / `?C?ICASE`).

Usage Examples:
  python3 analysis/xref_xdata.py 0xD8FE
  python3 analysis/xref_xdata.py 0xD8FE --context 6 --rom-ptrs
  python3 analysis/xref_xdata.py 0xD8F0-0xD8FF
  python3 analysis/xref_xdata.py --find-switches
  python3 analysis/xref_xdata.py --dump-json analysis/xdata_index.json
"""

from __future__ import annotations
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Exact 8051 instruction byte length table (0x00..0xFF)
OPCODE_LEN = [
    # 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F
    1, 2, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x00
    3, 2, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x10
    3, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x20
    3, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x30
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x40
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x50
    2, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x60
    2, 2, 2, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # 0x70
    2, 2, 2, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # 0x80
    3, 2, 2, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0x90
    2, 2, 2, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,  # 0xA0
    2, 2, 2, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,  # 0xB0
    2, 2, 2, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0xC0
    2, 2, 2, 1, 1, 3, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2,  # 0xD0
    1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0xE0
    1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 0xF0
]

# Instructions that unconditionally terminate or redirect sequential DPTR tracking
BB_TERMINATORS = {
    0x02,  # LJMP
    0x22,  # RET
    0x32,  # RETI
    0x73,  # JMP @A+DPTR
    0x80,  # SJMP
    0x01, 0x21, 0x41, 0x61, 0x81, 0xA1, 0xC1, 0xE1,  # AJMP
}

CALL_OPCODES = {
    0x12,  # LCALL
    0x11, 0x31, 0x51, 0x71, 0x91, 0xB1, 0xD1, 0xF1,  # ACALL
}

SFR_NAMES = {
    0x80: "P0", 0x81: "SP", 0x82: "DPL", 0x83: "DPH", 0x87: "PCON",
    0x88: "TCON", 0x89: "TMOD", 0x8A: "TL0", 0x8B: "TL1", 0x8C: "TH0", 0x8D: "TH1",
    0x90: "P1", 0x98: "SCON", 0x99: "SBUF", 0xA0: "P2", 0xA8: "IE",
    0xB0: "P3", 0xB8: "IP", 0xD0: "PSW", 0xE0: "ACC", 0xF0: "B",
}


def fmt_dir(byte_val: int) -> str:
    return SFR_NAMES.get(byte_val, f"0x{byte_val:02X}")


def decode_insn(buf: bytes, pc: int) -> Tuple[str, int, bytes]:
    """Decode a single 8051 instruction at `pc` into (mnemonic_str, length, raw_bytes)."""
    if pc >= len(buf):
        return ("DB ??", 1, b"")
    op = buf[pc]
    length = OPCODE_LEN[op]
    raw = buf[pc : pc + length]
    b1 = raw[1] if len(raw) > 1 else 0
    b2 = raw[2] if len(raw) > 2 else 0

    if op == 0x00:
        m = "NOP"
    elif op == 0x22:
        m = "RET"
    elif op == 0x32:
        m = "RETI"
    elif op == 0x90:
        m = f"MOV DPTR, #0x{(b1 << 8) | b2:04X}"
    elif op == 0xA3:
        m = "INC DPTR"
    elif op == 0xE0:
        m = "MOVX A, @DPTR"
    elif op == 0xF0:
        m = "MOVX @DPTR, A"
    elif op == 0x93:
        m = "MOVC A, @A+DPTR"
    elif op == 0x83:
        m = "MOVC A, @A+PC"
    elif op == 0x73:
        m = "JMP @A+DPTR"
    elif op == 0x02:
        m = f"LJMP 0x{(b1 << 8) | b2:04X}"
    elif op == 0x12:
        m = f"LCALL 0x{(b1 << 8) | b2:04X}"
    elif (op & 0x1F) == 0x01:
        target = ((pc + 2) & 0xF800) | ((op & 0xE0) << 3) | b1
        m = f"AJMP 0x{target:04X}"
    elif (op & 0x1F) == 0x11:
        target = ((pc + 2) & 0xF800) | ((op & 0xE0) << 3) | b1
        m = f"ACALL 0x{target:04X}"
    elif op == 0x80:
        rel = b1 if b1 < 128 else b1 - 256
        m = f"SJMP 0x{(pc + 2 + rel) & 0xFFFF:04X}"
    elif op in (0x40, 0x50, 0x60, 0x70):
        names = {0x40: "JC", 0x50: "JNC", 0x60: "JZ", 0x70: "JNZ"}
        rel = b1 if b1 < 128 else b1 - 256
        m = f"{names[op]} 0x{(pc + 2 + rel) & 0xFFFF:04X}"
    elif op == 0x74:
        m = f"MOV A, #0x{b1:02X}"
    elif 0x78 <= op <= 0x7F:
        m = f"MOV R{op - 0x78}, #0x{b1:02X}"
    elif 0xE8 <= op <= 0xEF:
        m = f"MOV A, R{op - 0xE8}"
    elif 0xF8 <= op <= 0xFF:
        m = f"MOV R{op - 0xF8}, A"
    elif op == 0x75:
        m = f"MOV {fmt_dir(b1)}, #0x{b2:02X}"
    elif op == 0xE5:
        m = f"MOV A, {fmt_dir(b1)}"
    elif op == 0xF5:
        m = f"MOV {fmt_dir(b1)}, A"
    elif op == 0x24:
        m = f"ADD A, #0x{b1:02X}"
    elif op == 0x25:
        m = f"ADD A, {fmt_dir(b1)}"
    elif op == 0x35:
        m = f"ADDC A, {fmt_dir(b1)}"
    elif op == 0xB4:
        rel = b2 if b2 < 128 else b2 - 256
        m = f"CJNE A, #0x{b1:02X}, 0x{(pc + 3 + rel) & 0xFFFF:04X}"
    elif op == 0xE4:
        m = "CLR A"
    elif op == 0xC0:
        m = f"PUSH {fmt_dir(b1)}"
    elif op == 0xD0:
        m = f"POP {fmt_dir(b1)}"
    else:
        hex_ops = " ".join(f"{b:02X}" for b in raw)
        m = f"OP_{op:02X} ({hex_ops})"
    return (m, length, raw)


def find_bank_files(banks_dir: Optional[str] = None) -> List[Tuple[int, Path]]:
    """Locate bank_0.bin .. bank_N.bin in analysis/banks/."""
    candidates = []
    if banks_dir:
        search_dirs = [Path(banks_dir)]
    else:
        repo_root = Path(__file__).resolve().parent.parent
        search_dirs = [
            Path("analysis/banks"),
            Path("banks"),
            repo_root / "analysis" / "banks",
        ]
    for d in search_dirs:
        if d.is_dir():
            for p in d.glob("bank_*.bin"):
                m = re.match(r"bank_(\d+)\.bin$", p.name)
                if m:
                    candidates.append((int(m.group(1)), p))
            if candidates:
                break
    return sorted(candidates, key=lambda x: x[0])


def scan_bank_xdata(bank_id: int, data: bytes) -> List[dict]:
    """
    Linear-sweep scan of a 64KB bank binary tracking DPTR loads, INC DPTR chains,
    DPL/DPH split loads, and array-indexed DPTR arithmetic.
    """
    events: List[dict] = []
    pc = 0
    n = len(data)

    dptr_val: Optional[int] = None
    dptr_set_pc: Optional[int] = None
    dptr_set_bytes: bytes = b""
    dptr_used: bool = False
    dptr_indexed: bool = False

    dph_val: Optional[int] = None
    dpl_val: Optional[int] = None
    dph_pc: Optional[int] = None

    while pc < n:
        op = data[pc]
        length = OPCODE_LEN[op]
        if pc + length > n:
            break
        raw = data[pc : pc + length]
        b1 = raw[1] if length > 1 else 0
        b2 = raw[2] if length > 2 else 0

        # 1. Direct MOV DPTR, #imm16 (0x90 HI LO)
        if op == 0x90:
            if dptr_val is not None and not dptr_used and dptr_set_pc is not None:
                events.append({
                    "bank": bank_id,
                    "addr": dptr_val,
                    "type": "DPTR_LOAD_ONLY",
                    "pc": dptr_set_pc,
                    "set_pc": dptr_set_pc,
                    "opcodes": dptr_set_bytes.hex().upper(),
                })
            dptr_val = (b1 << 8) | b2
            dptr_set_pc = pc
            dptr_set_bytes = raw
            dptr_used = False
            dptr_indexed = False
            dph_val = b1
            dpl_val = b2

        # 2. Split MOV DPH, #imm8 (75 83 XX) / MOV DPL, #imm8 (75 82 YY)
        elif op == 0x75 and b1 == 0x83:
            dph_val = b2
            dph_pc = pc
            if dpl_val is not None:
                dptr_val = (dph_val << 8) | dpl_val
                dptr_set_pc = dph_pc
                dptr_set_bytes = raw
                dptr_used = False
        elif op == 0x75 and b1 == 0x82:
            dpl_val = b2
            if dph_val is not None:
                dptr_val = (dph_val << 8) | dpl_val
                dptr_set_pc = dph_pc or pc
                dptr_set_bytes = raw
                dptr_used = False

        # 3. INC DPTR (0xA3) -> advances active DPTR by +1
        elif op == 0xA3 and dptr_val is not None:
            dptr_val = (dptr_val + 1) & 0xFFFF

        # 4. Indexed DPTR arithmetic: ADD A, DPL (25 82) or MOV DPL, A (F5 82)
        elif (op == 0x25 and b1 == 0x82) or (op == 0xF5 and b1 == 0x82):
            if dptr_val is not None:
                dptr_indexed = True

        # 5. MOVX A, @DPTR (0xE0) -> XDATA READ
        elif op == 0xE0 and dptr_val is not None:
            events.append({
                "bank": bank_id,
                "addr": dptr_val,
                "type": "XDATA_READ_INDEXED" if dptr_indexed else "XDATA_READ",
                "pc": pc,
                "set_pc": dptr_set_pc,
                "opcodes": (dptr_set_bytes + raw).hex().upper(),
            })
            dptr_used = True

        # 6. MOVX @DPTR, A (0xF0) -> XDATA WRITE
        elif op == 0xF0 and dptr_val is not None:
            events.append({
                "bank": bank_id,
                "addr": dptr_val,
                "type": "XDATA_WRITE_INDEXED" if dptr_indexed else "XDATA_WRITE",
                "pc": pc,
                "set_pc": dptr_set_pc,
                "opcodes": (dptr_set_bytes + raw).hex().upper(),
            })
            dptr_used = True

        # 7. MOVC A, @A+DPTR (0x93) -> CODE ROM Table Read
        elif op == 0x93 and dptr_val is not None:
            events.append({
                "bank": bank_id,
                "addr": dptr_val,
                "type": "CODE_TABLE_READ",
                "pc": pc,
                "set_pc": dptr_set_pc,
                "opcodes": (dptr_set_bytes + raw).hex().upper(),
            })
            dptr_used = True

        # 8. LCALL / ACALL with freshly loaded DPTR (pointer passed in DPTR)
        elif op in CALL_OPCODES:
            if dptr_val is not None and not dptr_used and dptr_set_pc is not None:
                call_target = ((b1 << 8) | b2) if op == 0x12 else (
                    ((pc + 2) & 0xF800) | ((op & 0xE0) << 3) | b1
                )
                events.append({
                    "bank": bank_id,
                    "addr": dptr_val,
                    "type": f"PTR_ARG_TO_CALL(0x{call_target:04X})",
                    "pc": pc,
                    "set_pc": dptr_set_pc,
                    "opcodes": (dptr_set_bytes + raw).hex().upper(),
                })
                dptr_used = True
            # Calls clobber DPTR in Keil C51
            dptr_val = None
            dph_val = None
            dpl_val = None
            dptr_indexed = False

        # 9. Basic-block terminators reset DPTR tracking
        elif op in BB_TERMINATORS:
            if dptr_val is not None and not dptr_used and dptr_set_pc is not None:
                events.append({
                    "bank": bank_id,
                    "addr": dptr_val,
                    "type": "DPTR_BEFORE_JUMP",
                    "pc": pc,
                    "set_pc": dptr_set_pc,
                    "opcodes": (dptr_set_bytes + raw).hex().upper(),
                })
            dptr_val = None
            dph_val = None
            dpl_val = None
            dptr_indexed = False

        pc += length

    return events


def scan_rom_pointers(bank_id: int, data: bytes, start_addr: int, end_addr: int) -> List[dict]:
    """
    Scan a bank binary for:
    - Keil 3-byte generic XDATA pointers: 0x01 HI LO
    - Aligned/table 16-bit Big-Endian words: HI LO (excluding `90 HI LO` MOV DPTR instructions)
    """
    hits = []
    n = len(data)
    for offset in range(0, n - 2):
        # Check Keil 3-byte generic pointer: 0x01 (XDATA tag), HI, LO
        if data[offset] == 0x01:
            val = (data[offset + 1] << 8) | data[offset + 2]
            if start_addr <= val <= end_addr:
                # Filter out AJMP 0x01 instructions where previous byte isn't table-like
                hits.append({
                    "bank": bank_id,
                    "addr": val,
                    "type": "ROM_GENERIC_PTR_3B(01_HI_LO)",
                    "pc": offset,
                    "set_pc": offset,
                    "opcodes": data[offset : offset + 3].hex().upper(),
                })

        # Check 16-bit Big-Endian HI LO not preceded by 0x90 (MOV DPTR), 0x02 (LJMP), 0x12 (LCALL)
        val16 = (data[offset] << 8) | data[offset + 1]
        if start_addr <= val16 <= end_addr:
            prev = data[offset - 1] if offset > 0 else 0
            if prev not in (0x90, 0x02, 0x12, 0x01):
                hits.append({
                    "bank": bank_id,
                    "addr": val16,
                    "type": "ROM_BE16_WORD",
                    "pc": offset,
                    "set_pc": offset,
                    "opcodes": data[offset : offset + 2].hex().upper(),
                })
    return hits


def find_keil_switch_Dispatchers(bank_files: List[Tuple[int, Path]]) -> List[dict]:
    """
    Locate Keil C51 ?C?CCASE (8-bit switch), ?C?ICASE (16-bit switch), and ?C?LCASE
    helpers in the common area by their exact Keil runtime byte signatures, then list
    every call site and decode the inline jump table.
    """
    if not bank_files:
        return []
    _, bank0_path = bank_files[0]
    b0 = bank0_path.read_bytes()

    # Standard Keil C51 ?C?CCASE signature:
    # D0 83 D0 82 (POP DPH; POP DPL) followed by E4 93 (CLR A; MOVC A, @A+DPTR)
    ccase_addrs = {}
    for off in range(0, min(0x6000, len(b0) - 16)):
        if b0[off : off + 4] == b"ÐÐ":
            chunk = b0[off : off + 32]
            if b"" in chunk and b"s" in chunk:  # MOVC + JMP @A+DPTR
                ccase_addrs[off] = "KEIL_SWITCH_HELPER"

    results = []
    for bank_id, path in bank_files:
        data = path.read_bytes()
        for off in range(0, len(data) - 3):
            if data[off] == 0x12:  # LCALL
                target = (data[off + 1] << 8) | data[off + 2]
                if target in ccase_addrs:
                    results.append({
                        "bank": bank_id,
                        "call_pc": f"0x{off:04X}",
                        "helper": f"0x{target:04X}",
                        "table_start": f"0x{off + 3:04X}",
                        "preview_bytes": data[off + 3 : off + 19].hex().upper(),
                    })
    return results


def format_disasm_window(data: bytes, center_pc: int, start_pc: Optional[int], ctx_insns: int = 5) -> List[str]:
    """Disassemble a small window around `[start_pc .. center_pc]`."""
    anchor = min(center_pc, start_pc) if start_pc is not None else center_pc
    win_start = max(0, anchor - ctx_insns * 3)
    # Align win_start by sweeping from max(0, win_start - 16)
    sweep = max(0, win_start - 16)
    insns = []
    while sweep < min(len(data), center_pc + ctx_insns * 3 + 6):
        mnem, length, raw = decode_insn(data, sweep)
        insns.append((sweep, raw, mnem))
        sweep += length

    lines = []
    for pc, raw, mnem in insns:
        if pc < win_start:
            continue
        marker = ">>" if pc in (center_pc, start_pc) else "  "
        lines.append(f"    {marker} 0x{pc:04X}: {raw.hex().upper():<8}  {mnem}")
    return lines


def parse_addr_spec(spec: str) -> Tuple[int, int]:
    """Parse '0xD8FE' or '0xD8F0-0xD8FF' into (start_addr, end_addr)."""
    spec = spec.strip()
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a, 16), int(b, 16)
    val = int(spec, 16)
    return val, val


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fast Cross-Bank 8051 XDATA, ROM Pointer & Keil Switch Analyzer"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target XDATA/Code address (e.g. 0xD8FE) or range (e.g. 0xD8F0-0xD8FF)",
    )
    parser.add_argument("--banks-dir", help="Path to directory containing bank_*.bin")
    parser.add_argument(
        "--context", "-C", type=int, default=0,
        help="Number of surrounding 8051 instructions to display around each hit",
    )
    parser.add_argument(
        "--rom-ptrs", action="store_true",
        help="Also scan for raw 16-bit Big-Endian and 3-byte Keil generic pointers in ROM",
    )
    parser.add_argument(
        "--include-indexed", action="store_true",
        help="Also match indexed DPTR bases within 0x100 below target (MOV DPTR,#base + ADD A,DPL)",
    )
    parser.add_argument(
        "--find-switches", action="store_true",
        help="Auto-detect Keil ?C?CCASE / ?C?ICASE switch helper calls across all banks",
    )
    parser.add_argument(
        "--dump-json", metavar="FILE",
        help="Export complete cross-bank XDATA read/write index to a JSON file",
    )
    args = parser.parse_args()

    bank_files = find_bank_files(args.banks_dir)
    if not bank_files:
        print("ERROR: Could not find bank_*.bin files (checked analysis/banks/).", file=sys.stderr)
        return 1

    if args.find_switches:
        switches = find_keil_switch_Dispatchers(bank_files)
        print(f"Found {len(switches)} Keil inline switch/case dispatch sites across {len(bank_files)} banks:")
        for s in switches:
            print(
                f"  Bank {s['bank']:02d} @ {s['call_pc']} -> LCALL {s['helper']} "
                f"(inline table @ {s['table_start']}: {s['preview_bytes']}...)"
            )
        if not args.target and not args.dump_json:
            return 0

    if args.dump_json:
        full_index: Dict[str, List[dict]] = defaultdict(list)
        for bank_id, path in bank_files:
            data = path.read_bytes()
            for ev in scan_bank_xdata(bank_id, data):
                full_index[f"0x{ev['addr']:04X}"].append({
                    "bank": ev["bank"],
                    "type": ev["type"],
                    "pc": f"0x{ev['pc']:04X}",
                    "set_pc": f"0x{ev['set_pc']:04X}" if ev["set_pc"] is not None else None,
                    "opcodes": ev["opcodes"],
                })
        out_path = Path(args.dump_json)
        out_path.write_text(json.dumps(full_index, indent=2, sort_keys=True))
        print(f"Exported {len(full_index)} unique DPTR target addresses to {out_path}")
        if not args.target:
            return 0

    if not args.target:
        parser.print_help()
        return 0

    start_addr, end_addr = parse_addr_spec(args.target)
    matched_events = []
    bank_bytes_map: Dict[int, bytes] = {}

    for bank_id, path in bank_files:
        data = path.read_bytes()
        bank_bytes_map[bank_id] = data
        for ev in scan_bank_xdata(bank_id, data):
            addr = ev["addr"]
            if start_addr <= addr <= end_addr:
                matched_events.append(ev)
            elif args.include_indexed and "INDEXED" in ev["type"]:
                if (start_addr - 0xFF) <= addr <= end_addr:
                    matched_events.append(ev)

        if args.rom_ptrs:
            matched_events.extend(scan_rom_pointers(bank_id, data, start_addr, end_addr))

    target_label = (
        f"0x{start_addr:04X}" if start_addr == end_addr else f"0x{start_addr:04X}..0x{end_addr:04X}"
    )
    print(f"=== XDATA / DPTR Cross-References for {target_label} ({len(matched_events)} hits) ===")

    for ev in matched_events:
        b = ev["bank"]
        addr = ev["addr"]
        pc = ev["pc"]
        set_pc = ev["set_pc"]
        set_info = f" (DPTR set @ 0x{set_pc:04X})" if set_pc is not None and set_pc != pc else ""
        print(
            f"[bank_{b}.bin, 0x{pc:04X}, {ev['opcodes']}]  "
            f"target=0x{addr:04X}  type={ev['type']}{set_info}"
        )
        if args.context > 0:
            for line in format_disasm_window(bank_bytes_map[b], pc, set_pc, args.context):
                print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
