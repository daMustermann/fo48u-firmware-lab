# FO48U firmware reverse engineering summary

This document consolidates the byte-verified findings for the stock **FO48U F08 / 2022-11-15** image
(`2,031,616` bytes, SHA-256 `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`).

## Firmware layout

- 20 banks of `0x10000` bytes each; `file_offset = bank * 0x10000 + address`.
- Bank 0 contains the reset/interrupt vectors and trampolines; banks 1-19 hold application code and data.
- Keil C51 code; opcode lengths audited in `analysis/oplen.py`.

## Key XDATA regions

| Region | Role |
| :-- | :-- |
| `0xCFD8-0xCFDF` | Receive buffer (CFDB dispatch byte, CFDA packet family, CFDC operand, CFDE refresh flag) |
| `0xD12D` | Request byte; 19 direct reads, no direct writer (hardware-mapped or bit-addressable) |
| `0xD180` | Request byte; 36+ direct reads, no direct writer |
| `0xD31B` | State byte; single direct writer at `bank4:A12B` |
| `0xD8FE` | D8FE state byte; 50+ direct reads, one direct writer at `bank4:E6F4` (also written at `4:E712`) |
| `0xD618` | 18+ direct reads, no direct writer |
| `0xFFxx` | Hardware-mapped flags (FFEB, FFEA, FFED, FFEE, FFFF, FFE9, FFE8, FFE7, FFE5, FFE4, FFB0, FFAD, FFAC) |
| `0x0043` | Single direct writer at `bank10:C50E` |
| `0x006C` | Updated at `bank10:CD98` |

## Interrupt vectors (bank 0)

| Vector | Address | Target |
| :-- | :-- | :-- |
| IE0 (External Int 0) | `0x0003` | `LJMP 510F` - primary Scaler/DDC-CI IRQ |
| TF0 (Timer 0) | `0x000B` | `LJMP 5246` |
| IE1 (External Int 1) | `0x0013` | `LJMP 520B` - secondary I2C/AUX/USB bridge IRQ |
| RI/TI (UART0) | `0x0023` | serial ingress |
| TF2 (Timer 2/UART1) | `0x002B` | `LJMP 508A` |

ISR producers and main-loop consumers are decoupled via ring buffers and ready flags (`bRxReady`).

## OLED care host commands

Realtek-HID execution frames (padded to 32 bytes):

- APCS: `51 85 03 E0 80 00 02 B5`
- AOCS: `51 85 03 E0 82 00 02 B7`
- Crosshair preset: `51 85 03 E0 55 00 <index> <xor>`

Readback query frames (`51 83 01 E0 <selector> <xor>`, padded to 36 bytes):

| Selector | Meaning |
| :-- | :-- |
| `0x7F` | Panel hours |
| `0x80` | APCS enable/status |
| `0x81` | APCS elapsed time |
| `0x82` | AOCS enable/status |
| `0x83` | AOCS elapsed time |

## Verified status

- **APCS trigger** executed successfully on user hardware.
- **AOCS** sends the same frame but may not produce a visible action until the panel degradation threshold (~1500 h) is reached.
- All other commands remain unverified.

## Host controller

`controller/` provides a safety-gated Python/customtkinter replacement for OSD Sidekick.
See `controller/README.md` for setup and usage.