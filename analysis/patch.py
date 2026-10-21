#!/usr/bin/env python3
"""FO48U firmware patching scaffold.

Usage:
  # extract a single bank for editing
  python patch.py extract 0 bank0.bin
  # reassemble all 31 banks into a full image
  python patch.py reassemble patched.bin
  # apply a list of patches (JSON) to a bank
  python patch.py patch bank_0.bin patches.json

patches.json format:
  [
    {"bank": 0, "offset": 0x1234, "old": "aa bb", "new": "cc dd"},
    ...
  ]
"""
import sys, os, json, struct

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(BASE, "firmware", "F08-20221115", "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
BANKS_DIR = os.path.join(BASE, "analysis", "banks")
BANK_SIZE = 0x10000
NUM_BANKS = 31

def cmd_extract(bank, out):
    d = open(IMG,'rb').read()
    b = int(bank)
    open(out,'wb').write(d[b*BANK_SIZE:(b+1)*BANK_SIZE])
    print("extracted bank %d -> %s" % (b, out))

def cmd_reassemble(out):
    # read banks from analysis/banks/ (bank_0.bin .. bank_30.bin)
    outb = bytearray()
    for b in range(NUM_BANKS):
        p = os.path.join(BANKS_DIR, "bank_%d.bin" % b)
        if not os.path.exists(p):
            print("MISSING", p); sys.exit(1)
        data = open(p,'rb').read()
        if len(data) != BANK_SIZE:
            print("BAD SIZE", p, len(data)); sys.exit(1)
        outb += data
    open(out,'wb').write(outb)
    print("reassembled %d banks -> %s (%d bytes)" % (NUM_BANKS, out, len(outb)))

def cmd_patch(bankfile, patches_json):
    data = bytearray(open(bankfile,'rb').read())
    patches = json.load(open(patches_json))
    for p in patches:
        off = p["offset"]
        old = bytes.fromhex(p["old"].replace(' ',''))
        new = bytes.fromhex(p["new"].replace(' ',''))
        if data[off:off+len(old)] != old:
            print("MISMATCH at %s: got %s expected %s" % (hex(off), data[off:off+len(old)].hex(' '), old.hex(' ')))
            sys.exit(1)
        data[off:off+len(old)] = new
        print("patched %s: %s -> %s" % (hex(off), old.hex(' '), new.hex(' ')))
    open(bankfile,'wb').write(data)
    print("written", bankfile)

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "extract":
        cmd_extract(sys.argv[2], sys.argv[3])
    elif cmd == "reassemble":
        cmd_reassemble(sys.argv[2])
    elif cmd == "patch":
        cmd_patch(sys.argv[2], sys.argv[3])
    else:
        print("unknown cmd", cmd); sys.exit(1)

if __name__ == "__main__":
    main()

