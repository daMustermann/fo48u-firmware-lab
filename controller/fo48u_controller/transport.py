"""Realtek HID transport wrapper around the installed RtHIDLib.dll."""

from __future__ import annotations

import ctypes
import os
from ctypes import c_byte, c_int, c_ushort, c_uint, c_void_p
from typing import List, Optional


DEFAULT_DLL = r"C:\Program Files (x86)\Gigabyte\OSDSidekick\AORUS\RtHIDLib.dll"


def xor_checksum(data: List[int]) -> int:
    value = 0
    for byte in data:
        value ^= byte & 0xFF
    return value & 0xFF


class RtHidTransport:
    """Thin ctypes wrapper for the functions used by OSD Sidekick."""

    def __init__(self, dll_path: str = DEFAULT_DLL, vid: int = 0x0BDA, pid: int = 0x1100):
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"RtHIDLib.dll not found: {dll_path}")
        self.dll = ctypes.CDLL(dll_path)
        self.vid = vid
        self.pid = pid
        self._setup_signatures()

    def _setup_signatures(self) -> None:
        self.dll.Open_HID.argtypes = [c_ushort, c_ushort]
        self.dll.Open_HID.restype = c_int

        self.dll.Close_HID.argtypes = []
        self.dll.Close_HID.restype = None

        self.dll.HID_i2cread.argtypes = [c_uint, c_byte, c_void_p, c_byte, c_byte, c_byte, c_uint]
        self.dll.HID_i2cread.restype = c_int

        self.dll.HID_i2cwrite.argtypes = [c_void_p, c_byte, c_byte, c_byte]
        self.dll.HID_i2cwrite.restype = c_int

        self.dll.Get_mutiHID.argtypes = [c_ushort, c_ushort]
        self.dll.Get_mutiHID.restype = c_int

        self.dll.Open_mutiHID.argtypes = [c_int]
        self.dll.Open_mutiHID.restype = c_int

    def open(self) -> None:
        if not self.dll.Open_HID(self.vid, self.pid):
            # Sidekick also probes the multi-HID list before retrying.
            index = self.dll.Get_mutiHID(self.vid, self.pid)
            if index:
                self.dll.Open_mutiHID(0)

    def close(self) -> None:
        self.dll.Close_HID()

    def i2c_write(self, buffer: List[int], slave: int = 0x6E, speed: int = 0) -> int:
        arr = (c_byte * len(buffer))(*[b & 0xFF for b in buffer])
        ptr = ctypes.cast(arr, c_void_p)
        return int(self.dll.HID_i2cwrite(ptr, len(buffer), slave, speed))

    def i2c_read(
        self,
        reg_addr: int = 0x51,
        reg_len: int = 1,
        buf_len: int = 36,
        slave: int = 0x6E,
        speed: int = 0,
        timeout: int = 100,
    ) -> List[int]:
        arr = (c_byte * buf_len)()
        ptr = ctypes.cast(arr, c_void_p)
        self.dll.HID_i2cread(reg_addr, reg_len, ptr, buf_len, slave, speed, timeout)
        return [b & 0xFF for b in arr]