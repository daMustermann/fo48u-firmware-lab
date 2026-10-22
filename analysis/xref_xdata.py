#!/usr/bin/env python3
"""Cross-bank XDATA read/write/index cross-reference tool for F08 8051 firmware.

Scans all bank bins in analysis/banks/bank_*.bin for:
- MOV DPTR,#0xXXXX followed by MOVX A,@DPTR (0xE0) reads or MOVX @DPTR,A (0xF0) writes
- Sequential INC DPTR (0xA3) accesses
- ROM pointer tables (16-bit big-endian, and 3-byte Keil generic 01 HI LO)
- Indexed base pointers (MOV DPTR,#base + ADD A,DPL / ADDC A,DPH)
- Keil C51 inline switch/case tables for ?C?CCASE / ?C?ICASE

Usage:
  python3 analysis/xref_xdata.py 0xD8FE -C 5
  python3 analysis/xref_xdata.py 0xD8FE --rom-ptrs --include-indexed -C 5
  python3 analysis/xref_xdata.py 0xD8F0-0xD8FF
  python3 analysis/xref_xdata.py --find-switches
  python3 analysis/xref_xdata.py --dump-json analysis/xdata_index.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BANKS_DIR = REPO / "analysis" / "banks"
OPLEN = REPO / "analysis" / "oplen.py"


def load_oplen():
    sys.path.insert(0, str(REPO / "analysis"))
    import oplen
    return oplen.OPLEN


OPLEN_TABLE = load_oplen()
ISA_FIXUP = {0x82: 3, 0x84: 2, 0xD6: 2, 0xD7: 2, 0xE2: 2, 0xE3: 2}


def inst_len(op):
    return ISA_FIXUP.get(op, OPLEN_TABLE[op] if op < len(OPLEN_TABLE) else 1)


def load_banks():
    banks = {}
    for p in sorted(BANKS_DIR.glob("bank_*.bin")):
        try:
            num = int(p.stem.split("_")[1])
        except Exception:
            continue
        banks[num] = p.read_bytes()
    return banks


def disasm_around(data, offset, ctx):
    """Simple disasm around offset with context"""
    lines = []
    # Go back
    start = max(0, offset - 200)
    # Just decode from start to offset+50
    pos = start
    target_pos = offset
    out_lines = []
    while pos < min(len(data), offset + 80):
        if pos >= len(data):
            break
        op = data[pos]
        l = inst_len(op)
        if pos + l > len(data):
            l = 1
        raw = data[pos:pos + l]
        marker = ">>>" if pos == target_pos or (pos < target_pos < pos + l) else "   "
        out_lines.append(f"        {marker} {pos:04X}: {raw.hex(' '):16s} op{op:02X}")
        pos += l
    return out_lines


def scan_xdata(banks, target_addr=None, addr_range=None, rom_ptrs=False, include_indexed=False):
    results = {"reads": [], "writes": [], "indexed": [], "rom_ptrs": []}
    
    if addr_range:
        start, end = addr_range
        targets = set(range(start, end + 1))
    elif target_addr is not None:
        targets = {target_addr}
    else:
        targets = None
    
    for bnum, data in banks.items():
        i = 0
        while i < len(data) - 5:
            op = data[i]
            # MOV DPTR, #imm16
            if op == 0x90 and i + 3 < len(data):
                dptr = (data[i+1] << 8) | data[i+2]
                # Check next instructions
                j = i + 3
                # Look ahead a bit
                k = j
                steps = 0
                while k < min(len(data), j + 30) and steps < 20:
                    op2 = data[k]
                    l2 = inst_len(op2)
                    # MOVX A, @DPTR
                    if op2 == 0xE0:
                        if targets is None or dptr in targets:
                            results["reads"].append({
                                "bank": bnum, "dptr_addr": dptr,
                                "movdptr_off": i, "movx_off": k,
                                "note": "direct MOVX read"
                            })
                        k += l2
                        break
                    # MOVX @DPTR, A
                    elif op2 == 0xF0:
                        if targets is None or dptr in targets:
                            results["writes"].append({
                                "bank": bnum, "dptr_addr": dptr,
                                "movdptr_off": i, "movx_off": k,
                                "note": "direct MOVX write"
                            })
                        k += l2
                        break
                    elif op2 == 0xA3:  # INC DPTR
                        k += l2
                        steps += 1
                        continue
                    elif op2 == 0x22 or op2 == 0x02:  # RET/LJMP
                        break
                    else:
                        k += l2
                        steps += 1
                        continue
                i += 1
                continue
            i += 1
    
    if rom_ptrs or targets is None:
        # Scan for ROM pointer tables - 16-bit big endian pointers
        for bnum, data in banks.items():
            for i in range(len(data) - 2):
                ptr = (data[i] << 8) | data[i+1]
                if targets is None or (targets and ptr in targets):
                    # Check if it looks like code pointer
                    if 0x0000 <= ptr < 0x8000:
                        results["rom_ptrs"].append({
                            "bank": bnum, "offset": i, "ptr": ptr,
                            "raw": data[i:i+2].hex()
                        })
            # 3-byte Keil generic pointer 01 HI LO
            for i in range(len(data) - 3):
                if data[i] == 0x01:
                    ptr = (data[i+1] << 8) | data[i+2]
                    if targets is None or (targets and ptr in targets):
                        results["rom_ptrs"].append({
                            "bank": bnum, "offset": i, "ptr": ptr,
                            "raw": data[i:i+3].hex(), "type": "keil_generic"
                        })
    
    if include_indexed:
        for bnum, data in banks.items():
            i = 0
            while i < len(data) - 10:
                op = data[i]
                if op == 0x90 and i + 3 < len(data):
                    base = (data[i+1] << 8) | data[i+2]
                    j = i + 3
                    # Look for ADD A,DPL or ADDC
                    for k in range(j, min(j+15, len(data)-2)):
                        if data[k] == 0x25:  # ADD A,DPL
                            if targets is None or (targets and any((base + x) in targets for x in range(256))):
                                results["indexed"].append({
                                    "bank": bnum, "base": base,
                                    "movdptr_off": i, "add_off": k,
                                    "note": "base + ADD A,DPL indexing"
                                })
                            break
                        elif data[k] == 0x35:  # ADDC A,DPL
                            results["indexed"].append({
                                "bank": bnum, "base": base,
                                "movdptr_off": i, "add_off": k,
                                "note": "base + ADDC A,DPL indexing"
                            })
                            break
                i += 1
    
    return results


def find_switches(banks):
    results = []
    for bnum, data in banks.items():
        # Look for LCALL followed by inline jump table (JMP @A+DPTR pattern or table)
        for i in range(len(data) - 10):
            if data[i] == 0x12:  # LCALL
                target = (data[i+1] << 8) | data[i+2]
                # Check if followed by table bytes
                # Common pattern: table right after
                table_start = i + 3
                # Look ahead for jump table entries
                if table_start + 10 < len(data):
                    # Check for 16-bit big endian pointers
                    hits = 0
                    for t in range(table_start, min(table_start + 40, len(data) - 1), 2):
                        p = (data[t] << 8) | data[t+1]
                        if 0x0000 < p < 0x10000 and p != 0xFFFF:
                            hits += 1
                    if hits >= 3:
                        results.append({
                            "bank": bnum, "lcall_off": i, "lcall_target": target,
                            "table_start": table_start, "table_entries": hits
                        })
    return results


def main():
    parser = argparse.ArgumentParser(description="XDATA cross-reference tool")
    parser.add_argument("addr", nargs="?", help="XDATA address like 0xD8FE or range 0xD8F0-0xD8FF")
    parser.add_argument("-C", "--context", type=int, default=3, help="Disasm context lines")
    parser.add_argument("--rom-ptrs", action="store_true", help="Include ROM pointer tables")
    parser.add_argument("--include-indexed", action="store_true", help="Include indexed base pointers")
    parser.add_argument("--find-switches", action="store_true", help="Find Keil inline switch tables")
    parser.add_argument("--dump-json", help="Export full index to JSON")
    args = parser.parse_args()
    
    banks = load_banks()
    print(f"Loaded {len(banks)} banks")
    
    if args.find_switches:
        sw = find_switches(banks)
        print(f"\nFound {len(sw)} potential inline switch tables:")
        for s in sw[:50]:
            print(f"  bank {s['bank']}:{s['lcall_off']:04X} LCALL {s['lcall_target']:04X}, table@{s['table_start']:04X} (~{s['table_entries']} entries)")
        return
    
    if args.dump_json:
        full = scan_xdata(banks, None, None, True, True)
        # Also switches
        full["switches"] = find_switches(banks)
        with open(args.dump_json, 'w') as f:
            json.dump(full, f, indent=2)
        print(f"Wrote {args.dump_json}")
        print(f"  reads:{len(full['reads'])} writes:{len(full['writes'])} rom_ptrs:{len(full['rom_ptrs'])} indexed:{len(full['indexed'])} switches:{len(full['switches'])}")
        return
    
    if not args.addr:
        parser.print_help()
        return
    
    target_addr = None
    addr_range = None
    if '-' in args.addr:
        a,b = args.addr.split('-')
        addr_range = (int(a,16), int(b,16))
        print(f"Scanning range 0x{addr_range[0]:04X}-0x{addr_range[1]:04X}")
    else:
        target_addr = int(args.addr, 16)
        print(f"Scanning XDATA 0x{target_addr:04X}")
    
    res = scan_xdata(banks, target_addr, addr_range, args.rom_ptrs, args.include_indexed)
    
    print(f"\n=== READS (MOVX A,@DPTR) ===")
    for r in res["reads"]:
        print(f"  bank{r['bank']}:{r['movdptr_off']:04X} MOV DPTR,#0x{r['dptr_addr']:04X} -> MOVX read @ {r['movx_off']:04X} [{r['note']}]")
        if args.context > 0 and target_addr:
            print('\n'.join(disasm_around(banks[r['bank']], r['movdptr_off'], args.context)))
    
    print(f"\n=== WRITES (MOVX @DPTR,A) ===")
    for w in res["writes"]:
        print(f"  bank{w['bank']}:{w['movdptr_off']:04X} MOV DPTR,#0x{w['dptr_addr']:04X} -> MOVX write @ {w['movx_off']:04X} [{w['note']}]")
        if args.context > 0 and target_addr:
            print('\n'.join(disasm_around(banks[w['bank']], w['movdptr_off'], args.context)))
    
    if res["rom_ptrs"]:
        print(f"\n=== ROM POINTER TABLES ===")
        for p in res["rom_ptrs"][:100]:
            print(f"  bank{p['bank']}:{p['offset']:04X} -> 0x{p['ptr']:04X} [{p.get('raw','')}]")
    
    if res["indexed"]:
        print(f"\n=== INDEXED BASE POINTERS ===")
        for p in res["indexed"]:
            print(f"  bank{p['bank']}:{p['movdptr_off']:04X} MOV DPTR,#0x{p['base']:04X} + {p['note']} @ {p['add_off']:04X}")


if __name__ == "__main__":
    main()
