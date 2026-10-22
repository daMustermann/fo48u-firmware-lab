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

    def close(self) -> None:
        for _, phys_list in self.monitors:
            arr = (PHYSICAL_MONITOR * len(phys_list))(*phys_list)
            self.dxva2.DestroyPhysicalMonitors(len(phys_list), arr)