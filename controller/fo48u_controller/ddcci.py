"""DDC/CI helpers for standard monitor controls (Windows)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import List, Tuple


class PHYSICAL_MONITOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


class DdcCi:
    def __init__(self):
        import sys
        if sys.platform != "win32":
            raise OSError("DDC/CI requires Windows")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.dxva2 = ctypes.WinDLL("dxva2", use_last_error=True)
        self.monitors: List[Tuple[wintypes.HMONITOR, List[PHYSICAL_MONITOR]]] = []
        self.last_error = None
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
            wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        self.user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p,
                                                    self.callback_type, wintypes.LPARAM]
        self.user32.EnumDisplayMonitors.restype = wintypes.BOOL
        signatures = {
            "GetNumberOfPhysicalMonitorsFromHMONITOR": [wintypes.HMONITOR, ctypes.POINTER(wintypes.DWORD)],
            "GetPhysicalMonitorsFromHMONITOR": [wintypes.HMONITOR, wintypes.DWORD, ctypes.POINTER(PHYSICAL_MONITOR)],
            "GetVCPFeatureAndVCPFeatureReply": [wintypes.HANDLE, wintypes.BYTE, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)],
            "SetVCPFeature": [wintypes.HANDLE, wintypes.BYTE, wintypes.DWORD],
            "DestroyPhysicalMonitors": [wintypes.DWORD, ctypes.POINTER(PHYSICAL_MONITOR)],
        }
        for name, args in signatures.items():
            fn = getattr(self.dxva2, name)
            fn.argtypes, fn.restype = args, wintypes.BOOL
        self._enum()

    def _enum(self) -> None:
        self.close()
        errors = []

        def callback(hmonitor, hdc, rect, data):
            try:
                count = wintypes.DWORD()
                if not self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, ctypes.byref(count)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not 0 <= count.value <= 64:
                    raise OSError("invalid monitor count")
                if count.value:
                    arr = (PHYSICAL_MONITOR * count.value)()
                    if not self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, arr):
                        raise ctypes.WinError(ctypes.get_last_error())
                    self.monitors.append((hmonitor, list(arr)))
            except Exception as exc:
                errors.append(exc)
            return True

        self._callback = self.callback_type(callback)
        ok = self.user32.EnumDisplayMonitors(None, None, self._callback, 0)
        if not ok or errors:
            error = errors[0] if errors else ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def physical_monitors(self):
        for _, phys_list in self.monitors:
            yield from phys_list

    def get_vcp(self, handle, code: int):
        if not 0 <= code <= 255:
            raise ValueError("VCP code must be 00..FF")
        vcp_type, current, maximum = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        ok = self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, code, ctypes.byref(vcp_type),
                                                       ctypes.byref(current), ctypes.byref(maximum))
        self.last_error = None if ok else ctypes.get_last_error()
        if not ok:
            return None, None
        return int(current.value), int(maximum.value)

    def set_vcp(self, handle, code: int, value: int) -> bool:
        if not 0 <= code <= 255 or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("invalid VCP code or value")
        return bool(self.dxva2.SetVCPFeature(handle, code, value))

    def scan_vcp(self) -> dict[int, tuple[int | None, int | None]]:
        # Compatibility API: first response across monitors. Use live_probe.py
        # for reports tied to one explicitly selected monitor.
        result = {}
        for code in range(0x100):
            result[code] = (None, None)
            for phys in self.physical_monitors():
                current, maximum = self.get_vcp(phys.hPhysicalMonitor, code)
                if current is not None:
                    result[code] = (current, maximum)
                    break
        return result

    def close(self) -> None:
        for _, phys_list in self.monitors:
            arr = (PHYSICAL_MONITOR * len(phys_list))(*phys_list)
            self.dxva2.DestroyPhysicalMonitors(len(phys_list), arr)
        self.monitors.clear()


VCP_NAMES = {
    0x02: "New control value",
    0x04: "Restore factory defaults",
    0x0B: "Color temperature request",
    0x0C: "Image mode",
    0x10: "Brightness",
    0x12: "Contrast",
    0x14: "Select color preset",
    0x16: "Red gain",
    0x18: "Green gain",
    0x1A: "Blue gain",
    0x60: "Input select",
    0x62: "Volume",
    0x6C: "Video black level: Red",
    0x6E: "Video black level: Green",
    0x70: "Video black level: Blue",
    0x87: "Sharpness",
    0xAC: "Horizontal frequency",
    0xAE: "Vertical frequency",
    0xB2: "Source timing mode / OLED care",
    0xCA: "OSD / button control",
    0xCC: "OSD language",
    0xD6: "Power mode",
    0xDF: "MCCS/VCP version",
    0xE0: "Manufacturer specific",
}

SIDEKICK_COMMANDS = {
    0x80: "APCS compensation request (D12D bit 0 when CFDE == 2)",
    0x82: "AOCS compensation request (D12D bit 1 when CFDE == 2)",
    0x55: "Virtual OSD key/event selector (crosshair / event injection)",
}
