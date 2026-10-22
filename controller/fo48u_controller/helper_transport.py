"""32-bit helper based transport for 64-bit Python."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List


def _find_helper() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "helper" / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
        Path("controller") / "helper" / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
        Path("helper") / "bin" / "Release" / "net8.0" / "win-x86" / "publish" / "helper.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("32-bit helper executable not found; build controller/helper first")


class HelperTransport:
    def __init__(self, helper_path: str | None = None):
        self.helper_path = helper_path or _find_helper()
        self.proc = subprocess.Popen(
            [self.helper_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready = self._recv()
        if not ready.get("ready"):
            raise RuntimeError("helper did not become ready")

    def _send(self, payload: dict) -> dict:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        return self._recv()

    def _recv(self) -> dict:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("helper process closed")
        return json.loads(line)

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

    def i2c_write(self, buffer, slave=0x6E, speed=0) -> int:
        response = self._send({"cmd": "i2c_write", "bytes": list(buffer), "slave": slave, "speed": speed})
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "write failed"))
        return int(response.get("result", 0))

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
        return list(response.get("bytes", []))