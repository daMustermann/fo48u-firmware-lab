"""OLED care readback and (gated) execution helpers."""

from __future__ import annotations

import time
from typing import Callable, List, Optional

from .transport import RtHidTransport, xor_checksum

OLED_SELECTORS = {
    0x7F: "panel hours",
    0x80: "APCS enable/status",
    0x81: "APCS elapsed time",
    0x82: "AOCS enable/status",
    0x83: "AOCS elapsed time",
}


class OledCare:
    def __init__(
        self,
        transport: RtHidTransport,
        dry_run: bool = True,
        allow_execute: bool = False,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.transport = transport
        self.dry_run = dry_run
        self.allow_execute = allow_execute
        self.sleeper = sleeper

    def _read(self, selector: int) -> Optional[int]:
        frame = [0x51, 0x83, 0x01, 0xE0, selector]
        frame.append(xor_checksum(frame))
        frame += [0] * (36 - len(frame))

        if self.dry_run:
            return None

        self.transport.i2c_write(frame, 0x6E, 0)
        self.sleeper(0.15)
        response = self.transport.i2c_read(0x51, 1, 36, 0x6E, 0, 100)
        self.sleeper(0.15)
        return (response[8] << 8) | response[9]

    def read_panel_hours(self) -> Optional[int]:
        return self._read(0x7F)

    def read_apcs_time(self) -> Optional[int]:
        return self._read(0x81)

    def read_aocs_time(self) -> Optional[int]:
        return self._read(0x83)

    def read_apcs_enable(self) -> Optional[int]:
        return self._read(0x80)

    def read_aocs_enable(self) -> Optional[int]:
        return self._read(0x82)

    def read_all(self) -> dict[int, Optional[int]]:
        return {selector: self._read(selector) for selector in OLED_SELECTORS}

    def inject_osd_event(self, selector: int, operand: int = 0x02, confirmed: bool = False) -> List[int]:
        """Send a virtual OSD key/event frame (Sidekick E0 family)."""
        return self.execute(selector, operand, confirmed=confirmed)

    def virtual_key(self, code: int, confirmed: bool = False) -> List[int]:
        return self.execute(0x55, code & 0xFF, confirmed=confirmed)

    def execute(self, selector: int, operand: int = 0x02, confirmed: bool = False) -> List[int]:
        if self.dry_run:
            frame = [0x51, 0x85, 0x03, 0xE0, selector, 0x00, operand]
            frame.append(xor_checksum(frame))
            frame += [0] * (32 - len(frame))
            return frame

        if not self.allow_execute or not confirmed:
            raise PermissionError(
                "OLED-care execution is unverified; pass allow_execute=True and confirmed=True"
            )

        frame = [0x51, 0x85, 0x03, 0xE0, selector, 0x00, operand]
        frame.append(xor_checksum(frame))
        frame += [0] * (32 - len(frame))
        self.transport.i2c_write(frame, 0x6E, 0)
        self.sleeper(0.3)
        return frame

    def execute_apcs(self, confirmed: bool = False) -> List[int]:
        return self.execute(0x80, 0x02, confirmed)

    def set_crosshair(self, index: int, confirmed: bool = False) -> List[int]:
        if self.dry_run:
            frame = [0x51, 0x85, 0x03, 0xE0, 0x55, 0x00, index & 0xFF]
            frame.append(xor_checksum(frame))
            frame += [0] * (32 - len(frame))
            return frame
        if not self.allow_execute or not confirmed:
            raise PermissionError("crosshair control is unverified; enable write access")
        frame = [0x51, 0x85, 0x03, 0xE0, 0x55, 0x00, index & 0xFF]
        frame.append(xor_checksum(frame))
        frame += [0] * (32 - len(frame))
        self.transport.i2c_write(frame, 0x6E, 0)
        self.sleeper(0.3)
        return frame