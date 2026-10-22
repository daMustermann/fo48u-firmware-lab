"""Command-line interface for the FO48U controller skeleton."""

from __future__ import annotations

import argparse
import sys

from .oled import OledCare
from .transport import DEFAULT_DLL, RtHidTransport


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