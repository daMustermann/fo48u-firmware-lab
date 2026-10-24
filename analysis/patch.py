#!/usr/bin/env python3
"""Validated offline bank operations. No in-place patching; DO NOT FLASH.

extract BANK OUTPUT
patch BANKFILE PATCHES_JSON OUTPUT [--bank BANK] --emit-offline-research
reassemble OUTPUT [--banks-dir DIR] --emit-offline-research

JSON records require bank, offset (integer), old and new (hex strings).
Validation covers byte identity and layout size, not arbitrary instruction safety.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
IMG = BASE / "firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin"
BANKS_DIR = BASE / "analysis/banks"
BANK_SIZE = 0x10000
NUM_BANKS = 31
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"


def load_stock(path=None):
    data = Path(path or IMG).read_bytes()
    if len(data) != NUM_BANKS * BANK_SIZE or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("source is not the hash-verified stock F08 image")
    return data


def bank_number(bank):
    if type(bank) is not int or not 0 <= bank < NUM_BANKS:
        raise ValueError("bank must be an integer in 0..30")
    return bank


def apply_patches(data, patches, bank, stock_bank):
    bank_number(bank)
    if len(data) != BANK_SIZE or len(stock_bank) != BANK_SIZE or data != stock_bank:
        raise ValueError("input bank must equal its verified stock F08 slice")
    if not isinstance(patches, list) or not patches:
        raise ValueError("patches must be a nonempty JSON array")
    planned, covered = [], set()
    for record in patches:
        if not isinstance(record, dict) or set(record) != {"bank", "offset", "old", "new"}:
            raise ValueError("patch requires exactly bank, offset, old, new")
        if bank_number(record["bank"]) != bank:
            raise ValueError("patch bank does not match input bank")
        offset = record["offset"]
        if not isinstance(record["old"], str) or not isinstance(record["new"], str):
            raise ValueError("old/new must be hex strings")
        old, new = bytes.fromhex(record["old"]), bytes.fromhex(record["new"])
        if not old or len(old) != len(new):
            raise ValueError("replacement must have the same nonzero length as old")
        if type(offset) is not int or offset < 0 or offset + len(old) > BANK_SIZE:
            raise ValueError("patch range is outside 0000..FFFF")
        span = set(range(offset, offset + len(old)))
        if covered & span:
            raise ValueError("patch ranges overlap")
        if stock_bank[offset:offset + len(old)] != old:
            raise ValueError(f"stock mismatch at {bank}:{offset:04X}")
        covered.update(span)
        planned.append((offset, new))
    result = bytearray(data)
    for offset, new in planned:
        result[offset:offset + len(new)] = new
    return bytes(result)


def reassemble(stock, banks_dir=None):
    if len(stock) != BANK_SIZE * NUM_BANKS or hashlib.sha256(stock).hexdigest() != SHA256:
        raise ValueError("reassembly requires hash-verified stock F08")
    result = bytearray(stock)
    directory = Path(banks_dir or BANKS_DIR)
    # Only code banks are overlaid. The verified stock tail is authoritative.
    for bank in range(20):
        data = (directory / f"bank_{bank}.bin").read_bytes()
        if len(data) != BANK_SIZE:
            raise ValueError(f"bank {bank} must contain exactly 65536 bytes")
        result[bank * BANK_SIZE:(bank + 1) * BANK_SIZE] = data
    if result[20 * BANK_SIZE:] != stock[20 * BANK_SIZE:]:
        raise AssertionError("stock tail was changed")
    return bytes(result)


def write_output(out, data, inputs=()):
    target = Path(out).resolve()
    protected = [Path(IMG).resolve(), *(Path(BANKS_DIR) / f"bank_{b}.bin" for b in range(NUM_BANKS)), *map(Path, inputs)]
    if any(target == p.resolve() or (target.exists() and p.exists() and target.samefile(p)) for p in protected):
        raise ValueError("refusing to overwrite a stock or input file")
    # Exclusive creation also refuses existing outputs, symlinks and hard links.
    with target.open("xb") as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("bank", type=int)
    extract.add_argument("output", type=Path)
    patch = sub.add_parser("patch")
    patch.add_argument("bankfile", type=Path)
    patch.add_argument("patches_json", type=Path)
    patch.add_argument("output", type=Path)
    patch.add_argument("--bank", type=int)
    assemble = sub.add_parser("reassemble")
    assemble.add_argument("output", type=Path)
    assemble.add_argument("--banks-dir", type=Path, default=BANKS_DIR)
    for command in (patch, assemble):
        command.add_argument("--emit-offline-research", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command != "extract" and not args.emit_offline_research:
            raise ValueError("output requires --emit-offline-research; DO NOT FLASH")
        stock = load_stock()
        inputs = []
        if args.command == "extract":
            bank = bank_number(args.bank)
            result = stock[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        elif args.command == "patch":
            match = re.fullmatch(r"bank_(\d+)\.bin", args.bankfile.name)
            bank = args.bank if args.bank is not None else (int(match[1]) if match else None)
            bank_number(bank)
            if match and int(match[1]) != bank:
                raise ValueError("--bank conflicts with input filename")
            result = apply_patches(args.bankfile.read_bytes(), json.loads(args.patches_json.read_text()),
                                   bank, stock[bank * BANK_SIZE:(bank + 1) * BANK_SIZE])
            inputs = [args.bankfile, args.patches_json]
        else:
            result = reassemble(stock, args.banks_dir)
            inputs = list(args.banks_dir.glob("bank_*.bin"))
        write_output(args.output, result, inputs)
        print(f"wrote {len(result)} bytes to {args.output}; DO NOT FLASH")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
