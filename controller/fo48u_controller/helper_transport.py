"""32-bit helper based transport for 64-bit Python."""

from __future__ import annotations

import json
import subprocess
import queue
import threading
from pathlib import Path
from typing import List


def _find_helper() -> str:
    candidates = [
        Path(__file__).resolve().parents[1] / "helper" / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
        Path("controller") / "helper" / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
        Path("helper") / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("32-bit helper executable not found; build controller/helper first")


class HelperTransport:
    def __init__(self, helper_path: str | None = None, read_only: bool = False, response_timeout: float = 5.0):
        self.helper_path = helper_path or _find_helper()
        self.read_only = read_only
        self.response_timeout = response_timeout
        self._responses = queue.Queue()
        self.proc = subprocess.Popen(
            [self.helper_path, *( ["--read-only"] if read_only else [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        def reader():
            try:
                for line in self.proc.stdout:
                    self._responses.put(line)
            finally:
                self._responses.put(None)
        self._reader = threading.Thread(target=reader, daemon=True)
        self._reader.start()
        try:
            ready = self._recv()
            if not ready.get("ready") or ready.get("protocol") != 2:
                raise RuntimeError("helper protocol 2 required; rebuild controller/helper to include failed-read safety fixes")
            if read_only and (ready.get("read_only") is not True or ready.get("status_query") is not True):
                raise RuntimeError("helper lacks enforced read-only status-query support; republish it")
        except Exception:
            self.proc.terminate()
            self.proc.wait(timeout=5)
            raise

    def _send(self, payload: dict) -> dict:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        return self._recv()

    def _recv(self) -> dict:
        assert self.proc.stdout is not None
        try:
            line = self._responses.get(timeout=self.response_timeout)
        except queue.Empty:
            self.proc.terminate()
            raise TimeoutError("HID helper response deadline exceeded")
        if not line:
            raise RuntimeError("helper process closed")
        return json.loads(line)

    def status_query(self, selector: int) -> List[int]:
        return self._read_query(selector, standard=False)

    def ddc_query(self, code: int) -> List[int]:
        return self._read_query(code, standard=True)

    def _read_query(self, selector: int, standard: bool) -> List[int]:
        if not self.read_only:
            raise PermissionError("status probe requires an enforced read-only helper")
        allowed = (0x10, 0x12, 0x6C, 0x6E, 0x70, 0xDF, 0xE0) if standard else (0x02, 0x07, 0x38, 0x7F, 0x80, 0x81, 0x82, 0x83)
        if selector not in allowed:
            raise ValueError("selector is not an allowlisted status query")
        response = self._send({"cmd": "ddc_query" if standard else "status_query", "selector": selector})
        if response.get("ok") is not True or type(response.get("result")) is not int or response["result"] != 0:
            raise OSError(response.get("error", "status query failed"))
        data = response.get("bytes")
        if not isinstance(data, list) or len(data) != 36 or any(type(b) is not int or not 0 <= b <= 255 for b in data):
            raise OSError("invalid status response buffer")
        return data

    def open(self) -> None:
        response = self._send({"cmd": "open"})
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "open failed"))

    def close(self) -> None:
        for payload in ({"cmd": "close"}, {"cmd": "quit"}):
            try:
                self._send(payload)
            except Exception:
                pass
        self.proc.terminate()
        self.proc.wait(timeout=5)

    def i2c_write(self, buffer, slave=0x6E, speed=0) -> int:
        response = self._send({"cmd": "i2c_write", "bytes": list(buffer), "slave": slave, "speed": speed})
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "write failed"))
        if type(response.get("result")) is not int or response["result"] != 0:
            raise OSError(f"helper I2C write failed: status={response.get('result')}")
        return 0

    def i2c_read(self, reg_addr=0x51, reg_len=1, buf_len=36, slave=0x6E, speed=0, timeout=100) -> List[int]:
        response = self._send({
            "cmd": "i2c_read",
            "reg": reg_addr,
            "reg_len": reg_len,
            "buf_len": buf_len,
            "slave": slave,
            "speed": speed,
            "timeout": timeout,
        })
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "read failed"))
        if type(response.get("result")) is not int or response["result"] != 0:
            raise OSError(f"helper I2C read failed: status={response.get('result')}")
        data = response.get("bytes")
        if not isinstance(data, list) or len(data) != buf_len or any(type(b) is not int or not 0 <= b <= 255 for b in data):
            raise OSError("helper returned invalid or incomplete I2C data")
        return data
