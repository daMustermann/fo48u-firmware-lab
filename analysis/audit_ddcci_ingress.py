#!/usr/bin/env python3
"""Inventory direct 8051 DPTR references near the FO48U DDC/CI mailbox.

Read-only static byte-pattern search on the MD5-verified stock F08 image.
These references are not a disassembly, exhaustive xrefs or proof of an
incoming wire layout; indirect MOVX writes need separate control-flow work.
"""

from collections import Counter
from hashlib import md5

from build_custom import load_source


def audit() -> list[tuple[int, int, int, str]]:
    image = bytes(load_source())
    assert md5(image).hexdigest() == "d4324c6c88abea48b1ee896f7e14ee9f"
    refs = []
    for bank in range(20):
        code = image[bank * 0x10000 : (bank + 1) * 0x10000]
        for addr in range(len(code) - 10):
            if code[addr : addr + 2] == b"\x90\xcf" and 0xD0 <= code[addr + 2] <= 0xDF:
                refs.append((bank, addr, code[addr + 2], code[addr + 3 : addr + 11].hex(" ")))
    summary = Counter(field for _, _, field, _ in refs)
    assert summary[0xDA] == 8 and summary[0xDE] == 78, summary
    return refs


if __name__ == "__main__":
    rows = audit()
    counts = Counter(field for _, _, field, _ in rows)
    print("Literal DPTR patterns CFd0..CFdf:")
    for field, n in sorted(counts.items()):
        print(f"  CF{field:02X}: {n}")
    print("CFDA..CFDD direct references (following bytes only, not decoded semantics):")
    for bank, addr, field, follow in rows:
        if field in (0xDA, 0xDB, 0xDC, 0xDD):
            print(f"  {bank:02}:{addr:04X} CF{field:02X}: {follow}")
    print("PASS: original F08 verified; no monitor traffic or firmware modification")
