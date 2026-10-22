#!/usr/bin/env python3
"""Trace dual_ingress/rx_acceptance from 8051 interrupt vectors in bank_0.bin."""
from hashlib import sha256
from pathlib import Path

IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115" / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000

VECTORS = {
    0x0003: ("IE0", "External Int 0 - primary Scaler/DDC-CI IRQ"),
    0x000B: ("TF0", "Timer 0"),
    0x0013: ("IE1", "External Int 1 - secondary I2C/AUX/USB bridge IRQ"),
    0x0023: ("RI/TI", "UART0 serial ingress"),
    0x002B: ("TF2", "Timer 2/UART1"),
}

def audit():
    data = IMAGE.read_bytes()
    assert len(data) == 2_031_616
    assert sha256(data).hexdigest() == SHA256
    print(f"Stock F08: {len(data)} bytes; SHA256 {SHA256}\n")
    
    print("Interrupt vectors in bank_0.bin (file offsets bank0 + vector):")
    for vaddr, (name, desc) in VECTORS.items():
        # LJMP is 02 addr_high addr_low
        if vaddr + 2 < len(data):
            op = data[vaddr]
            if op == 0x02:  # LJMP
                tgt = (data[vaddr+1] << 8) | data[vaddr+2]
                print(f"  0:{vaddr:04X} {name:12s} LJMP {tgt:04X} - {desc}")
            elif op == 0x32:  # RETI
                print(f"  0:{vaddr:04X} {name:12s} RETI - {desc}")
            else:
                print(f"  0:{vaddr:04X} {name:12s} op={op:02X} - {desc}")
    
    print("\nNote: ISR producers/consumers decoupled via ring buffers/ready flags (bRxReady)")
    print("No LCALL link between ISR and main-loop dispatcher - trace forward from ISRs")

if __name__ == "__main__":
    audit()
