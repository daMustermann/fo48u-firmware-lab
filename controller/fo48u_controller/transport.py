"""Realtek HID transport wrapper around the installed RtHIDLib.dll."""

from __future__ import annotations

import ctypes
import os
from ctypes import c_ubyte as c_byte, c_int, c_ushort, c_uint, c_void_p
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
        self._opened = False
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
        self._opened = self.dll.Open_HID(self.vid, self.pid) > 0
        if not self._opened:
            # Sidekick also probes the multi-HID list before retrying.
            index = self.dll.Get_mutiHID(self.vid, self.pid)
            if index > 0:
                # Installed RtHIDLib: Open_HID returns a count, whereas
                # Open_mutiHID and I2C operations return zero on success.
                self._opened = self.dll.Open_mutiHID(0) == 0
        if not self._opened:
            raise OSError("Realtek HID device could not be opened")

    def close(self) -> None:
        if self._opened:
            self.dll.Close_HID()
            self._opened = False

    def _require_open(self) -> None:
        if not self._opened:
            raise OSError("Realtek HID device is not open")

    def i2c_write(self, buffer: List[int], slave: int = 0x6E, speed: int = 0) -> int:
        self._require_open()
        if not 1 <= len(buffer) <= 128 or any(type(b) is not int or not 0 <= b <= 255 for b in buffer):
            raise ValueError("I2C write requires 1..128 bytes")
        if not 0 <= slave <= 255 or not 0 <= speed <= 255:
            raise ValueError("slave and speed must be bytes")
        arr = (c_byte * len(buffer))(*buffer)
        ptr = ctypes.cast(arr, c_void_p)
        result = int(self.dll.HID_i2cwrite(ptr, len(buffer), slave, speed))
        if result != 0:
            raise OSError(f"HID_i2cwrite failed: status={result}")
        return result

    def i2c_read(
        self,
        reg_addr: int = 0x51,
        reg_len: int = 1,
        buf_len: int = 36,
        slave: int = 0x6E,
        speed: int = 0,
        timeout: int = 100,
    ) -> List[int]:
        self._require_open()
        if not 1 <= buf_len <= 128 or not 0 <= reg_addr <= 0xFFFFFFFF or not 0 <= reg_len <= 4:
            raise ValueError("invalid I2C read range")
        if not 0 <= slave <= 255 or not 0 <= speed <= 255 or not 0 <= timeout <= 0xFFFFFFFF:
            raise ValueError("invalid I2C slave, speed or timeout")
        arr = (c_byte * buf_len)()
        ptr = ctypes.cast(arr, c_void_p)
        result = int(self.dll.HID_i2cread(reg_addr, reg_len, ptr, buf_len, slave, speed, timeout))
        if result != 0:
            raise OSError(f"HID_i2cread failed: status={result}")
        return [b & 0xFF for b in arr]
