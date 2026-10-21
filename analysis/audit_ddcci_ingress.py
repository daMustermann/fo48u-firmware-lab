#!/usr/bin/env python3
"""Inventory direct 8051 DPTR references near the FO48U DDC/CI mailbox.

Read-only static byte-pattern search on the MD5-verified stock F08 image.
These references are not a disassembly, exhaustive xrefs or proof of an
incoming wire layout. This also checks a conditional indirect buffer writer;
the link to bank-12 service-command dispatch remains unidentified.
"""

from collections import Counter
from hashlib import md5

from build_custom import load_source


def check_indirect_receive_path(image: bytes) -> None:
    """Pin the original bytes for an XDATA buffer selection/write chain."""
    sites = {
        (13, 0xE3B1): "90 ff 23 e0 54 fe 64 6e 70 32",
        (13, 0xE3BB): "12 26 56 ef 7b 01 70 08 7a cf 79 d8 7d 80 80 06 7a ce 79 e1 7d 50 12 dd 24",
        (13, 0xDD24): "90 c9 c2 eb f0 a3 ea f0 a3 e9 f0 a3 ed f0",
        (13, 0xDD3C): "78 58 f6 90 ff 24 e0 ff 12 ef 37 12 ef 43",
        (13, 0xDD7A): "90 ff 25 e0 90 c9 c2 12 ef 0d",
        (13, 0xDDA4): "12 ef 37 90 00 03 12 36 81 b4 fc 0e 90 00 02 12 36 81 b4 03 05",
        (13, 0xDEB3): "90 fe 89 e0 90 c9 c2 12 ef 0d",
        (13, 0xEF0D): "ff e0 fb a3 e0 fa a3 e0 f9 78 58 e6 06 f5 82 75 83 00 ef 12 36 c0",
        (13, 0xEF23): "90 00 01 12 36 81 54 7f 24 03 ff e4 33 fe 78 58 e6 7c 00 22",
        (13, 0xC8BF): "90 cf da e0 90 c9 c4 f0 90 cf db e0 90 c9 c5 f0",
        (0, 0x36C0): "f8 bb 01 0d e5 82 29 f5 82 e5 83 3a f5 83 e8 f0 22",
    }
    for (bank, address), expected in sites.items():
        wanted = bytes.fromhex(expected)
        position = bank * 0x10000 + address
        actual = image[position:position + len(wanted)]
        assert actual == wanted, (f"{bank}:{address:04X}", actual.hex(" "))


def audit() -> list[tuple[int, int, int, str]]:
    image = bytes(load_source())
    assert md5(image).hexdigest() == "d4324c6c88abea48b1ee896f7e14ee9f"
    check_indirect_receive_path(image)
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
    print("PASS: conditional CFD8/CEE1 receive-buffer writer and original F08 bytes verified")
    print("No proof of external packet framing or a link to bank-12 commands")
