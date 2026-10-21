#!/usr/bin/env python3
"""Decode the FO48U OSD string table.

The F08 image stores OSD strings in program bank 1:

  * index table : bank-relative 0xD707, 310 entries, 3 bytes each
                  (offset_hi, offset_lo, 0xFF), offsets big-endian.
  * string data : bank-relative 0x536C .. ~0xD4C2,
                  each string is a group of 0xFF-separated language slots.

Run from the repo root:
    python analysis/osd_strings.py [firmware.bin] > analysis/osd_strings.txt
"""

import sys
from pathlib import Path

DEFAULT_FW = Path("firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
BANK = 1
INDEX_START = 0xD707
STRING_BASE = 0x536C
STRING_END = 0xD4C2

# Glyph map recovered from the OSD font.
# 0x2B and 0x55 are kerning/blank glyphs, not letters.
CAPITALS = {0x1E + i: chr(ord("A") + i) for i in range(13)}         # A..M
CAPITALS[0x2B] = ""                                                 # kerning / thin space
CAPITALS[0x2C] = "N"
CAPITALS[0x2D] = "O"
CAPITALS.update({0x2E + i: chr(ord("P") + i) for i in range(11)})   # P..Z
SMALLCAPS = {0x3B + i: chr(ord("A") + i) for i in range(26)}        # A..Z
SMALLCAPS[0x55] = ""                                                # trailing special


def decode(part: bytes) -> str:
    out = []
    i = 0
    while i < len(part):
        c = part[i]
        if c in (0xFB, 0xFC):
            if i + 1 < len(part):
                out.append("{%02x:%02x}" % (c, part[i + 1]))
                i += 2
            else:
                out.append("{%02x}" % c)
                i += 1
            continue
        if c == 0x00:
            pass
        elif c == 0x01:
            out.append(" ")
        elif c in CAPITALS:
            out.append(CAPITALS[c])
        elif c in SMALLCAPS:
            out.append(SMALLCAPS[c])
        else:
            out.append("{%02x}" % c)
        i += 1
    return "".join(out)


def parse_index(bank: bytes):
    entries = []
    pos = INDEX_START
    while pos + 2 < len(bank):
        hi, lo, sep = bank[pos], bank[pos + 1], bank[pos + 2]
        if sep != 0xFF:
            break
        value = (hi << 8) | lo
        if entries and value <= entries[-1]:
            break
        if not (STRING_BASE <= value < 0xE000):
            break
        entries.append(value)
        pos += 3
    return entries


def main() -> None:
    fw = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FW
    data = fw.read_bytes()
    bank = data[BANK * 0x10000:(BANK + 1) * 0x10000]
    entries = parse_index(bank)

    print("# FO48U F08 OSD string table")
    print("# source      : %s" % fw)
    print("# index table : bank %d 0x%04X, %d entries x 3 bytes (BE16 + 0xFF)"
          % (BANK, INDEX_START, len(entries)))
    print("# string base : 0x%04X, end 0x%04X" % (STRING_BASE, STRING_END))
    print("# format      : ID  OFFSET  LANG0 | LANG1 | ...   ({xx} = raw glyph)")
    print()

    for sid, start in enumerate(entries):
        end = entries[sid + 1] if sid + 1 < len(entries) else STRING_END
        parts = bank[start:end].split(b"\xFF")
        texts = [decode(p) for p in parts]
        raw = " ".join(p.hex() for p in parts)
        print("%3d  0x%04X  %s" % (sid, start, " | ".join(texts)))
        print("           raw: %s" % raw)


if __name__ == "__main__":
    main()
