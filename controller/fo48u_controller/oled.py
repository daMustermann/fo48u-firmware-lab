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


def decode_status_reply(response, selector):
    """Validate the Realtek E0 status reply before exposing its uint16 value.

    F06 capture: 6E 88 02 00 E0 selector max-hi max-lo val-hi val-lo xor.
    DDC replies use virtual destination 50 as XOR seed. Only the length-framed
    bytes participate; remaining HID buffer bytes can contain repeated data.
    No transaction ID exists, so echo validation cannot prove freshness.
    """
    if selector not in (0x02, 0x07, 0x38, *OLED_SELECTORS):
        raise ValueError("unsupported status selector")
    if not isinstance(response, (list, bytes, bytearray)) or len(response) != 36:
        raise OSError("invalid OLED/status reply buffer length")
    if any(type(b) is not int or not 0 <= b <= 255 for b in response):
        raise OSError("invalid status reply bytes")
    if bytes(response[:3]) != bytes.fromhex("6E 88 02"):
        raise OSError("invalid status reply address, payload length or opcode")
    length = (response[1] & 0x7F) + 3
    frame = list(response[:length])
    if frame[3] != 0:
        raise OSError(f"device rejected status query: result={frame[3]}")
    if frame[4:6] != [0xE0, selector]:
        raise OSError("status reply family/selector echo mismatch")
    if xor_checksum(frame) != 0x50:
        raise OSError("status reply checksum mismatch")
    return {"value": frame[8] * 256 + frame[9], "maximum_raw": frame[6] * 256 + frame[7],
            "frame_hex": bytes(frame).hex(' '), "checksum_valid": True,
            "selector_echo_valid": True, "freshness": "not provable without a transaction ID"}


def decode_standard_reply(response, code):
    """Validate a standard MCCS response, including the returned VCP code."""
    if len(response) != 36 or any(type(b) is not int or not 0 <= b <= 255 for b in response):
        raise OSError('invalid standard VCP buffer')
    frame = list(response[:11])
    if frame[:3] != [0x6E, 0x88, 2] or frame[3] != 0:
        raise OSError('invalid or rejected standard VCP reply')
    if frame[4] != code:
        raise OSError(f'VCP echo mismatch: requested {code:02X}, received {frame[4]:02X}')
    if frame[5] not in (0, 1):
        raise OSError(f'invalid standard VCP type {frame[5]:02X}; possible vendor-family reply')
    if xor_checksum(frame) != 0x50:
        raise OSError('standard VCP checksum mismatch')
    return {'value': frame[8]*256+frame[9], 'maximum_raw': frame[6]*256+frame[7],
            'vcp_type_raw': frame[5], 'frame_hex': bytes(frame).hex(' '),
            'checksum_valid': True, 'vcp_echo_valid': True}


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
        return decode_status_reply(response, selector)["value"]

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

    def execute_aocs(self, confirmed: bool = False) -> List[int]:
        return self.execute(0x82, 0x02, confirmed)

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
