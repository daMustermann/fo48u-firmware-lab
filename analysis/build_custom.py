#!/usr/bin/env python3
"""Build a custom FO48U firmware image with configurable panel-care settings.

Everything is applied to the original F08 image and verified byte-for-byte
before writing.  The original image is never modified.

Examples
--------
    # See every available option
    python analysis/build_custom.py --help

    # Stock schedule, but the service-menu APCS/AOCS items now actually
    # request a refresh when selected.
    python analysis/build_custom.py --name F08-menu --menu-actions

    # Same, with the 36 h APCS interval used by the public F08b firmware.
    python analysis/build_custom.py --name F08-menu-quiet --menu-actions --apcs 36

    # Aggressive care schedule.
    python analysis/build_custom.py --name F08-menu-care --menu-actions \
        --apcs 8 --aocs 750 --tss 12

    # Verify every patch site without writing anything.
    python analysis/build_custom.py --verify

Notes
-----
* APCS and TSS are one-byte hour counters (0-254; 255 = never).
* AOCS is a 16-bit hour counter (0-65534; 65535 = never).
* `--menu-actions` patches the key path of the existing service-menu
  "APCS" and "AOCS" items.  The original UI behaviour is preserved; the
  patch only adds a direct `0xD12D` request before the original code runs.
* These images are unofficial and untested on hardware.  Read
  firmware/PATCHED/README.md before flashing.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "firmware" / "F08-20221115" / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin"
OUT_DIR = REPO / "firmware" / "PATCHED"

SRC_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"
SRC_SIZE = 2_031_616
BANK_SIZE = 0x10000

# --- fixed patch sites -----------------------------------------------------
# (bank, address, expected bytes)
UNLOCK_SITES = [
    (12, 0x68AD, bytes.fromhex("64 02")),
    (12, 0x68BD, bytes.fromhex("B4 02 14")),
]
APCS_SITE = (13, 0xCAA8, bytes.fromhex("94 04"))
AOCS_SITE = (13, 0xCAD3, bytes.fromhex("7C 05 7D DC"))
TSS_SITE = (13, 0xCB1A, bytes.fromhex("94 24"))

# Service-menu key paths.  Each starts with `mov dptr,#0xC693; movx a,@dptr`
# and is followed by `jnz ...`.  We replace the 3-byte `mov dptr` with a
# `ljmp` into free bank-9 space, perform the request, then re-load A and
# jump back to the original `jnz`.
MENU_APCS_SITE = (9, 0xA161, bytes.fromhex("90 C6 93"))
MENU_AOCS_SITE = (9, 0xA1D5, bytes.fromhex("90 C6 93"))
MENU_APCS_TRAMPOLINE = 0xFEFA
MENU_AOCS_TRAMPOLINE = 0xFF08


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


def expect(data: bytearray, bank: int, addr: int, expected: bytes, what: str) -> None:
    off = file_offset(bank, addr)
    got = bytes(data[off : off + len(expected)])
    if got != expected:
        raise SystemExit(
            f"{what}: bank {bank} 0x{addr:04x} has {got.hex(' ')}, "
            f"expected {expected.hex(' ')}"
        )


def put(data: bytearray, bank: int, addr: int, replacement: bytes) -> None:
    off = file_offset(bank, addr)
    data[off : off + len(replacement)] = replacement


def patch_unlock(data: bytearray, notes: list[str]) -> None:
    expect(data, *UNLOCK_SITES[0], "unlock APCS command gate")
    expect(data, *UNLOCK_SITES[1], "unlock AOCS command gate")
    put(data, 12, 0x68AD, bytes.fromhex("E4 00"))
    put(data, 12, 0x68BD, bytes.fromhex("E4 00 00"))
    notes.append(
        "bank 12 0x68AD/0x68BD: removed the `0xCFDE == 2` gate in front of the "
        "APCS/AOCS command entries"
    )


def patch_apcs(data: bytearray, hours: int, notes: list[str]) -> None:
    bank, addr, expected = APCS_SITE
    expect(data, bank, addr, expected, "APCS interval")
    value = 0xFF if hours <= 0 else hours
    if not 1 <= value <= 0xFF:
        raise SystemExit("APCS must be 0 (never) or 1-255 hours")
    put(data, bank, addr, bytes([0x94, value]))
    notes.append(
        f"bank 13 0x{addr:04X}: APCS interval `subb a,#0x04` -> "
        f"`subb a,#0x{value:02X}` ({'never' if value == 0xFF else str(value) + ' h'})"
    )


def patch_aocs(data: bytearray, hours: int, notes: list[str]) -> None:
    bank, addr, expected = AOCS_SITE
    expect(data, bank, addr, expected, "AOCS divisor")
    value = 0xFFFF if hours <= 0 else hours
    if not 1 <= value <= 0xFFFF:
        raise SystemExit("AOCS must be 0 (never) or 1-65535 hours")
    hi, lo = (value >> 8) & 0xFF, value & 0xFF
    put(data, bank, addr, bytes([0x7C, hi, 0x7D, lo]))
    notes.append(
        f"bank 13 0x{addr:04X}: AOCS divisor 0x05DC -> "
        f"0x{hi:02X}{lo:02X} ({'never' if value == 0xFFFF else str(value) + ' h'})"
    )


def patch_tss(data: bytearray, hours: int, notes: list[str]) -> None:
    bank, addr, expected = TSS_SITE
    expect(data, bank, addr, expected, "TSS interval")
    value = 0xFF if hours <= 0 else hours
    if not 1 <= value <= 0xFF:
        raise SystemExit("TSS must be 0 (never) or 1-255 hours")
    put(data, bank, addr, bytes([0x94, value]))
    notes.append(
        f"bank 13 0x{addr:04X}: panel-care reminder `subb a,#0x24` -> "
        f"`subb a,#0x{value:02X}` ({'never' if value == 0xFF else str(value) + ' h'})"
    )


def patch_menu_actions(data: bytearray, notes: list[str]) -> None:
    """Make the service-menu APCS/AOCS items request a real refresh.

    The existing handlers are split into a draw path (R5 == 0) and a key
    path (R5 != 0).  We leave the draw path alone and redirect the key
    path through a tiny trampoline that sets the matching bit in 0xD12D
    before running the original key handler.  This is additive: if the
    stock handler already triggered something, the request is still
    idempotent.
    """
    bank, addr, expected = MENU_APCS_SITE
    expect(data, bank, addr, expected, "APCS menu key path")
    bank, addr, expected = MENU_AOCS_SITE
    expect(data, bank, addr, expected, "AOCS menu key path")

    # The trampolines live in erased bank-9 flash.  Check it is still erased.
    expect(data, 9, MENU_APCS_TRAMPOLINE, b"\xFF" * 14, "APCS trampoline space")
    expect(data, 9, MENU_AOCS_TRAMPOLINE, b"\xFF" * 14, "AOCS trampoline space")

    # APCS: set bit0, then re-load A from 0xC693 and jump to the stock
    # `jnz` at 0xA165.
    apcs = bytes.fromhex("90 D1 2D E0 44 01 F0 90 C6 93 E0 02 A1 65")
    # AOCS: set bit1, then jump to the stock `jnz` at 0xA1D9.
    aocs = bytes.fromhex("90 D1 2D E0 44 02 F0 90 C6 93 E0 02 A1 D9")
    put(data, 9, MENU_APCS_TRAMPOLINE, apcs)
    put(data, 9, MENU_AOCS_TRAMPOLINE, aocs)

    put(data, 9, 0xA161, bytes.fromhex("02 FE FA"))
    put(data, 9, 0xA1D5, bytes.fromhex("02 FF 08"))
    notes.append(
        "bank 9 0xA161: service-menu APCS key path now sets 0xD12D bit0 "
        "(request APCS) before the stock handler"
    )
    notes.append(
        "bank 9 0xA1D5: service-menu AOCS key path now sets 0xD12D bit1 "
        "(request AOCS) before the stock handler"
    )


def verify_all() -> None:
    data = load_source()
    checks = [
        ("unlock APCS", *UNLOCK_SITES[0]),
        ("unlock AOCS", *UNLOCK_SITES[1]),
        ("APCS interval", *APCS_SITE),
        ("AOCS divisor", *AOCS_SITE),
        ("TSS interval", *TSS_SITE),
        ("APCS menu key path", *MENU_APCS_SITE),
        ("AOCS menu key path", *MENU_AOCS_SITE),
    ]
    print(f"source: {SRC}")
    print(f"size:   {SRC_SIZE} bytes")
    print(f"MD5:    {SRC_MD5}")
    for name, bank, addr, expected in checks:
        off = file_offset(bank, addr)
        got = bytes(data[off : off + len(expected)])
        status = "OK" if got == expected else "MISMATCH"
        print(
            f"  {status:8s} {name:20s} bank {bank:2d} 0x{addr:04x} "
            f"file 0x{off:06x}  got {got.hex(' ')}  want {expected.hex(' ')}"
        )
        if got != expected:
            raise SystemExit("patch site mismatch")
    for name, addr in [
        ("APCS trampoline space", MENU_APCS_TRAMPOLINE),
        ("AOCS trampoline space", MENU_AOCS_TRAMPOLINE),
    ]:
        off = file_offset(9, addr)
        got = bytes(data[off : off + 14])
        if got != b"\xFF" * 14:
            raise SystemExit(f"{name} at 0x{addr:04x} is not erased: {got.hex(' ')}")
        print(f"  {'OK':8s} {name:20s} bank  9 0x{addr:04x} is erased")
    print("all patch sites match the original image")


def build(args: argparse.Namespace) -> dict[str, object]:
    data = load_source()
    notes: list[str] = []
    patches: list[str] = []

    if args.unlock:
        patch_unlock(data, notes)
        patches.append("unlock")
    if args.menu_actions:
        patch_menu_actions(data, notes)
        patches.append("menu-actions")
    if args.apcs is not None:
        patch_apcs(data, args.apcs, notes)
        patches.append(f"apcs-{args.apcs or 'never'}")
    if args.aocs is not None:
        patch_aocs(data, args.aocs, notes)
        patches.append(f"aocs-{args.aocs or 'never'}")
    if args.tss is not None:
        patch_tss(data, args.tss, notes)
        patches.append(f"tss-{args.tss or 'never'}")

    if not patches:
        raise SystemExit("nothing selected; use --unlock, --menu-actions, --apcs, --aocs or --tss")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.name}.bin"
    out.write_bytes(data)
    digest = md5(bytes(data))
    (OUT_DIR / f"{args.name}.bin.md5").write_text(
        f"{digest}  {out.name}\n", encoding="utf-8", newline="\n"
    )
    print(f"built {out}  {len(data)} bytes  MD5 {digest}")
    return {
        "name": args.name,
        "file": out.name,
        "md5": digest,
        "patches": patches,
        "notes": notes,
        "description": args.description or ", ".join(patches),
    }


def write_manifest(built: list[dict[str, object]]) -> None:
    lines = [
        "# Custom firmware variants",
        "",
        "Generated by `analysis/build_custom.py` from",
        f"`firmware/F08-20221115/{SRC.name}` (MD5 `{SRC_MD5}`).",
        "",
        "> **Unofficial, experimental, untested on hardware.**",
        "> Flashing modified firmware can brick the monitor. Keep the original",
        "> image and make sure you have a recovery path before trying these.",
        "",
        "| Image | MD5 | Patches | Description |",
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
        "## What the menu action patch does",
        "",
        "The service menu already has **APCS** and **AOCS** entries. In the",
        "stock firmware those entries toggle internal test bits but do not",
        "directly request a refresh. `--menu-actions` redirects the key path",
        "of each entry through a small trampoline in erased bank-9 flash:",
        "",
        "- APCS entry: `0xD12D |= 0x01`",
        "- AOCS entry: `0xD12D |= 0x02`",
        "",
        "The original handler code still runs afterwards, so the stock UI",
        "behaviour is preserved. The request bits are the same ones the",
        "automatic scheduler uses, so the normal completion path clears them.",
        "",
        "## Limits",
        "",
        "- APCS and TSS intervals are 8-bit: 0 = never, 1-254 hours.",
        "- AOCS interval is 16-bit: 0 = never, 1-65534 hours.",
        "- The service menu is still the hidden service menu; this does not",
        "  add a page to the normal OSD.",
        "- The 0xD12D request flag is volatile. The menu action requests a",
        "  refresh for the current session; it does not change the schedule.",
        "",
        "## Before flashing",
        "",
        "1. Confirm the original image still matches",
        f"   `{SRC_MD5}`.",
        "2. Read `firmware/PATCHED/README.md`.",
        "3. Use the same OSD Sidekick version and USB 2.0 port as for the",
        "   original image. Do not interrupt power during the flash.",
        "4. If the monitor does not come back, restore the original image.",
        "",
    ]
    (OUT_DIR / "MANIFEST-custom.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Build a custom FO48U F08 image with verified patches.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--name", default="F08-custom", help="output base name")
    parser.add_argument("--description", default="", help="manifest description")
    parser.add_argument("--unlock", action="store_true", help="remove the APCS/AOCS command gate")
    parser.add_argument("--menu-actions", action="store_true", help="make service-menu APCS/AOCS items request a refresh")
    parser.add_argument("--apcs", type=int, help="APCS interval in hours; 0 = never")
    parser.add_argument("--aocs", type=int, help="AOCS interval in hours; 0 = never")
    parser.add_argument("--tss", type=int, help="panel-care reminder in hours; 0 = never")
    parser.add_argument("--verify", action="store_true", help="verify patch sites and exit")
    parser.add_argument(
        "--preset",
        choices=["menu", "menu-quiet", "menu-no-nag", "menu-care", "all"],
        help="build a named preset (all = every preset)",
    )
    args = parser.parse_args(argv[1:])

    if args.verify:
        verify_all()
        return 0

    presets = {
        "menu": dict(unlock=True, menu_actions=True),
        "menu-quiet": dict(unlock=True, menu_actions=True, apcs=36),
        "menu-no-nag": dict(unlock=True, menu_actions=True, apcs=36, tss=0),
        "menu-care": dict(unlock=True, menu_actions=True, apcs=8, aocs=750, tss=12),
    }
    preset_descriptions = {
        "menu": "stock schedule + service-menu APCS/AOCS actions",
        "menu-quiet": "menu actions + APCS every 36 h",
        "menu-no-nag": "menu actions + APCS 36 h + panel-care reminder disabled",
        "menu-care": "menu actions + APCS 8 h / AOCS 750 h / reminder 12 h",
    }

    verify_all()
    built = []
    if args.preset == "all":
        for preset_name, preset_values in presets.items():
            sub = argparse.Namespace(**vars(args))
            sub.preset = preset_name
            for key, value in preset_values.items():
                setattr(sub, key, value)
            sub.name = f"F08-{preset_name}"
            sub.description = args.description or preset_descriptions[preset_name]
            built.append(build(sub))
    else:
        if args.preset:
            for key, value in presets[args.preset].items():
                setattr(args, key, value)
            if args.name == "F08-custom":
                args.name = f"F08-{args.preset}"
            if not args.description:
                args.description = preset_descriptions[args.preset]
        built.append(build(args))

    write_manifest(built)
    print(f"wrote {OUT_DIR / 'MANIFEST-custom.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
