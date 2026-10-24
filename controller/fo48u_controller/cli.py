"""Command-line interface for the FO48U controller skeleton."""

from __future__ import annotations

import argparse
import sys

from .oled import OledCare, OLED_SELECTORS
from .transport import DEFAULT_DLL, RtHidTransport
from .ddcci import VCP_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FO48U host-side controller (safety-gated)")
    parser.add_argument("--dll", default=DEFAULT_DLL, help="path to RtHIDLib.dll")
    parser.add_argument("--send", action="store_true", help="actually open the HID device and send frames")
    parser.add_argument("--allow-unverified-oled-execution", action="store_true",
                        help="permit sending unverified APCS/AOCS execution frames")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="read panel/APCS/AOCS hours and enable flags")

    apcs = sub.add_parser("execute-apcs", help="send the APCS execution frame")
    apcs.add_argument("--yes", action="store_true", help="confirm the unverified action")

    aocs = sub.add_parser("execute-aocs", help="send the AOCS execution frame")
    aocs.add_argument("--yes", action="store_true", help="confirm the unverified action")

    scan = sub.add_parser("scan-vcp", help="scan all DDC/CI VCP codes")
    scan.add_argument("--code", type=lambda x: int(x, 0), help="scan a single VCP code")

    dump = sub.add_parser("dump-state", help="dump OLED selectors and VCP state")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = not args.send

    if dry_run:
        transport = None
    else:
        transport = RtHidTransport(args.dll)
        transport.open()

    care = OledCare(
        transport=transport if transport is not None else _NullTransport(),
        dry_run=dry_run,
        allow_execute=args.allow_unverified_oled_execution,
    )

    try:
        if args.command == "info":
            print("panel_hours:", care.read_panel_hours())
            print("apcs_time:", care.read_apcs_time())
            print("aocs_time:", care.read_aocs_time())
            print("apcs_enable:", care.read_apcs_enable())
            print("aocs_enable:", care.read_aocs_enable())
        elif args.command == "execute-apcs":
            frame = care.execute_apcs(confirmed=args.yes)
            print("frame:", " ".join(f"{b:02x}" for b in frame))
        elif args.command == "execute-aocs":
            frame = care.execute_aocs(confirmed=args.yes)
            print("frame:", " ".join(f"{b:02x}" for b in frame))
        elif args.command == "scan-vcp":
            from .ddcci import DdcCi
            ddc = DdcCi()
            try:
                if getattr(args, "code", None) is not None:
                    for phys in ddc.physical_monitors():
                        current, maximum = ddc.get_vcp(phys.hPhysicalMonitor, args.code)
                        print(f"VCP 0x{args.code:02X} {VCP_NAMES.get(args.code, '')}: current={current} max={maximum}")
                else:
                    for code, (current, maximum) in ddc.scan_vcp().items():
                        if current is not None:
                            print(f"VCP 0x{code:02X} {VCP_NAMES.get(code, '')}: current={current} max={maximum}")
            finally:
                ddc.close()
        elif args.command == "dump-state":
            print("OLED selectors:")
            for selector, name in OLED_SELECTORS.items():
                print(f"  0x{selector:02X} {name}: {care._read(selector) if hasattr(care, '_read') else 'n/a'}")
            from .ddcci import DdcCi
            ddc = DdcCi()
            try:
                print("VCP state:")
                for code, (current, maximum) in ddc.scan_vcp().items():
                    if current is not None:
                        print(f"  0x{code:02X} {VCP_NAMES.get(code, '')}: current={current} max={maximum}")
            finally:
                ddc.close()
    finally:
        if transport is not None:
            transport.close()
    return 0


class _NullTransport:
    def i2c_write(self, *a, **k):
        return 0

    def i2c_read(self, *a, **k):
        return [0] * 36


if __name__ == "__main__":
    raise SystemExit(main())