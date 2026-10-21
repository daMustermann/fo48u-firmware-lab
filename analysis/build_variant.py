#!/usr/bin/env python3
"""Offline FO48U F08 firmware research tool. DO NOT FLASH outputs.

Use --verify for static source-byte checks. --emit-offline-research
explicitly permits creating local unvalidated research images.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "firmware" / "F08-20221115" / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin"
OUT_DIR = REPO / "firmware" / "PATCHED"

SRC_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"
SRC_SIZE = 2_031_616
BANK_SIZE = 0x10000

# name -> list of (bank, bank-relative address, expected, replacement, note)
PATCHES: dict[str, list[tuple[int, int, bytes, bytes, str]]] = {
    "unlock_cmd_gate": [
        (
            12,
            0x68AD,
            bytes.fromhex("64 02"),
            bytes.fromhex("E4 00"),
            "APCS command entry: replace `xrl a,#2` with `clr a; nop`, so the "
            "following `jnz` never skips the request",
        ),
        (
            12,
            0x68BD,
            bytes.fromhex("B4 02 14"),
            bytes.fromhex("E4 00 00"),
            "AOCS command entry: replace `cjne a,#2,0x68D4` with "
            "`clr a; nop; nop`, so it always falls through",
        ),
    ],
    "apcs_2h": [
        (
            13,
            0xCAA8,
            bytes.fromhex("94 04"),
            bytes.fromhex("94 02"),
            "APCS interval 4 h -> 2 h (`subb a,#4` -> `subb a,#2`)",
        ),
    ],
    "apcs_36h": [
        (
            13,
            0xCAA8,
            bytes.fromhex("94 04"),
            bytes.fromhex("94 24"),
            "APCS interval 4 h -> 36 h (`subb a,#4` -> `subb a,#0x24`); "
            "the TSS reminder is separate and unchanged at 36 h",
        ),
    ],
    "aocs_750h": [
        (
            13,
            0xCAD3,
            bytes.fromhex("7C 05 7D DC"),
            bytes.fromhex("7C 02 7D EE"),
            "AOCS divisor 1500 h (0x05DC) -> 750 h (0x02EE)",
        ),
    ],
    "tss_12h": [
        (
            13,
            0xCB1A,
            bytes.fromhex("94 24"),
            bytes.fromhex("94 0C"),
            "panel-care reminder 36 h -> 12 h (`subb a,#0x24` -> `#0x0C`)",
        ),
    ],
}

VARIANTS: dict[str, tuple[list[str], str]] = {
    "F08-unlock": (
        ["unlock_cmd_gate"],
        "APCS/AOCS command gate removed; schedule unchanged",
    ),
    "F08-care": (
        ["unlock_cmd_gate", "apcs_2h", "aocs_750h", "tss_12h"],
        "unlock + APCS 2 h / AOCS 750 h / TSS 12 h",
    ),
    "F08-quiet": (
        ["unlock_cmd_gate", "apcs_36h"],
        "unlock + APCS 36 h (TSS reminder unchanged at 36 h)",
    ),
}


def file_offset(bank: int, addr: int) -> int:
    return bank * BANK_SIZE + addr


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def load_source() -> bytearray:
    if not SRC.exists():
        raise SystemExit(f"source image not found: {SRC}")
    data = bytearray(SRC.read_bytes())
    if len(data) != SRC_SIZE:
        raise SystemExit(f"unexpected source size: {len(data)} != {SRC_SIZE}")
    got = md5(bytes(data))
    if got != SRC_MD5:
        raise SystemExit(f"unexpected source MD5: {got} != {SRC_MD5}")
    return data


def verify_sites(data: bytearray) -> None:
    problems = 0
    for patch_name, sites in PATCHES.items():
        for bank, addr, expected, _replacement, note in sites:
            off = file_offset(bank, addr)
            got = bytes(data[off : off + len(expected)])
            status = "OK" if got == expected else "MISMATCH"
            if got != expected:
                problems += 1
            print(
                f"  {status:8s} {patch_name:16s} bank {bank:2d} 0x{addr:04x} "
                f"file 0x{off:06x}  got {got.hex(' ')}  want {expected.hex(' ')}"
            )
            if got != expected:
                print(f"           {note}")
    if problems:
        raise SystemExit(f"{problems} patch site(s) do not match the source image")


def apply_patch(data: bytearray, name: str) -> list[str]:
    notes: list[str] = []
    for bank, addr, expected, replacement, note in PATCHES[name]:
        off = file_offset(bank, addr)
        got = bytes(data[off : off + len(expected)])
        if got != expected:
            raise SystemExit(
                f"{name}: bank {bank} 0x{addr:04x}: got {got.hex(' ')}, "
                f"want {expected.hex(' ')}"
            )
        if len(replacement) != len(expected):
            raise SystemExit(f"{name}: replacement length mismatch at 0x{addr:04x}")
        data[off : off + len(replacement)] = replacement
        notes.append(f"bank {bank:2d} 0x{addr:04x}: {expected.hex(' ')} -> {replacement.hex(' ')}  ({note})")
    return notes


def write_variant(name: str, patch_names: list[str], description: str) -> dict[str, str]:
    data = load_source()
    notes: list[str] = []
    for patch_name in patch_names:
        notes.extend(apply_patch(data, patch_name))

    out = OUT_DIR / f"{name}.bin"
    if out.exists():
        raise SystemExit(
            f"research image already exists: {out}; choose a fresh workspace "
            "before generating experimental files"
        )
    out.write_bytes(data)
    digest = md5(bytes(data))
    (OUT_DIR / f"{name}.bin.md5").write_text(
        f"{digest}  {out.name}\n", encoding="utf-8", newline="\n"
    )
    print(f"built {out}  {len(data)} bytes  MD5 {digest}")
    return {
        "name": name,
        "description": description,
        "patches": patch_names,
        "notes": notes,
        "md5": digest,
        "file": out.name,
    }


def write_manifest(built: list[dict[str, object]]) -> None:
    lines = [
        "# Patched firmware variants",
        "",
        "Generated by `analysis/build_variant.py` from",
        f"`firmware/F08-20221115/{SRC.name}` (MD5 `{SRC_MD5}`).",
        "",
        "> **OFFLINE RESEARCH ONLY. DO NOT FLASH.**",
        "> Static byte matching does not establish functional or safe firmware.",
        "",
        "| Variant | MD5 | Patches | Description |",
        "|---|---|---|---|",
    ]
    for item in built:
        lines.append(
            f"| `{item['file']}` | `{item['md5']}` | "
            f"{', '.join('`' + p + '`' for p in item['patches'])} | "
            f"{item['description']} |"
        )
    lines += ["", "## Patch details", ""]
    for item in built:
        lines.append(f"### `{item['name']}`")
        lines.append("")
        for note in item["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    lines += [
        "## What the patches do",
        "",
        "- `unlock_cmd_gate` removes the `0xCFDE == 2` check in front of the",
        "  APCS and AOCS command entries in bank 12. Those entries are the",
        "  cleanest way to request a refresh; the check makes them inert when",
        "  the command code is not 2.",
        "- `apcs_2h` changes the automatic APCS interval from 4 h to 2 h.",
        "- `apcs_36h` changes the automatic APCS interval from 4 h to 36 h;",
        "  the TSS reminder is a separate timer and remains at 36 h.",
        "- `aocs_750h` changes the automatic AOCS interval from 1500 h to 750 h.",
        "- `tss_12h` changes the TSS panel-care reminder from 36 h to 12 h.",
        "",
        "## Research status",
        "",
        "Local-only outputs have not been tested on hardware and have no",
        "verified recovery path. DO NOT FLASH.",
        "",
    ]
    (OUT_DIR / "MANIFEST.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if "--verify" in argv:
        print(f"source: {SRC}")
        print(f"size:   {SRC_SIZE} bytes")
        print(f"MD5:    {SRC_MD5}")
        verify_sites(load_source())
        print("all patch sites match")
        return 0

    if "--emit-offline-research" not in argv:
        raise SystemExit(
            "No validated firmware release. Use --verify for byte checks or "
            "--emit-offline-research for local-only experiments. DO NOT FLASH."
        )

    wanted = [a for a in argv[1:] if not a.startswith("-")]
    if wanted:
        unknown = [n for n in wanted if n not in VARIANTS]
        if unknown:
            raise SystemExit(f"unknown variant(s): {', '.join(unknown)}")
        names = wanted
    else:
        names = list(VARIANTS)

    verify_sites(load_source())
    built = []
    for name in names:
        patch_names, description = VARIANTS[name]
        built.append(write_variant(name, patch_names, description))

    if len(built) == len(VARIANTS):
        write_manifest(built)
        print(f"wrote {OUT_DIR / 'MANIFEST.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
