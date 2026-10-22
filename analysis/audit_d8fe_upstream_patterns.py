#!/usr/bin/env python3
"""Audit additional D8FE/buffer-handoff upstream patterns."""
from hashlib import sha256
from pathlib import Path

IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115" / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000

def scan_bank(data, bank):
    seg = data[bank*BANK_SIZE:(bank+1)*BANK_SIZE]
    results = []
    for i in range(len(seg)-2):
        if seg[i] == 0x7A and seg[i+1] == 0xD8:
            results.append(("R2_imm_D8", bank, i, seg[i:i+4].hex()))
        if seg[i] == 0x7E and seg[i+1] == 0xD8:
            results.append(("R6_imm_D8", bank, i, seg[i:i+4].hex()))
    for i in range(len(seg)-6):
        if seg[i] == 0x75 and seg[i+1] == 0xA0 and seg[i+2] == 0xD8:
            for j in range(i+3, min(i+12, len(seg)-3)):
                if (seg[j] == 0x78 or seg[j] == 0x79) and (seg[j+2] == 0xF2 or seg[j+2] == 0xF3):
                    results.append(("P2_D8_movx", bank, i, seg[i:j+3].hex()))
                    break
    for i in range(len(seg)-6):
        if seg[i] == 0x78 and seg[i+1] == 0xFE and seg[i+2] == 0x75 and seg[i+3] == 0xA0 and seg[i+4] == 0xD8:
            if i+5 < len(seg) and seg[i+5] == 0xF2:
                results.append(("R0_FE_P2_D8_F2", bank, i, seg[i:i+7].hex()))
        if seg[i] == 0x79 and seg[i+1] == 0xFE and seg[i+2] == 0x75 and seg[i+3] == 0xA0 and seg[i+4] == 0xD8:
            if i+5 < len(seg) and seg[i+5] == 0xF3:
                results.append(("R1_FE_P2_D8_F3", bank, i, seg[i:i+7].hex()))
    return results

def audit():
    data = IMAGE.read_bytes()
    assert len(data) == 2_031_616
    assert sha256(data).hexdigest() == SHA256
    print(f"Stock F08: {len(data)} bytes; SHA256 {SHA256}")
    all_results = []
    for bank in range(20):
        all_results.extend(scan_bank(data, bank))
    print(f"\nFound {len(all_results)} patterns:")
    for name, bank, addr, seq in all_results:
        print(f"  {name}: {bank}:{addr:04X} [{seq}]")
    print("\nNote: R2/R6 for high byte with R1/R7 for low byte; paged MOVX via P2")

if __name__ == "__main__":
    audit()
