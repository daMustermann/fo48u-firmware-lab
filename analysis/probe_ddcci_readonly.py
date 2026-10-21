#!/usr/bin/env python3
"""Read-only Windows DDC/CI probe for the connected FO48U.

Only GetCapabilitiesStringLength, CapabilitiesRequestAndCapabilitiesReply and
GetVCPFeatureAndVCPFeatureReply are used. No SetVCPFeature or other writes.
"""

import argparse
import ctypes as c
import sys
from ctypes import wintypes as w


class PhysicalMonitor(c.Structure):
    _fields_ = [("handle", w.HANDLE), ("description", w.WCHAR * 128)]


def run(codes: list[int]) -> None:
    if sys.platform != "win32":
        raise SystemExit("This probe requires Windows and DXVA2")

    user = c.WinDLL("user32", use_last_error=True)
    dxva = c.WinDLL("dxva2", use_last_error=True)
    dxva.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    dxva.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = w.BOOL
    dxva.GetPhysicalMonitorsFromHMONITOR.argtypes = [
        w.HANDLE, w.DWORD, c.POINTER(PhysicalMonitor)
    ]
    dxva.GetPhysicalMonitorsFromHMONITOR.restype = w.BOOL
    dxva.DestroyPhysicalMonitor.argtypes = [w.HANDLE]
    dxva.DestroyPhysicalMonitor.restype = w.BOOL
    dxva.GetVCPFeatureAndVCPFeatureReply.argtypes = [
        w.HANDLE, w.BYTE, c.POINTER(w.DWORD), c.POINTER(w.DWORD), c.POINTER(w.DWORD)
    ]
    dxva.GetVCPFeatureAndVCPFeatureReply.restype = w.BOOL
    dxva.GetCapabilitiesStringLength.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    dxva.GetCapabilitiesStringLength.restype = w.BOOL
    dxva.CapabilitiesRequestAndCapabilitiesReply.argtypes = [
        w.HANDLE, c.c_void_p, w.DWORD
    ]
    dxva.CapabilitiesRequestAndCapabilitiesReply.restype = w.BOOL

    seen = 0
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HANDLE, c.c_void_p, w.LPARAM)

    def on_monitor(hmonitor: int, _hdc: int, _rect: int, _data: int) -> bool:
        nonlocal seen
        count = w.DWORD()
        if not dxva.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, c.byref(count)):
            print("Physical-monitor count error:", c.get_last_error())
            return True
        monitors = (PhysicalMonitor * count.value)()
        if not dxva.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, monitors):
            print("Physical-monitor handle error:", c.get_last_error())
            return True
        for monitor in monitors:
            seen += 1
            print("Monitor:", monitor.description)
            try:
                length = w.DWORD()
                if dxva.GetCapabilitiesStringLength(monitor.handle, c.byref(length)):
                    if 1 < length.value <= 65536:
                        buf = c.create_string_buffer(length.value)
                        if dxva.CapabilitiesRequestAndCapabilitiesReply(
                            monitor.handle, buf, length.value
                        ):
                            print("DDC capabilities:", buf.value.decode("ascii", "replace"))
                        else:
                            print("DDC capabilities read error:", c.get_last_error())
                for code in codes:
                    value, maximum, kind = w.DWORD(), w.DWORD(), w.DWORD()
                    success = dxva.GetVCPFeatureAndVCPFeatureReply(
                        monitor.handle, code, c.byref(kind), c.byref(value), c.byref(maximum)
                    )
                    if success:
                        print(f"GET VCP {code:02X}: current={value.value:04X} "
                              f"max={maximum.value:04X} type={kind.value}")
                    else:
                        print(f"GET VCP {code:02X}: error={c.get_last_error()}")
            finally:
                dxva.DestroyPhysicalMonitor(monitor.handle)
        return True

    callback = callback_type(on_monitor)
    user.EnumDisplayMonitors.argtypes = [w.HANDLE, c.c_void_p, callback_type, w.LPARAM]
    user.EnumDisplayMonitors.restype = w.BOOL
    if not user.EnumDisplayMonitors(None, None, callback, 0):
        raise OSError(c.get_last_error(), "EnumDisplayMonitors failed")
    if not seen:
        print("No attached physical monitors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codes", nargs="*", default=["10", "DF", "E0", "E1"],
                        help="VCP codes in hex (read only)")
    args = parser.parse_args()
    codes = [int(item, 16) for item in args.codes]
    if any(not 0 <= code <= 255 for code in codes):
        parser.error("VCP codes must be 00..FF")
    run(codes)
