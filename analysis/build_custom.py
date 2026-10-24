#!/usr/bin/env python3
"""Offline FO48U F08 firmware experiments; DO NOT FLASH outputs.

Use --verify for static byte checks. --emit-offline-research explicitly
permits creating local unvalidated research files.
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

# The menu engine has FOUR direct calls to 9:0x97DB. In the host-command
# path (9:0xD584), R3 can be zero with R5=1 too! Patching the shared item
# handlers therefore triggers unintended refresh requests. Scope the patch
# exclusively to the E057 path at 9:0xE0E2. That path is now proven
# unreachable for actions 23/24: retain the implementation for research only.
MENU_UI_CALL_SITE = (9, 0xE0E2, bytes.fromhex("12 97 DB"))
MENU_UI_TRAMPOLINE = 0xFEFA
MENU_TRAMPOLINE_SIZE = 36


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
        raise SystemExit("APCS must be 0 (encoded as 255 h) or 1-255 hours")
    put(data, bank, addr, bytes([0x94, value]))
    value_text = "255 h maximum / effectively off" if value == 0xFF else f"{value} h"
    notes.append(
        f"bank 13 0x{addr:04X}: APCS interval `subb a,#0x04` -> "
        f"`subb a,#0x{value:02X}` ({value_text})"
    )


def patch_aocs(data: bytearray, hours: int, notes: list[str]) -> None:
    bank, addr, expected = AOCS_SITE
    expect(data, bank, addr, expected, "AOCS divisor")
    value = 0xFFFF if hours <= 0 else hours
    if not 1 <= value <= 0xFFFF:
        raise SystemExit("AOCS must be 0 (encoded as 65535 h) or 1-65535 hours")
    hi, lo = (value >> 8) & 0xFF, value & 0xFF
    put(data, bank, addr, bytes([0x7C, hi, 0x7D, lo]))
    value_text = "65535 h maximum / effectively off" if value == 0xFFFF else f"{value} h"
    notes.append(
        f"bank 13 0x{addr:04X}: AOCS divisor 0x05DC -> "
        f"0x{hi:02X}{lo:02X} ({value_text})"
    )


def patch_tss(data: bytearray, hours: int, notes: list[str]) -> None:
    bank, addr, expected = TSS_SITE
    expect(data, bank, addr, expected, "TSS interval")
    value = 0xFF if hours <= 0 else hours
    if not 1 <= value <= 0xFF:
        raise SystemExit("TSS must be 0 (encoded as 255 h) or 1-255 hours")
    put(data, bank, addr, bytes([0x94, value]))
    value_text = "255 h maximum / effectively off" if value == 0xFF else f"{value} h"
    notes.append(
        f"bank 13 0x{addr:04X}: panel-care reminder `subb a,#0x24` -> "
        f"`subb a,#0x{value:02X}` ({value_text})"
    )


def patch_menu_actions(data: bytearray, notes: list[str]) -> None:
    """Intercept only UI dispatch. R5 != 0, R3 == 0, item 23/24 required.

    The wrapper uses only A and DPTR, which are overwritten on entry to the
    original dispatcher 0x97DB. Its LJMP tail call retains the existing return
    address, stack depth and R3/R5/R7. Hardware behavior remains untested.
    """
    expect(data, *MENU_UI_CALL_SITE, "interactive-menu dispatcher call")
    expect(data, 9, MENU_UI_TRAMPOLINE, b"\xFF" * MENU_TRAMPOLINE_SIZE, "menu trampoline space")

    # FEFA: mov a,r5; jz skip; mov a,r3; jnz skip; mov a,r7;
    #       cjne a,#23,check_aocs; request bit 0; ljmp 97DB;
    # check_aocs: cjne a,#24,skip; request bit 1; ljmp 97DB;
    # skip: ljmp 97DB.  All conditional targets are instruction boundaries.
    wrapper = bytes.fromhex(
        "ED 60 1E EB 70 1B EF B4 17 0A "
        "90 D1 2D E0 44 01 F0 02 97 DB "
        "B4 18 0A 90 D1 2D E0 44 02 F0 02 97 DB "
        "02 97 DB"
    )
    assert len(wrapper) == MENU_TRAMPOLINE_SIZE
    put(data, 9, MENU_UI_TRAMPOLINE, wrapper)
    put(data, 9, MENU_UI_CALL_SITE[1], bytes.fromhex("12 FE FA"))
    notes.append(
        "bank 9 0xE0E2: UI-only call to trampoline 0xFEFA; "
        "if R5!=0 and R3==0 and R7==23/24, request 0xD12D bit0/bit1; "
        "tail-jump to stock dispatcher 0x97DB; other callers untouched"
    )


def verify_all() -> None:
    data = load_source()
    checks = [
        ("unlock APCS", *UNLOCK_SITES[0]),
        ("unlock AOCS", *UNLOCK_SITES[1]),
        ("APCS interval", *APCS_SITE),
        ("AOCS divisor", *AOCS_SITE),
        ("TSS interval", *TSS_SITE),
        ("UI dispatcher call", *MENU_UI_CALL_SITE),
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
    for name, addr in [("menu trampoline space", MENU_UI_TRAMPOLINE)]:
        off = file_offset(9, addr)
        got = bytes(data[off : off + MENU_TRAMPOLINE_SIZE])
        if got != b"\xFF" * MENU_TRAMPOLINE_SIZE:
            raise SystemExit(f"{name} at 0x{addr:04x} is not erased: {got.hex(' ')}")
        print(f"  {'OK':8s} {name:20s} bank  9 0x{addr:04x} is erased")
    print("all patch sites match the original image")


def build(args: argparse.Namespace) -> dict[str, object]:
    if args.menu_actions and not args.allow_unreachable_menu_prototype:
        raise SystemExit(
            "REFUSED: --menu-actions hooks bank 9 E0E2, but E057's direct "
            "callers only request IDs 11/14, never APCS=23/AOCS=24. "
            "The patch is nonfunctional and DO NOT FLASH. For offline "
            "research only, pass --allow-unreachable-menu-prototype."
        )
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
        patches.append(f"apcs-{args.apcs or 255}")
    if args.aocs is not None:
        patch_aocs(data, args.aocs, notes)
        patches.append(f"aocs-{args.aocs or 65535}")
    if args.tss is not None:
        patch_tss(data, args.tss, notes)
        patches.append(f"tss-{args.tss or 255}")

    if not patches:
        raise SystemExit("nothing selected; use --unlock, --menu-actions, --apcs, --aocs or --tss")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.name}.bin"
    if out.exists() and not args.overwrite:
        raise SystemExit(
            f"output already exists: {out}. Choose a new --name, "
            "or explicitly pass --overwrite to replace it"
        )
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
        "> **Unofficial, experimental, untested on hardware. DO NOT FLASH.**",
        "> The `menu-actions` implementation is a known unreachable prototype:",
        "> E057 is only called for action IDs 11/14, not APCS=23/AOCS=24.",
        "> No validated firmware release or recovery procedure exists. DO NOT FLASH.",
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
        "directly request a refresh. The UNREACHABLE PROTOTYPE intercepts the",
        "interactive-menu call at bank 9 `0xE0E2`, checks item and key class,",
        "and continues through the stock dispatcher:",
        "",
        "- APCS entry: `0xD12D |= 0x01`",
        "- AOCS entry: `0xD12D |= 0x02`",
        "",
        "But direct E057 callers pass only IDs 11/14, so this wrapper does",
        "not run for service items 23/24. DO NOT FLASH these research images.",
        "",
        "## Limits",
        "",
        "- APCS and TSS intervals are 8-bit: `0` encodes `0xFF` (255 h), the",
        "  maximum; this is effectively off in normal use, not a hard disable.",
        "- AOCS interval is 16-bit: `0` encodes `0xFFFF` (65535 h), effectively",
        "  never for the panel's lifetime.",
        "- The service menu is still the hidden service menu; this does not",
        "  add a page to the normal OSD.",
        "- D12D request flags are volatile; a valid physical selection path",
        "  to this code has not been demonstrated.",
        "",
        "## Research status",
        "",
        "These binaries are reference-only. APCS/AOCS menu behavior is not fixed.",
        "",
    ]
    (OUT_DIR / "MANIFEST-custom.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate offline FO48U F08 research files (DO NOT FLASH).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--name", default="F08-custom", help="output base name")
    parser.add_argument("--description", default="", help="manifest description")
    parser.add_argument("--unlock", action="store_true", help="OFFLINE RESEARCH ONLY / DO NOT FLASH: remove unvalidated APCS/AOCS command operand check")
    parser.add_argument("--menu-actions", action="store_true", help="unreachable APCS/AOCS menu-hook prototype (disabled by default)")
    parser.add_argument("--allow-unreachable-menu-prototype", action="store_true",
                        help="explicitly emit known nonfunctional prototype for OFFLINE RESEARCH ONLY; DO NOT FLASH")
    parser.add_argument("--apcs", type=int, help="APCS interval in hours; 0 encodes 255 h (maximum)")
    parser.add_argument("--aocs", type=int, help="AOCS interval in hours; 0 encodes 65535 h (maximum)")
    parser.add_argument("--tss", type=int, help="TSS reminder in hours; 0 encodes 255 h (maximum)")
    parser.add_argument("--verify", action="store_true", help="verify patch sites and exit")
    parser.add_argument("--emit-offline-research", action="store_true",
                        help="explicitly permit local, unflashable research output")
    parser.add_argument("--overwrite", action="store_true", help="explicitly allow replacing existing output images")
    parser.add_argument("--no-manifest", action="store_true", help="retain the existing multi-variant manifest")
    parser.add_argument(
        "--preset",
        choices=["menu", "menu-quiet", "menu-no-nag", "menu-care", "all"],
        help="build a named preset (all = every preset)",
    )
    args = parser.parse_args(argv[1:])

    if args.verify:
        verify_all()
        return 0

    if not args.emit_offline_research:
        parser.error("No validated firmware release. Use --verify or "
                     "--emit-offline-research for local experiments (DO NOT FLASH).")

    presets = {
        "menu": dict(unlock=True, menu_actions=True),
        "menu-quiet": dict(unlock=True, menu_actions=True, apcs=36),
        "menu-no-nag": dict(unlock=True, menu_actions=True, apcs=36, tss=0),
        "menu-care": dict(unlock=True, menu_actions=True, apcs=8, aocs=750, tss=12),
        "full-control": dict(unlock=True),
    }
    preset_descriptions = {
        "menu": "unreachable menu prototype with stock schedule",
        "menu-quiet": "unreachable menu prototype + APCS 36 h; TSS unchanged",
        "menu-no-nag": "unreachable menu prototype + APCS 36 h + TSS 255 h",
        "menu-care": "unreachable menu prototype + APCS 8 h / AOCS 750 h / TSS 12 h",
        "full-control": "unlock command gate + documented host-side full software-control profile",
    }
    # Explicitly label the UI-scoped, unreachable research implementation.
    preset_output_names = {
        "menu": "F08-menu-ui-scoped",
        "menu-quiet": "F08-menu-ui-scoped-quiet",
        "menu-no-nag": "F08-menu-ui-scoped-no-nag",
        "menu-care": "F08-menu-ui-scoped-care",
    }

    verify_all()
    built = []
    if args.preset == "all":
        for preset_name, preset_values in presets.items():
            sub = argparse.Namespace(**vars(args))
            sub.preset = preset_name
            for key, value in preset_values.items():
                setattr(sub, key, value)
            sub.name = preset_output_names[preset_name]
            sub.description = args.description or preset_descriptions[preset_name]
            built.append(build(sub))
    else:
        if args.preset:
            for key, value in presets[args.preset].items():
                setattr(args, key, value)
            if args.name == "F08-custom":
                args.name = preset_output_names[args.preset]
            if not args.description:
                args.description = preset_descriptions[args.preset]
        built.append(build(args))

    if not args.no_manifest:
        write_manifest(built)
        print(f"wrote {OUT_DIR / 'MANIFEST-custom.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
