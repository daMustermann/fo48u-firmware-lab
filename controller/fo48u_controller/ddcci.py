"""DDC/CI helpers for standard monitor controls (Windows)."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import List, Tuple


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128),
    ]


MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


class DdcCi:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.dxva2 = ctypes.windll.dxva2
        self.monitors: List[Tuple[wintypes.HMONITOR, List[PHYSICAL_MONITOR]]] = []
        self._enum()

    def _enum(self) -> None:
        self.monitors.clear()

        def callback(hmonitor, hdc, rect, data):
            count = wintypes.DWORD()
            if self.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmonitor, ctypes.byref(count)):
                arr = (PHYSICAL_MONITOR * count.value)()
                if self.dxva2.GetPhysicalMonitorsFromHMONITOR(hmonitor, count.value, arr):
                    self.monitors.append((hmonitor, list(arr)))
            return True

        self.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)

    def physical_monitors(self):
        for _, phys_list in self.monitors:
            for phys in phys_list:
                yield phys

    def get_vcp(self, handle, code: int):
        vcp_type = wintypes.DWORD()
        current = wintypes.DWORD()
        maximum = wintypes.DWORD()
        ok = self.dxva2.GetVCPFeatureAndVCPFeatureReply(handle, code, ctypes.byref(vcp_type),
                                                         ctypes.byref(current), ctypes.byref(maximum))
        if not ok:
            return None, None
        return int(current.value), int(maximum.value)

    def set_vcp(self, handle, code: int, value: int) -> bool:
        return bool(self.dxva2.SetVCPFeature(handle, code, value))


    def scan_vcp(self) -> dict[int, tuple[int | None, int | None]]:
        result = {}
        for code in range(0x100):
            found = False
            for phys in self.physical_monitors():
                current, maximum = self.get_vcp(phys.hPhysicalMonitor, code)
                if current is not None:
                    result[code] = (current, maximum)
                    found = True
                    break
            if not found:
                result[code] = (None, None)
        return result


    def scan_vcp(self) -> dict[int, tuple[int | None, int | None]]:
        result = {}
        for code in range(0x100):
            found = False
            for phys in self.physical_monitors():
                current, maximum = self.get_vcp(phys.hPhysicalMonitor, code)
                if current is not None:
                    result[code] = (current, maximum)
                    found = True
                    break
            if not found:
                result[code] = (None, None)
        return result

    def close(self) -> None:
        for _, phys_list in self.monitors:
            arr = (PHYSICAL_MONITOR * len(phys_list))(*phys_list)
            self.dxva2.DestroyPhysicalMonitors(len(phys_list), arr)


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
    0x6C: "Black level",
    0x6E: "Black stabilizer",
    0x70: "Gamma",
    0x87: "Sharpness",
    0xAC: "Horizontal frequency",
    0xAE: "Vertical frequency",
    0xB2: "Source timing mode / OLED care",
    0xCA: "OSD / button control",
    0xCC: "OSD language",
    0xD6: "Power mode",
    0xDF: "Manufacturer specific",
    0xE0: "Manufacturer specific",
}

SIDEKICK_COMMANDS = {
    0x80: "APCS compensation request (D12D bit 0 when CFDE == 2)",
    0x82: "AOCS compensation request (D12D bit 1 when CFDE == 2)",
    0x55: "Virtual OSD key/event selector (crosshair / event injection)",
}


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
    0x6C: "Black level",
    0x6E: "Black stabilizer",
    0x70: "Gamma",
    0x87: "Sharpness",
    0xAC: "Horizontal frequency",
    0xAE: "Vertical frequency",
    0xB2: "Source timing mode / OLED care",
    0xCA: "OSD / button control",
    0xCC: "OSD language",
    0xD6: "Power mode",
    0xDF: "Manufacturer specific",
    0xE0: "Manufacturer specific",
}

SIDEKICK_COMMANDS = {
    0x80: "APCS compensation request (D12D bit 0 when CFDE == 2)",
    0x82: "AOCS compensation request (D12D bit 1 when CFDE == 2)",
    0x55: "Virtual OSD key/event selector (crosshair / event injection)",
}
