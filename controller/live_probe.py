#!/usr/bin/env python3
"""GET-only Windows DDC/CI diagnostics; never loads the HID controller.

python controller/live_probe.py --list
python controller/live_probe.py --monitor 0 --output live-probe.json

Only FO48U-labelled monitors are selected automatically. --monitor explicitly
selects an enumerated physical monitor. An exhaustive GET sweep cannot prove
that a monitor implements a code correctly or accepts any corresponding SET.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).resolve().parents[1]


class PhysicalMonitor(c.Structure):
    _pack_ = 1  # physicalmonitorenumerationapi.h uses pshpack1.h
    _fields_ = [("handle", w.HANDLE), ("description", w.WCHAR * 128)]


class ReadOnlyDdc:
    """Deliberately exposes no SET, raw-I2C or HID methods."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Windows and Dxva2.dll are required")
        self.user = c.WinDLL("user32", use_last_error=True)
        self.dxva = c.WinDLL("dxva2", use_last_error=True)
        self.callback_type = c.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HANDLE, c.c_void_p, w.LPARAM)
        signatures = {
            "GetNumberOfPhysicalMonitorsFromHMONITOR": [w.HANDLE, c.POINTER(w.DWORD)],
            "GetPhysicalMonitorsFromHMONITOR": [w.HANDLE, w.DWORD, c.POINTER(PhysicalMonitor)],
            "DestroyPhysicalMonitor": [w.HANDLE],
            "GetVCPFeatureAndVCPFeatureReply": [w.HANDLE, w.BYTE, c.POINTER(w.DWORD), c.POINTER(w.DWORD), c.POINTER(w.DWORD)],
            "GetCapabilitiesStringLength": [w.HANDLE, c.POINTER(w.DWORD)],
            "CapabilitiesRequestAndCapabilitiesReply": [w.HANDLE, c.c_void_p, w.DWORD],
        }
        for name, args in signatures.items():
            fn = getattr(self.dxva, name)
            fn.argtypes, fn.restype = args, w.BOOL
        self.user.EnumDisplayMonitors.argtypes = [w.HANDLE, c.c_void_p, self.callback_type, w.LPARAM]
        self.user.EnumDisplayMonitors.restype = w.BOOL
        self.monitors = []
        self.errors = []

        def collect(hmonitor, *_):
            # Never let an exception escape a ctypes callback.
            try:
                count = w.DWORD()
                if not self.dxva.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, c.byref(count)):
                    raise c.WinError(c.get_last_error())
                if not 0 <= count.value <= 64:
                    raise OSError("invalid physical monitor count")
                if count.value:
                    arr = (PhysicalMonitor * count.value)()
                    if not self.dxva.GetPhysicalMonitorsFromHMONITOR(hmonitor, count, arr):
                        raise c.WinError(c.get_last_error())
                    self.monitors.extend(arr)
            except Exception as exc:
                self.errors.append(str(exc))
            return True

        self._callback = self.callback_type(collect)
        if not self.user.EnumDisplayMonitors(None, None, self._callback, 0):
            error = c.get_last_error()
            self.close()
            raise c.WinError(error)

    def inventory(self):
        return [{"index": i, "description": m.description} for i, m in enumerate(self.monitors)]

    def capabilities(self, handle):
        length = w.DWORD()
        if not self.dxva.GetCapabilitiesStringLength(handle, c.byref(length)):
            return {"error": c.get_last_error(), "raw": None}
        if not 1 < length.value <= 65536:
            return {"error": "invalid capabilities length", "raw": None}
        buf = c.create_string_buffer(length.value)
        if not self.dxva.CapabilitiesRequestAndCapabilitiesReply(handle, buf, length.value):
            return {"error": c.get_last_error(), "raw": None}
        return {"error": None, "raw": buf.value.decode("ascii", "replace")}

    def get(self, handle, code):
        kind, current, maximum = w.DWORD(), w.DWORD(), w.DWORD()
        c.set_last_error(0)
        ok = self.dxva.GetVCPFeatureAndVCPFeatureReply(
            handle, code, c.byref(kind), c.byref(current), c.byref(maximum))
        error = c.get_last_error()
        if not ok:
            return {"status": "get_failed", "win32_error": error}
        return {"status": "responded", "current": current.value,
                "maximum_raw": maximum.value, "vcp_type_raw": kind.value,
                "win32_error": None}

    def close(self):
        for monitor in self.monitors:
            self.dxva.DestroyPhysicalMonitor(monitor.handle)
        self.monitors.clear()


def advertised_codes(raw):
    """Read only top-level VCP tokens, excluding nested value enumerations."""
    match = re.search(r"\bvcp\s*\(", raw or "", re.I)
    if not match:
        return None
    depth, tokens, token = 1, [], ""
    for char in raw[match.end():]:
        if char in "()" or char.isspace():
            if depth == 1 and token:
                tokens.append(token)
            token = ""
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return sorted({int(t, 16) for t in tokens if re.fullmatch(r"[0-9a-fA-F]{2}", t)})
        elif depth == 1:
            token += char
    return None  # truncated or malformed capability string


def reference_index(repo=REPO):
    """Literal source comparisons, never a claim that switch cases are VCPs."""
    paths = [repo / "analysis/knowledge_base.json", repo / "analysis/atlas/SWITCH_TABLES.md"]
    kb = json.loads(paths[0].read_text(encoding="utf-8"))
    cases = defaultdict(list)
    heading = ""
    for line_no, line in enumerate(paths[1].read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            heading = line[3:]
        match = re.match(r"\s+- case 0x([0-9A-Fa-f]+) -> (0x[0-9A-Fa-f]+)", line)
        if match and int(match[1], 16) <= 255:
            cases[int(match[1], 16)].append({"heading": heading, "line": line_no, "target": match[2]})
    refs = {}
    for code in range(256):
        refs[f"0x{code:02X}"] = {
            "kb_declared_observation": kb.get("vcp_codes_observed", {}).get(f"0x{code:02X}"),
            "kb_vendor_command": kb.get("command_table", {}).get(f"{code:02X}"),
            "atlas_numeric_case_matches": cases[code],
        }
    return {"files": [{"path": str(p.relative_to(repo)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
            "stock_image": kb["image"], "codes": refs,
            "interpretation": "Numeric atlas/command-table overlap is not a VCP mapping. KB observations are prior claims, not live validation."}


def worker(connection, selected, expected, delay):
    backend = None
    try:
        backend = ReadOnlyDdc()
        connection.send(("inventory", {"monitors": backend.inventory(), "errors": backend.errors}))
        if selected is None:
            return
        if selected >= len(backend.monitors):
            raise OSError("selected monitor no longer exists")
        monitor = backend.monitors[selected]
        if monitor.description != expected:
            raise OSError("monitor inventory changed; rerun --list")
        connection.send(("capabilities", backend.capabilities(monitor.handle)))
        for code in range(256):
            connection.send(("vcp", (code, backend.get(monitor.handle, code))))
            time.sleep(delay)
        connection.send(("done", True))
    except Exception as exc:
        connection.send(("error", str(exc)))
    finally:
        if backend is not None:
            backend.close()
        connection.close()


def collect(selected, expected, delay, timeout, on_event):
    """Isolate driver calls so a hung GET cannot block the parent indefinitely."""
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(child, selected, expected, delay))
    process.start()
    child.close()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() >= deadline:
                on_event("error", "probe deadline exceeded; worker terminated; report is partial")
                break
            try:
                available = parent.poll(0.2)
            except (EOFError, BrokenPipeError):
                break
            if available:
                try:
                    kind, value = parent.recv()
                except (EOFError, BrokenPipeError):
                    break
                on_event(kind, value)
            elif not process.is_alive():
                break
    except KeyboardInterrupt:
        on_event("error", "interrupted; report is partial")
    finally:
        if process.is_alive():
            process.terminate()
        process.join(5)
        parent.close()


def summarize(report):
    replies = {code: row for code, row in report["vcp"].items() if row["status"] == "responded"}
    groups = defaultdict(list)
    for code, row in replies.items():
        groups[(row["current"], row["maximum_raw"], row["vcp_type_raw"])].append(code)
    return {"responded": len(replies),
            "get_failed": sum(row["status"] == "get_failed" for row in report["vcp"].values()),
            "not_attempted": sum(row["status"] == "not_attempted" for row in report["vcp"].values()),
            "identical_reply_groups": [codes for codes in groups.values() if len(codes) > 1],
            "interpretation": "A successful GET is a response observation, not SET acceptance or proof of vendor-handler reachability. Identical replies can be legitimate or generic fallback. Maximum is undefined for non-continuous controls."}


def save_report(path, report):
    report["summary"] = summarize(report)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def firmware_identity(label=None):
    return {"version": label, "source": "operator_supplied" if label else "unknown",
            "verified_by_probe": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="enumerate only; no DDC queries")
    parser.add_argument("--monitor", type=int, help="physical monitor index from --list")
    parser.add_argument("--output", type=Path, default=Path("live-probe.json"))
    parser.add_argument("--firmware-label", help="operator-reported installed firmware, e.g. F06; not detected or verified by the probe")
    parser.add_argument("--delay", type=float, default=0.10, help="seconds between GET requests (minimum 0.05)")
    parser.add_argument("--timeout", type=float, default=180, help="scan deadline in seconds")
    args = parser.parse_args(argv)
    if not math.isfinite(args.delay) or not math.isfinite(args.timeout) or args.delay < 0.05 or args.timeout <= 0 or (args.monitor is not None and args.monitor < 0):
        parser.error("invalid delay, timeout or monitor index")
    inventory, errors = [], []

    def discovery(kind, value):
        if kind == "inventory":
            inventory.extend(value["monitors"])
            errors.extend(value["errors"])
        elif kind == "error":
            errors.append(value)

    collect(None, None, args.delay, 15, discovery)
    if args.list:
        print(json.dumps({"monitors": inventory, "errors": errors}, indent=2))
        return 0 if inventory else 2
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "device_firmware": firmware_identity(args.firmware_label),
              "comparison_scope": "Static references describe F08. Live GET responses do not establish the same behavior on F08; the installed revision is not detected by this probe.",
              "transport": "Windows Dxva2 GET VCP only", "writes_sent": 0,
              "inventory": inventory, "errors": errors, "complete": False,
              "references": reference_index(), "capabilities": None,
              "vcp": {f"0x{code:02X}": {"status": "not_attempted"} for code in range(256)}}
    selected = args.monitor
    if selected is None:
        matches = [m["index"] for m in inventory if "FO48U" in m["description"].upper()]
        if len(matches) == 1:
            selected = matches[0]
    if selected is None or selected >= len(inventory):
        report["errors"].append("No unique FO48U target; use --list and explicitly select --monitor INDEX")
        save_report(args.output, report)
        print(f"No scan performed. Inventory and errors: {args.output.resolve()}")
        return 2
    report["selected_monitor"] = inventory[selected]
    save_report(args.output, report)

    def event(kind, value):
        if kind == "capabilities":
            report[kind] = value
        elif kind == "vcp":
            code, row = value
            advertised = advertised_codes((report["capabilities"] or {}).get("raw"))
            row["advertised"] = None if advertised is None else code in advertised
            report["vcp"][f"0x{code:02X}"] = row
            if code % 32 == 0:
                print(f"GET sweep: {code + 1}/256", flush=True)
        elif kind == "error":
            report["errors"].append(value)
        elif kind == "done":
            report["complete"] = True
        save_report(args.output, report)

    collect(selected, inventory[selected]["description"], args.delay, args.timeout, event)
    if not report["complete"] and not report["errors"]:
        report["errors"].append("worker ended without completing sweep")
    save_report(args.output, report)
    print(f"Report: {args.output.resolve()} ({report['summary']['responded']} GET responses; complete={report['complete']})")
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
