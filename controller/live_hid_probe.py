#!/usr/bin/env python3
"""Allowlisted F06 status queries through an enforced read-only x86 helper.

HID output reports carry GET requests, not settings writes. No flash/reset,
compensation execution, EEPROM write or arbitrary I2C command is exposed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from fo48u_controller.helper_transport import HelperTransport
from fo48u_controller.oled import OLED_SELECTORS, decode_status_reply, decode_standard_reply

SELECTORS = {0x38: "firmware revision", 0x02: "black equalizer (Sidekick E0/02)",
             0x07: "gamma raw (Sidekick masks low nibble)", **OLED_SELECTORS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("controller/live-hid-probe.json"))
    parser.add_argument("--firmware-label", default=None, help="owner-reported revision; independent from decoded firmware query")
    parser.add_argument("--helper", help="explicit path to a freshly published helper")
    parser.add_argument("--compare-vcp", action="store_true", help="also validate seven allowlisted standard GET replies through HID")
    args = parser.parse_args(argv)
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "owner_reported_firmware": args.firmware_label, "status_only": True,
              "setting_or_flash_writes_sent": 0, "get_query_output_frames_sent": 0,
              "device_firmware": None, "results": {}, "errors": [], "complete": False}

    def save():
        temp = args.output.with_suffix(args.output.suffix + '.tmp')
        temp.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        temp.replace(args.output)

    transport = None
    save()
    try:
        transport = HelperTransport(args.helper, read_only=True)
        transport.open()
        for selector, name in SELECTORS.items():
            record = {"name": name, "validation": "failed", "value": None}
            try:
                report["get_query_output_frames_sent"] += 1
                raw = transport.status_query(selector)
                record["raw_bytes"] = raw
                decoded = decode_status_reply(raw, selector)
                record.update(decoded)
                record["validation"] = "passed"
                if selector == 0x38:
                    high, low = decoded["value"] >> 8, decoded["value"] & 255
                    if high == ord('F') and low <= 99:
                        report["device_firmware"] = {"version": f"F{low:02d}", "source": "validated E0/38 reply", "raw_value": decoded["value"]}
                print(f"GET E0/{selector:02X} {name}: {record['value']} (validated)", flush=True)
            except Exception as exc:
                record["error"] = str(exc)
                report["errors"].append(f"{selector:02X}: {exc}")
                print(f"GET E0/{selector:02X}: {exc}", flush=True)
            report["results"][f"0x{selector:02X}"] = record
            save()
            time.sleep(0.15)
        if args.compare_vcp:
            report['standard_vcp_via_hid'] = {}
            for code in (0x10, 0x12, 0x6C, 0x6E, 0x70, 0xDF, 0xE0):
                row = {'validation': 'failed', 'value': None}
                try:
                    report['get_query_output_frames_sent'] += 1
                    raw = transport.ddc_query(code)
                    row['raw_bytes'] = raw
                    row.update(decode_standard_reply(raw, code))
                    row['validation'] = 'passed'
                    print(f'GET VCP {code:02X} via HID: {row["value"]} (validated)', flush=True)
                except Exception as exc:
                    row['error'] = str(exc)
                    report['errors'].append(f'VCP {code:02X}: {exc}')
                    print(f'GET VCP {code:02X} via HID: {exc}', flush=True)
                report['standard_vcp_via_hid'][f'0x{code:02X}'] = row
                save()
                time.sleep(0.15)
        report["complete"] = True
    except (Exception, KeyboardInterrupt) as exc:
        report["errors"].append(str(exc) or "interrupted")
    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception as exc:
                report["errors"].append(f"helper cleanup: {exc}")
        report['summary'] = {
            'validated_vendor_status_replies': sum(x['validation'] == 'passed' for x in report['results'].values()),
            'validated_standard_replies': sum(x['validation'] == 'passed' for x in report.get('standard_vcp_via_hid', {}).values()),
            'invalid_standard_replies': [code for code, row in report.get('standard_vcp_via_hid', {}).items() if row['validation'] != 'passed'],
        }
        save()
    print(f"Report: {args.output.resolve()}")
    return 0 if report["complete"] and not report["errors"] else 2


if __name__ == '__main__':
    raise SystemExit(main())
