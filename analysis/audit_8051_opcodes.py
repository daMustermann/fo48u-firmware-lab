#!/usr/bin/env python3
"""Cross-check all 256 8051 instruction lengths against radare2's decoder.

No firmware data is modified. One temporary synthetic instruction is assembled
per opcode, padded to four bytes to make its start address unambiguous.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import tempfile

from oplen import OPLEN


def audit(r2: str) -> list[tuple[int, int, int, str]]:
    with tempfile.TemporaryDirectory(prefix="fo48u-opcodes-") as temporary:
        directory = pathlib.Path(temporary)
        blob = directory / "synthetic.bin"
        script = directory / "instructions.r2"
        blob.write_bytes(b"".join(bytes((op, 0, 0, 0)) for op in range(256)))
        script.write_text("\n".join(f"aoj 1 @ 0x{op*4:x}" for op in range(256)), encoding="ascii")
        result = subprocess.run(
            [r2, "-q", "-a", "8051", "-b", "8", "-i", str(script), str(blob)],
            capture_output=True, text=True, check=True, timeout=60,
        )
    operations = [json.loads(line)[0] for line in result.stdout.splitlines() if line.startswith("[{")]
    if len(operations) != 256:
        raise RuntimeError(f"radare2 returned {len(operations)}/256 instructions: {result.stderr[:350]}")
    wrong = []
    for op, operation in enumerate(operations):
        if operation["addr"] != op * 4:
            raise RuntimeError(f"unexpected alignment for opcode {op:02x}: {operation}")
        actual = operation["size"]
        expected = OPLEN[op]
        if actual != expected:
            wrong.append((op, expected, actual, operation.get("opcode", "")))
    return wrong


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r2", default="r2", help="path to the radare2 executable")
    args = parser.parse_args()
    disagreements = audit(args.r2)
    for op, expected, actual, instruction in disagreements:
        print(f"0x{op:02X}: OPLEN={expected} r2={actual}  {instruction}")
    print(f"{len(disagreements)} / 256 opcode lengths disagree")
    raise SystemExit(bool(disagreements))
