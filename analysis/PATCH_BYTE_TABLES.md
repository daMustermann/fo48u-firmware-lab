# Patch byte and instruction verification

Audited base commit: `0d94de00e2251b816809f6f8e9e9b4cb05fe4d0e`. Stock SHA-256: `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`.

All 20 extracted code banks match the stock image. Remaining 11 banks are covered by the image hash. Mutations below occur only in RAM.
PASS applies to local encoding/layout only. Global stack, interrupts, bank switching,
firmware integrity checks, hardware behavior and recoverability are not certified.

`full-control` adds an offline E0/FE allowlisted XDATA/D8FE hook to the carry-safe unlock.
Injected-code interpreter passes 133376 cases; external runtime reachability and cave ownership remain unproved.

## unlock_cmd_gate: 12:68AD

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:68AD | 64 | E4 | `68AD: xrl a, #0x02` +0 | `68AD: clr a` +0 |
| 12:68AE | 02 | 00 | `68AD: xrl a, #0x02` +1 | `68AE: nop` +0 |

## unlock_cmd_gate: 12:68BD

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:68BD | B4 | C3 | `68BD: cjne a, #0x02, 0x68d4` +0 | `68BD: clr c` +0 |
| 12:68BE | 02 | 74 | `68BD: cjne a, #0x02, 0x68d4` +1 | `68BE: mov a, #0x02` +0 |
| 12:68BF | 14 | 02 | `68BD: cjne a, #0x02, 0x68d4` +2 | `68BE: mov a, #0x02` +1 |

## apcs_2h: 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0x02` +0 |
| 13:CAA9 | 04 | 02 | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0x02` +1 |

## apcs_36h: 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0x24` +0 |
| 13:CAA9 | 04 | 24 | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0x24` +1 |

## aocs_750h: 13:CAD3

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAD3 | 7C | 7C | `CAD3: mov r4, #0x05` +0 | `CAD3: mov r4, #0x02` +0 |
| 13:CAD4 | 05 | 02 | `CAD3: mov r4, #0x05` +1 | `CAD3: mov r4, #0x02` +1 |
| 13:CAD5 | 7D | 7D | `CAD5: mov r5, #0xdc` +0 | `CAD5: mov r5, #0xee` +0 |
| 13:CAD6 | DC | EE | `CAD5: mov r5, #0xdc` +1 | `CAD5: mov r5, #0xee` +1 |

## tss_12h: 13:CB1A

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CB1A | 94 | 94 | `CB1A: subb a, #0x24` +0 | `CB1A: subb a, #0x0c` +0 |
| 13:CB1B | 24 | 0C | `CB1A: subb a, #0x24` +1 | `CB1A: subb a, #0x0c` +1 |

## control_hook: 12:5520 (Keil default pointer data)

| Bank:address | Stock | After | Kind |
|---|---|---|---|
| 12:5520 | 5D | FF | table data |
| 12:5521 | 3D | 60 | table data |

## control_hook: 12:5EB3 (Keil default pointer data)

| Bank:address | Stock | After | Kind |
|---|---|---|---|
| 12:5EB3 | 68 | FF | table data |
| 12:5EB4 | CF | 00 | table data |

## control_hook: 12:FF00

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:FF00 | FF | 90 | `FF00: mov r7, a` +0 | `FF00: mov dptr, #0xcfdc` +0 |
| 12:FF01 | FF | CF | `FF01: mov r7, a` +0 | `FF00: mov dptr, #0xcfdc` +1 |
| 12:FF02 | FF | DC | `FF02: mov r7, a` +0 | `FF00: mov dptr, #0xcfdc` +2 |
| 12:FF03 | FF | E0 | `FF03: mov r7, a` +0 | `FF03: movx a, @dptr` +0 |
| 12:FF04 | FF | B4 | `FF04: mov r7, a` +0 | `FF04: cjne a, #0xfe, 0xff43` +0 |
| 12:FF05 | FF | FE | `FF05: mov r7, a` +0 | `FF04: cjne a, #0xfe, 0xff43` +1 |
| 12:FF06 | FF | 3C | `FF06: mov r7, a` +0 | `FF04: cjne a, #0xfe, 0xff43` +2 |
| 12:FF07 | FF | 90 | `FF07: mov r7, a` +0 | `FF07: mov dptr, #0xcfd8` +0 |
| 12:FF08 | FF | CF | `FF08: mov r7, a` +0 | `FF07: mov dptr, #0xcfd8` +1 |
| 12:FF09 | FF | D8 | `FF09: mov r7, a` +0 | `FF07: mov dptr, #0xcfd8` +2 |
| 12:FF0A | FF | E0 | `FF0A: mov r7, a` +0 | `FF0A: movx a, @dptr` +0 |
| 12:FF0B | FF | B4 | `FF0B: mov r7, a` +0 | `FF0B: cjne a, #0x51, 0xff41` +0 |
| 12:FF0C | FF | 51 | `FF0C: mov r7, a` +0 | `FF0B: cjne a, #0x51, 0xff41` +1 |
| 12:FF0D | FF | 33 | `FF0D: mov r7, a` +0 | `FF0B: cjne a, #0x51, 0xff41` +2 |
| 12:FF0E | FF | A3 | `FF0E: mov r7, a` +0 | `FF0E: inc dptr` +0 |
| 12:FF0F | FF | E0 | `FF0F: mov r7, a` +0 | `FF0F: movx a, @dptr` +0 |
| 12:FF10 | FF | B4 | `FF10: mov r7, a` +0 | `FF10: cjne a, #0x86, 0xff41` +0 |
| 12:FF11 | FF | 86 | `FF11: mov r7, a` +0 | `FF10: cjne a, #0x86, 0xff41` +1 |
| 12:FF12 | FF | 2E | `FF12: mov r7, a` +0 | `FF10: cjne a, #0x86, 0xff41` +2 |
| 12:FF13 | FF | 90 | `FF13: mov r7, a` +0 | `FF13: mov dptr, #0xcfd8` +0 |
| 12:FF14 | FF | CF | `FF14: mov r7, a` +0 | `FF13: mov dptr, #0xcfd8` +1 |
| 12:FF15 | FF | D8 | `FF15: mov r7, a` +0 | `FF13: mov dptr, #0xcfd8` +2 |
| 12:FF16 | FF | 7F | `FF16: mov r7, a` +0 | `FF16: mov r7, #0x09` +0 |
| 12:FF17 | FF | 09 | `FF17: mov r7, a` +0 | `FF16: mov r7, #0x09` +1 |
| 12:FF18 | FF | 7E | `FF18: mov r7, a` +0 | `FF18: mov r6, #0x00` +0 |
| 12:FF19 | FF | 00 | `FF19: mov r7, a` +0 | `FF18: mov r6, #0x00` +1 |
| 12:FF1A | FF | E0 | `FF1A: mov r7, a` +0 | `FF1A: movx a, @dptr` +0 |
| 12:FF1B | FF | 6E | `FF1B: mov r7, a` +0 | `FF1B: xrl a, r6` +0 |
| 12:FF1C | FF | FE | `FF1C: mov r7, a` +0 | `FF1C: mov r6, a` +0 |
| 12:FF1D | FF | A3 | `FF1D: mov r7, a` +0 | `FF1D: inc dptr` +0 |
| 12:FF1E | FF | DF | `FF1E: mov r7, a` +0 | `FF1E: djnz r7, 0xff1a` +0 |
| 12:FF1F | FF | FA | `FF1F: mov r7, a` +0 | `FF1E: djnz r7, 0xff1a` +1 |
| 12:FF20 | FF | EE | `FF20: mov r7, a` +0 | `FF20: mov a, r6` +0 |
| 12:FF21 | FF | 70 | `FF21: mov r7, a` +0 | `FF21: jnz 0xff41` +0 |
| 12:FF22 | FF | 1E | `FF22: mov r7, a` +0 | `FF21: jnz 0xff41` +1 |
| 12:FF23 | FF | 90 | `FF23: mov r7, a` +0 | `FF23: mov dptr, #0xcfdd` +0 |
| 12:FF24 | FF | CF | `FF24: mov r7, a` +0 | `FF23: mov dptr, #0xcfdd` +1 |
| 12:FF25 | FF | DD | `FF25: mov r7, a` +0 | `FF23: mov dptr, #0xcfdd` +2 |
| 12:FF26 | FF | E0 | `FF26: mov r7, a` +0 | `FF26: movx a, @dptr` +0 |
| 12:FF27 | FF | B4 | `FF27: mov r7, a` +0 | `FF27: cjne a, #0xd8, 0xff41` +0 |
| 12:FF28 | FF | D8 | `FF28: mov r7, a` +0 | `FF27: cjne a, #0xd8, 0xff41` +1 |
| 12:FF29 | FF | 17 | `FF29: mov r7, a` +0 | `FF27: cjne a, #0xd8, 0xff41` +2 |
| 12:FF2A | FF | A3 | `FF2A: mov r7, a` +0 | `FF2A: inc dptr` +0 |
| 12:FF2B | FF | E0 | `FF2B: mov r7, a` +0 | `FF2B: movx a, @dptr` +0 |
| 12:FF2C | FF | B4 | `FF2C: mov r7, a` +0 | `FF2C: cjne a, #0xfe, 0xff41` +0 |
| 12:FF2D | FF | FE | `FF2D: mov r7, a` +0 | `FF2C: cjne a, #0xfe, 0xff41` +1 |
| 12:FF2E | FF | 12 | `FF2E: mov r7, a` +0 | `FF2C: cjne a, #0xfe, 0xff41` +2 |
| 12:FF2F | FF | A3 | `FF2F: mov r7, a` +0 | `FF2F: inc dptr` +0 |
| 12:FF30 | FF | E0 | `FF30: mov r7, a` +0 | `FF30: movx a, @dptr` +0 |
| 12:FF31 | FF | 60 | `FF31: mov r7, a` +0 | `FF31: jz 0xff3b` +0 |
| 12:FF32 | FF | 08 | `FF32: mov r7, a` +0 | `FF31: jz 0xff3b` +1 |
| 12:FF33 | FF | B4 | `FF33: mov r7, a` +0 | `FF33: cjne a, #0x10, 0xff38` +0 |
| 12:FF34 | FF | 10 | `FF34: mov r7, a` +0 | `FF33: cjne a, #0x10, 0xff38` +1 |
| 12:FF35 | FF | 02 | `FF35: mov r7, a` +0 | `FF33: cjne a, #0x10, 0xff38` +2 |
| 12:FF36 | FF | 80 | `FF36: mov r7, a` +0 | `FF36: sjmp 0xff3b` +0 |
| 12:FF37 | FF | 03 | `FF37: mov r7, a` +0 | `FF36: sjmp 0xff3b` +1 |
| 12:FF38 | FF | B4 | `FF38: mov r7, a` +0 | `FF38: cjne a, #0x20, 0xff41` +0 |
| 12:FF39 | FF | 20 | `FF39: mov r7, a` +0 | `FF38: cjne a, #0x20, 0xff41` +1 |
| 12:FF3A | FF | 06 | `FF3A: mov r7, a` +0 | `FF38: cjne a, #0x20, 0xff41` +2 |
| 12:FF3B | FF | 90 | `FF3B: mov r7, a` +0 | `FF3B: mov dptr, #0xd8fe` +0 |
| 12:FF3C | FF | D8 | `FF3C: mov r7, a` +0 | `FF3B: mov dptr, #0xd8fe` +1 |
| 12:FF3D | FF | FE | `FF3D: mov r7, a` +0 | `FF3B: mov dptr, #0xd8fe` +2 |
| 12:FF3E | FF | F0 | `FF3E: mov r7, a` +0 | `FF3E: movx @dptr, a` +0 |
| 12:FF3F | FF | D3 | `FF3F: mov r7, a` +0 | `FF3F: setb c` +0 |
| 12:FF40 | FF | 22 | `FF40: mov r7, a` +0 | `FF40: ret` +0 |
| 12:FF41 | FF | C3 | `FF41: mov r7, a` +0 | `FF41: clr c` +0 |
| 12:FF42 | FF | 22 | `FF42: mov r7, a` +0 | `FF42: ret` +0 |
| 12:FF43 | FF | 02 | `FF43: mov r7, a` +0 | `FF43: ljmp 0x68cf` +0 |
| 12:FF44 | FF | 68 | `FF44: mov r7, a` +0 | `FF43: ljmp 0x68cf` +1 |
| 12:FF45 | FF | CF | `FF45: mov r7, a` +0 | `FF43: ljmp 0x68cf` +2 |

## control_hook: 12:FF60

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:FF60 | FF | 90 | `FF60: mov r7, a` +0 | `FF60: mov dptr, #0xcfdc` +0 |
| 12:FF61 | FF | CF | `FF61: mov r7, a` +0 | `FF60: mov dptr, #0xcfdc` +1 |
| 12:FF62 | FF | DC | `FF62: mov r7, a` +0 | `FF60: mov dptr, #0xcfdc` +2 |
| 12:FF63 | FF | E0 | `FF63: mov r7, a` +0 | `FF63: movx a, @dptr` +0 |
| 12:FF64 | FF | B4 | `FF64: mov r7, a` +0 | `FF64: cjne a, #0xfe, 0xffcc` +0 |
| 12:FF65 | FF | FE | `FF65: mov r7, a` +0 | `FF64: cjne a, #0xfe, 0xffcc` +1 |
| 12:FF66 | FF | 65 | `FF66: mov r7, a` +0 | `FF64: cjne a, #0xfe, 0xffcc` +2 |
| 12:FF67 | FF | 90 | `FF67: mov r7, a` +0 | `FF67: mov dptr, #0xcfd8` +0 |
| 12:FF68 | FF | CF | `FF68: mov r7, a` +0 | `FF67: mov dptr, #0xcfd8` +1 |
| 12:FF69 | FF | D8 | `FF69: mov r7, a` +0 | `FF67: mov dptr, #0xcfd8` +2 |
| 12:FF6A | FF | E0 | `FF6A: mov r7, a` +0 | `FF6A: movx a, @dptr` +0 |
| 12:FF6B | FF | B4 | `FF6B: mov r7, a` +0 | `FF6B: cjne a, #0x51, 0xffc2` +0 |
| 12:FF6C | FF | 51 | `FF6C: mov r7, a` +0 | `FF6B: cjne a, #0x51, 0xffc2` +1 |
| 12:FF6D | FF | 54 | `FF6D: mov r7, a` +0 | `FF6B: cjne a, #0x51, 0xffc2` +2 |
| 12:FF6E | FF | A3 | `FF6E: mov r7, a` +0 | `FF6E: inc dptr` +0 |
| 12:FF6F | FF | E0 | `FF6F: mov r7, a` +0 | `FF6F: movx a, @dptr` +0 |
| 12:FF70 | FF | B4 | `FF70: mov r7, a` +0 | `FF70: cjne a, #0x85, 0xffc2` +0 |
| 12:FF71 | FF | 85 | `FF71: mov r7, a` +0 | `FF70: cjne a, #0x85, 0xffc2` +1 |
| 12:FF72 | FF | 4F | `FF72: mov r7, a` +0 | `FF70: cjne a, #0x85, 0xffc2` +2 |
| 12:FF73 | FF | 90 | `FF73: mov r7, a` +0 | `FF73: mov dptr, #0xcfd8` +0 |
| 12:FF74 | FF | CF | `FF74: mov r7, a` +0 | `FF73: mov dptr, #0xcfd8` +1 |
| 12:FF75 | FF | D8 | `FF75: mov r7, a` +0 | `FF73: mov dptr, #0xcfd8` +2 |
| 12:FF76 | FF | 7F | `FF76: mov r7, a` +0 | `FF76: mov r7, #0x08` +0 |
| 12:FF77 | FF | 08 | `FF77: mov r7, a` +0 | `FF76: mov r7, #0x08` +1 |
| 12:FF78 | FF | 7E | `FF78: mov r7, a` +0 | `FF78: mov r6, #0x00` +0 |
| 12:FF79 | FF | 00 | `FF79: mov r7, a` +0 | `FF78: mov r6, #0x00` +1 |
| 12:FF7A | FF | E0 | `FF7A: mov r7, a` +0 | `FF7A: movx a, @dptr` +0 |
| 12:FF7B | FF | 6E | `FF7B: mov r7, a` +0 | `FF7B: xrl a, r6` +0 |
| 12:FF7C | FF | FE | `FF7C: mov r7, a` +0 | `FF7C: mov r6, a` +0 |
| 12:FF7D | FF | A3 | `FF7D: mov r7, a` +0 | `FF7D: inc dptr` +0 |
| 12:FF7E | FF | DF | `FF7E: mov r7, a` +0 | `FF7E: djnz r7, 0xff7a` +0 |
| 12:FF7F | FF | FA | `FF7F: mov r7, a` +0 | `FF7E: djnz r7, 0xff7a` +1 |
| 12:FF80 | FF | EE | `FF80: mov r7, a` +0 | `FF80: mov a, r6` +0 |
| 12:FF81 | FF | 70 | `FF81: mov r7, a` +0 | `FF81: jnz 0xffc2` +0 |
| 12:FF82 | FF | 3F | `FF82: mov r7, a` +0 | `FF81: jnz 0xffc2` +1 |
| 12:FF83 | FF | 90 | `FF83: mov r7, a` +0 | `FF83: mov dptr, #0xcfdd` +0 |
| 12:FF84 | FF | CF | `FF84: mov r7, a` +0 | `FF83: mov dptr, #0xcfdd` +1 |
| 12:FF85 | FF | DD | `FF85: mov r7, a` +0 | `FF83: mov dptr, #0xcfdd` +2 |
| 12:FF86 | FF | E0 | `FF86: mov r7, a` +0 | `FF86: movx a, @dptr` +0 |
| 12:FF87 | FF | FE | `FF87: mov r7, a` +0 | `FF87: mov r6, a` +0 |
| 12:FF88 | FF | A3 | `FF88: mov r7, a` +0 | `FF88: inc dptr` +0 |
| 12:FF89 | FF | E0 | `FF89: mov r7, a` +0 | `FF89: movx a, @dptr` +0 |
| 12:FF8A | FF | FD | `FF8A: mov r7, a` +0 | `FF8A: mov r5, a` +0 |
| 12:FF8B | FF | EE | `FF8B: mov r7, a` +0 | `FF8B: mov a, r6` +0 |
| 12:FF8C | FF | B4 | `FF8C: mov r7, a` +0 | `FF8C: cjne a, #0xd8, 0xff95` +0 |
| 12:FF8D | FF | D8 | `FF8D: mov r7, a` +0 | `FF8C: cjne a, #0xd8, 0xff95` +1 |
| 12:FF8E | FF | 06 | `FF8E: mov r7, a` +0 | `FF8C: cjne a, #0xd8, 0xff95` +2 |
| 12:FF8F | FF | ED | `FF8F: mov r7, a` +0 | `FF8F: mov a, r5` +0 |
| 12:FF90 | FF | B4 | `FF90: mov r7, a` +0 | `FF90: cjne a, #0xfe, 0xffc2` +0 |
| 12:FF91 | FF | FE | `FF91: mov r7, a` +0 | `FF90: cjne a, #0xfe, 0xffc2` +1 |
| 12:FF92 | FF | 2F | `FF92: mov r7, a` +0 | `FF90: cjne a, #0xfe, 0xffc2` +2 |
| 12:FF93 | FF | 80 | `FF93: mov r7, a` +0 | `FF93: sjmp 0xffa6` +0 |
| 12:FF94 | FF | 11 | `FF94: mov r7, a` +0 | `FF93: sjmp 0xffa6` +1 |
| 12:FF95 | FF | B4 | `FF95: mov r7, a` +0 | `FF95: cjne a, #0xd1, 0xffc2` +0 |
| 12:FF96 | FF | D1 | `FF96: mov r7, a` +0 | `FF95: cjne a, #0xd1, 0xffc2` +1 |
| 12:FF97 | FF | 2A | `FF97: mov r7, a` +0 | `FF95: cjne a, #0xd1, 0xffc2` +2 |
| 12:FF98 | FF | ED | `FF98: mov r7, a` +0 | `FF98: mov a, r5` +0 |
| 12:FF99 | FF | B4 | `FF99: mov r7, a` +0 | `FF99: cjne a, #0x2d, 0xff9e` +0 |
| 12:FF9A | FF | 2D | `FF9A: mov r7, a` +0 | `FF99: cjne a, #0x2d, 0xff9e` +1 |
| 12:FF9B | FF | 02 | `FF9B: mov r7, a` +0 | `FF99: cjne a, #0x2d, 0xff9e` +2 |
| 12:FF9C | FF | 80 | `FF9C: mov r7, a` +0 | `FF9C: sjmp 0xffa6` +0 |
| 12:FF9D | FF | 08 | `FF9D: mov r7, a` +0 | `FF9C: sjmp 0xffa6` +1 |
| 12:FF9E | FF | B4 | `FF9E: mov r7, a` +0 | `FF9E: cjne a, #0x3d, 0xffa3` +0 |
| 12:FF9F | FF | 3D | `FF9F: mov r7, a` +0 | `FF9E: cjne a, #0x3d, 0xffa3` +1 |
| 12:FFA0 | FF | 02 | `FFA0: mov r7, a` +0 | `FF9E: cjne a, #0x3d, 0xffa3` +2 |
| 12:FFA1 | FF | 80 | `FFA1: mov r7, a` +0 | `FFA1: sjmp 0xffa6` +0 |
| 12:FFA2 | FF | 03 | `FFA2: mov r7, a` +0 | `FFA1: sjmp 0xffa6` +1 |
| 12:FFA3 | FF | B4 | `FFA3: mov r7, a` +0 | `FFA3: cjne a, #0x3e, 0xffc2` +0 |
| 12:FFA4 | FF | 3E | `FFA4: mov r7, a` +0 | `FFA3: cjne a, #0x3e, 0xffc2` +1 |
| 12:FFA5 | FF | 1C | `FFA5: mov r7, a` +0 | `FFA3: cjne a, #0x3e, 0xffc2` +2 |
| 12:FFA6 | FF | 8D | `FFA6: mov r7, a` +0 | `FFA6: mov 0x82, r5` +0 |
| 12:FFA7 | FF | 82 | `FFA7: mov r7, a` +0 | `FFA6: mov 0x82, r5` +1 |
| 12:FFA8 | FF | 8E | `FFA8: mov r7, a` +0 | `FFA8: mov 0x83, r6` +0 |
| 12:FFA9 | FF | 83 | `FFA9: mov r7, a` +0 | `FFA8: mov 0x83, r6` +1 |
| 12:FFAA | FF | E0 | `FFAA: mov r7, a` +0 | `FFAA: movx a, @dptr` +0 |
| 12:FFAB | FF | FC | `FFAB: mov r7, a` +0 | `FFAB: mov r4, a` +0 |
| 12:FFAC | FF | 90 | `FFAC: mov r7, a` +0 | `FFAC: mov dptr, #0xcf86` +0 |
| 12:FFAD | FF | CF | `FFAD: mov r7, a` +0 | `FFAC: mov dptr, #0xcf86` +1 |
| 12:FFAE | FF | 86 | `FFAE: mov r7, a` +0 | `FFAC: mov dptr, #0xcf86` +2 |
| 12:FFAF | FF | 74 | `FFAF: mov r7, a` +0 | `FFAF: mov a, #0xfe` +0 |
| 12:FFB0 | FF | FE | `FFB0: mov r7, a` +0 | `FFAF: mov a, #0xfe` +1 |
| 12:FFB1 | FF | F0 | `FFB1: mov r7, a` +0 | `FFB1: movx @dptr, a` +0 |
| 12:FFB2 | FF | A3 | `FFB2: mov r7, a` +0 | `FFB2: inc dptr` +0 |
| 12:FFB3 | FF | E4 | `FFB3: mov r7, a` +0 | `FFB3: clr a` +0 |
| 12:FFB4 | FF | F0 | `FFB4: mov r7, a` +0 | `FFB4: movx @dptr, a` +0 |
| 12:FFB5 | FF | A3 | `FFB5: mov r7, a` +0 | `FFB5: inc dptr` +0 |
| 12:FFB6 | FF | 74 | `FFB6: mov r7, a` +0 | `FFB6: mov a, #0xff` +0 |
| 12:FFB7 | FF | FF | `FFB7: mov r7, a` +0 | `FFB6: mov a, #0xff` +1 |
| 12:FFB8 | FF | F0 | `FFB8: mov r7, a` +0 | `FFB8: movx @dptr, a` +0 |
| 12:FFB9 | FF | A3 | `FFB9: mov r7, a` +0 | `FFB9: inc dptr` +0 |
| 12:FFBA | FF | E4 | `FFBA: mov r7, a` +0 | `FFBA: clr a` +0 |
| 12:FFBB | FF | F0 | `FFBB: mov r7, a` +0 | `FFBB: movx @dptr, a` +0 |
| 12:FFBC | FF | A3 | `FFBC: mov r7, a` +0 | `FFBC: inc dptr` +0 |
| 12:FFBD | FF | EC | `FFBD: mov r7, a` +0 | `FFBD: mov a, r4` +0 |
| 12:FFBE | FF | F0 | `FFBE: mov r7, a` +0 | `FFBE: movx @dptr, a` +0 |
| 12:FFBF | FF | 02 | `FFBF: mov r7, a` +0 | `FFBF: ljmp 0x5d5a` +0 |
| 12:FFC0 | FF | 5D | `FFC0: mov r7, a` +0 | `FFBF: ljmp 0x5d5a` +1 |
| 12:FFC1 | FF | 5A | `FFC1: mov r7, a` +0 | `FFBF: ljmp 0x5d5a` +2 |
| 12:FFC2 | FF | 90 | `FFC2: mov r7, a` +0 | `FFC2: mov dptr, #0xcf84` +0 |
| 12:FFC3 | FF | CF | `FFC3: mov r7, a` +0 | `FFC2: mov dptr, #0xcf84` +1 |
| 12:FFC4 | FF | 84 | `FFC4: mov r7, a` +0 | `FFC2: mov dptr, #0xcf84` +2 |
| 12:FFC5 | FF | 74 | `FFC5: mov r7, a` +0 | `FFC5: mov a, #0x01` +0 |
| 12:FFC6 | FF | 01 | `FFC6: mov r7, a` +0 | `FFC5: mov a, #0x01` +1 |
| 12:FFC7 | FF | F0 | `FFC7: mov r7, a` +0 | `FFC7: movx @dptr, a` +0 |
| 12:FFC8 | FF | E4 | `FFC8: mov r7, a` +0 | `FFC8: clr a` +0 |
| 12:FFC9 | FF | FC | `FFC9: mov r7, a` +0 | `FFC9: mov r4, a` +0 |
| 12:FFCA | FF | 80 | `FFCA: mov r7, a` +0 | `FFCA: sjmp 0xffac` +0 |
| 12:FFCB | FF | E0 | `FFCB: mov r7, a` +0 | `FFCA: sjmp 0xffac` +1 |
| 12:FFCC | FF | 02 | `FFCC: mov r7, a` +0 | `FFCC: ljmp 0x5d3d` +0 |
| 12:FFCD | FF | 5D | `FFCD: mov r7, a` +0 | `FFCC: ljmp 0x5d3d` +1 |
| 12:FFCE | FF | 3D | `FFCE: mov r7, a` +0 | `FFCC: ljmp 0x5d3d` +2 |

## patch_apcs(0): 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0xff` +0 |
| 13:CAA9 | 04 | FF | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0xff` +1 |

## patch_apcs(1): 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0x01` +0 |
| 13:CAA9 | 04 | 01 | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0x01` +1 |

## patch_apcs(4): 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0x04` +0 |
| 13:CAA9 | 04 | 04 | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0x04` +1 |

## patch_apcs(8): 13:CAA8

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAA8 | 94 | 94 | `CAA8: subb a, #0x04` +0 | `CAA8: subb a, #0x08` +0 |
| 13:CAA9 | 04 | 08 | `CAA8: subb a, #0x04` +1 | `CAA8: subb a, #0x08` +1 |

## patch_aocs(0): 13:CAD3

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAD3 | 7C | 7C | `CAD3: mov r4, #0x05` +0 | `CAD3: mov r4, #0xff` +0 |
| 13:CAD4 | 05 | FF | `CAD3: mov r4, #0x05` +1 | `CAD3: mov r4, #0xff` +1 |
| 13:CAD5 | 7D | 7D | `CAD5: mov r5, #0xdc` +0 | `CAD5: mov r5, #0xff` +0 |
| 13:CAD6 | DC | FF | `CAD5: mov r5, #0xdc` +1 | `CAD5: mov r5, #0xff` +1 |

## patch_aocs(1): 13:CAD3

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAD3 | 7C | 7C | `CAD3: mov r4, #0x05` +0 | `CAD3: mov r4, #0x00` +0 |
| 13:CAD4 | 05 | 00 | `CAD3: mov r4, #0x05` +1 | `CAD3: mov r4, #0x00` +1 |
| 13:CAD5 | 7D | 7D | `CAD5: mov r5, #0xdc` +0 | `CAD5: mov r5, #0x01` +0 |
| 13:CAD6 | DC | 01 | `CAD5: mov r5, #0xdc` +1 | `CAD5: mov r5, #0x01` +1 |

## patch_aocs(1500): 13:CAD3

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CAD3 | 7C | 7C | `CAD3: mov r4, #0x05` +0 | `CAD3: mov r4, #0x05` +0 |
| 13:CAD4 | 05 | 05 | `CAD3: mov r4, #0x05` +1 | `CAD3: mov r4, #0x05` +1 |
| 13:CAD5 | 7D | 7D | `CAD5: mov r5, #0xdc` +0 | `CAD5: mov r5, #0xdc` +0 |
| 13:CAD6 | DC | DC | `CAD5: mov r5, #0xdc` +1 | `CAD5: mov r5, #0xdc` +1 |

## patch_tss(0): 13:CB1A

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CB1A | 94 | 94 | `CB1A: subb a, #0x24` +0 | `CB1A: subb a, #0xff` +0 |
| 13:CB1B | 24 | FF | `CB1A: subb a, #0x24` +1 | `CB1A: subb a, #0xff` +1 |

## patch_tss(1): 13:CB1A

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CB1A | 94 | 94 | `CB1A: subb a, #0x24` +0 | `CB1A: subb a, #0x01` +0 |
| 13:CB1B | 24 | 01 | `CB1A: subb a, #0x24` +1 | `CB1A: subb a, #0x01` +1 |

## patch_tss(36): 13:CB1A

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 13:CB1A | 94 | 94 | `CB1A: subb a, #0x24` +0 | `CB1A: subb a, #0x24` +0 |
| 13:CB1B | 24 | 24 | `CB1A: subb a, #0x24` +1 | `CB1A: subb a, #0x24` +1 |

## menu-actions (unreachable prototype): 9:E0E2

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 9:E0E2 | 12 | 12 | `E0E2: lcall 0x97db` +0 | `E0E2: lcall 0xfefa` +0 |
| 9:E0E3 | 97 | FE | `E0E2: lcall 0x97db` +1 | `E0E2: lcall 0xfefa` +1 |
| 9:E0E4 | DB | FA | `E0E2: lcall 0x97db` +2 | `E0E2: lcall 0xfefa` +2 |

## menu-actions (unreachable prototype): 9:FEFA

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 9:FEFA | FF | ED | `FEFA: mov r7, a` +0 | `FEFA: mov a, r5` +0 |
| 9:FEFB | FF | 60 | `FEFB: mov r7, a` +0 | `FEFB: jz 0xff1b` +0 |
| 9:FEFC | FF | 1E | `FEFC: mov r7, a` +0 | `FEFB: jz 0xff1b` +1 |
| 9:FEFD | FF | EB | `FEFD: mov r7, a` +0 | `FEFD: mov a, r3` +0 |
| 9:FEFE | FF | 70 | `FEFE: mov r7, a` +0 | `FEFE: jnz 0xff1b` +0 |
| 9:FEFF | FF | 1B | `FEFF: mov r7, a` +0 | `FEFE: jnz 0xff1b` +1 |
| 9:FF00 | FF | EF | `FF00: mov r7, a` +0 | `FF00: mov a, r7` +0 |
| 9:FF01 | FF | B4 | `FF01: mov r7, a` +0 | `FF01: cjne a, #0x17, 0xff0e` +0 |
| 9:FF02 | FF | 17 | `FF02: mov r7, a` +0 | `FF01: cjne a, #0x17, 0xff0e` +1 |
| 9:FF03 | FF | 0A | `FF03: mov r7, a` +0 | `FF01: cjne a, #0x17, 0xff0e` +2 |
| 9:FF04 | FF | 90 | `FF04: mov r7, a` +0 | `FF04: mov dptr, #0xd12d` +0 |
| 9:FF05 | FF | D1 | `FF05: mov r7, a` +0 | `FF04: mov dptr, #0xd12d` +1 |
| 9:FF06 | FF | 2D | `FF06: mov r7, a` +0 | `FF04: mov dptr, #0xd12d` +2 |
| 9:FF07 | FF | E0 | `FF07: mov r7, a` +0 | `FF07: movx a, @dptr` +0 |
| 9:FF08 | FF | 44 | `FF08: mov r7, a` +0 | `FF08: orl a, #0x01` +0 |
| 9:FF09 | FF | 01 | `FF09: mov r7, a` +0 | `FF08: orl a, #0x01` +1 |
| 9:FF0A | FF | F0 | `FF0A: mov r7, a` +0 | `FF0A: movx @dptr, a` +0 |
| 9:FF0B | FF | 02 | `FF0B: mov r7, a` +0 | `FF0B: ljmp 0x97db` +0 |
| 9:FF0C | FF | 97 | `FF0C: mov r7, a` +0 | `FF0B: ljmp 0x97db` +1 |
| 9:FF0D | FF | DB | `FF0D: mov r7, a` +0 | `FF0B: ljmp 0x97db` +2 |
| 9:FF0E | FF | B4 | `FF0E: mov r7, a` +0 | `FF0E: cjne a, #0x18, 0xff1b` +0 |
| 9:FF0F | FF | 18 | `FF0F: mov r7, a` +0 | `FF0E: cjne a, #0x18, 0xff1b` +1 |
| 9:FF10 | FF | 0A | `FF10: mov r7, a` +0 | `FF0E: cjne a, #0x18, 0xff1b` +2 |
| 9:FF11 | FF | 90 | `FF11: mov r7, a` +0 | `FF11: mov dptr, #0xd12d` +0 |
| 9:FF12 | FF | D1 | `FF12: mov r7, a` +0 | `FF11: mov dptr, #0xd12d` +1 |
| 9:FF13 | FF | 2D | `FF13: mov r7, a` +0 | `FF11: mov dptr, #0xd12d` +2 |
| 9:FF14 | FF | E0 | `FF14: mov r7, a` +0 | `FF14: movx a, @dptr` +0 |
| 9:FF15 | FF | 44 | `FF15: mov r7, a` +0 | `FF15: orl a, #0x02` +0 |
| 9:FF16 | FF | 02 | `FF16: mov r7, a` +0 | `FF15: orl a, #0x02` +1 |
| 9:FF17 | FF | F0 | `FF17: mov r7, a` +0 | `FF17: movx @dptr, a` +0 |
| 9:FF18 | FF | 02 | `FF18: mov r7, a` +0 | `FF18: ljmp 0x97db` +0 |
| 9:FF19 | FF | 97 | `FF19: mov r7, a` +0 | `FF18: ljmp 0x97db` +1 |
| 9:FF1A | FF | DB | `FF1A: mov r7, a` +0 | `FF18: ljmp 0x97db` +2 |
| 9:FF1B | FF | 02 | `FF1B: mov r7, a` +0 | `FF1B: ljmp 0x97db` +0 |
| 9:FF1C | FF | 97 | `FF1C: mov r7, a` +0 | `FF1B: ljmp 0x97db` +1 |
| 9:FF1D | FF | DB | `FF1D: mov r7, a` +0 | `FF1B: ljmp 0x97db` +2 |

## Full-control surrounding disassembly

| Bank:address | Stock bytes / instruction | After bytes / instruction |
|---|---|---|
| 12:68A9 | `90cfde` mov dptr, #0xcfde | `90cfde` mov dptr, #0xcfde |
| 12:68AC | `e0` movx a, @dptr | `e0` movx a, @dptr |
| 12:68AD | `6402` xrl a, #0x02 | `e4` clr a |
| 12:68AE | operand of preceding instruction | `00` nop |
| 12:68AF | `7023` jnz 0x68d4 | `7023` jnz 0x68d4 |
| 12:68B1 | `90d12d` mov dptr, #0xd12d | `90d12d` mov dptr, #0xd12d |
| 12:68B4 | `e0` movx a, @dptr | `e0` movx a, @dptr |
| 12:68B5 | `4401` orl a, #0x01 | `4401` orl a, #0x01 |
| 12:68B7 | `800d` sjmp 0x68c6 | `800d` sjmp 0x68c6 |
| 12:68B9 | `90cfde` mov dptr, #0xcfde | `90cfde` mov dptr, #0xcfde |
| 12:68BC | `e0` movx a, @dptr | `e0` movx a, @dptr |
| 12:68BD | `b40214` cjne a, #0x02, 0x68d4 | `c3` clr c |
| 12:68BE | operand of preceding instruction | `7402` mov a, #0x02 |
| 12:68C0 | `90d12d` mov dptr, #0xd12d | `90d12d` mov dptr, #0xd12d |
| 12:68C3 | `e0` movx a, @dptr | `e0` movx a, @dptr |
| 12:68C4 | `4402` orl a, #0x02 | `4402` orl a, #0x02 |
| 12:68C6 | `f0` movx @dptr, a | `f0` movx @dptr, a |
| 12:68C7 | `122c50` lcall 0x2c50 | `122c50` lcall 0x2c50 |
| 12:68CA | `122b9c` lcall 0x2b9c | `122b9c` lcall 0x2b9c |
| 12:68CD | `8005` sjmp 0x68d4 | `8005` sjmp 0x68d4 |
| 12:68CF | `8000` sjmp 0x68d1 | `8000` sjmp 0x68d1 |
| 12:68D1 | `122dc4` lcall 0x2dc4 | `122dc4` lcall 0x2dc4 |
| 12:68D4 | `d3` setb c | `d3` setb c |
| 12:68D5 | `22` ret | `22` ret |

## Relative branches in the audited windows

Computed from signed rel8 and OPLEN, including JB/JNB/JBC and both DJNZ forms.
Both outcomes are checked structurally even when a patched predicate is constant.

| Bank:source | Target | Image |
|---|---|---|
| 9:E0C4 | 9:E0CE | patched |
| 9:E0C4 | 9:E0CE | stock |
| 9:E0CC | 9:E0D4 | patched |
| 9:E0CC | 9:E0D4 | stock |
| 9:E0E9 | 9:E0F3 | patched |
| 9:E0E9 | 9:E0F3 | stock |
| 9:FEFB | 9:FF1B | patched |
| 9:FEFE | 9:FF1B | patched |
| 9:FF01 | 9:FF0E | patched |
| 9:FF0E | 9:FF1B | patched |
| 12:68AF | 12:68D4 | patched |
| 12:68AF | 12:68D4 | stock |
| 12:68B7 | 12:68C6 | patched |
| 12:68B7 | 12:68C6 | stock |
| 12:68BD | 12:68D4 | stock |
| 12:68CD | 12:68D4 | patched |
| 12:68CD | 12:68D4 | stock |
| 12:68CF | 12:68D1 | patched |
| 12:68CF | 12:68D1 | stock |
| 12:FF04 | 12:FF43 | patched |
| 12:FF0B | 12:FF41 | patched |
| 12:FF10 | 12:FF41 | patched |
| 12:FF1E | 12:FF1A | patched |
| 12:FF21 | 12:FF41 | patched |
| 12:FF27 | 12:FF41 | patched |
| 12:FF2C | 12:FF41 | patched |
| 12:FF31 | 12:FF3B | patched |
| 12:FF33 | 12:FF38 | patched |
| 12:FF36 | 12:FF3B | patched |
| 12:FF38 | 12:FF41 | patched |
| 12:FF64 | 12:FFCC | patched |
| 12:FF6B | 12:FFC2 | patched |
| 12:FF70 | 12:FFC2 | patched |
| 12:FF7E | 12:FF7A | patched |
| 12:FF81 | 12:FFC2 | patched |
| 12:FF8C | 12:FF95 | patched |
| 12:FF90 | 12:FFC2 | patched |
| 12:FF93 | 12:FFA6 | patched |
| 12:FF95 | 12:FFC2 | patched |
| 12:FF99 | 12:FF9E | patched |
| 12:FF9C | 12:FFA6 | patched |
| 12:FF9E | 12:FFA3 | patched |
| 12:FFA1 | 12:FFA6 | patched |
| 12:FFA3 | 12:FFC2 | patched |
| 12:FFCA | 12:FFAC | patched |
| 13:CA64 | 13:CA7B | patched |
| 13:CA64 | 13:CA7B | stock |
| 13:CA6D | 13:CA7B | patched |
| 13:CA6D | 13:CA7B | stock |
| 13:CA82 | 13:CAEF | patched |
| 13:CA82 | 13:CAEF | stock |
| 13:CA8A | 13:CA92 | patched |
| 13:CA8A | 13:CA92 | stock |
| 13:CA9E | 13:CABD | patched |
| 13:CA9E | 13:CABD | stock |
| 13:CAAD | 13:CABD | patched |
| 13:CAAD | 13:CABD | stock |
| 13:CAB4 | 13:CABD | patched |
| 13:CAB4 | 13:CABD | stock |
| 13:CAD1 | 13:CAEF | patched |
| 13:CAD1 | 13:CAEF | stock |
| 13:CADC | 13:CAEF | patched |
| 13:CADC | 13:CAEF | stock |
| 13:CAE5 | 13:CAEF | patched |
| 13:CAE5 | 13:CAEF | stock |
| 13:CAF6 | 13:CB03 | patched |
| 13:CAF6 | 13:CB03 | stock |
| 13:CB1F | 13:CB38 | patched |
| 13:CB1F | 13:CB38 | stock |
| 13:CB2D | 13:CB38 | patched |
| 13:CB2D | 13:CB38 | stock |

## Stack and scope

Unlock and threshold replacements contain no PUSH, POP, call, RET or SP write.
The menu call remains LCALL (SP +2), returning to 9:E0E5; every wrapper path
tail-jumps to 9:97DB with no additional stack use. Stock dispatcher return consumes
that same address (SP -2), conditional on the unchanged dispatcher/callees returning.
The APCS/AOCS handlers retain calls 0:2C50 and 0:2B9C and RET at 12:68D5.
AOCS CLR C; MOV A,#2 matches the accepted stock A=2/CY=0 state; 131072 cases pass.
MOVX at 12:68C3 reloads A before the request update; CY remains zero at 12:68C7.
Cross-bank synthetic returns and ISR stack depth are outside this local proof.
An unchanged call graph does not prove absence of overflow or balanced runtime SP.

New SET hook paths consume the existing return address once (RET); GET paths tail-jump
to stock checksum/send code at 12:5D5A. No injected PUSH/POP/LCALL or SP write occurs.
Unknown commands tail-jump to their original defaults. FE requests require exact length,
51 header and XOR=00. SET writes only D8FE values 00/10/20; GET reads only D12D/D13D/D13E/D8FE.
All selected ranges end at instruction boundaries; no trailing instruction fragments.
Unchanged bytes are included in the tables. Erased FF bytes decode as MOV R7,A;
that does not prove the erased region is unreachable or available for a trampoline.
Parameter samples cover all named presets and endpoints; arbitrary valid values only
replace immediate operands (94 xx / 7C hi 7D lo), preserving the same boundaries.
patch.py validates stock identity, length, bounds, overlaps, bank selection and outputs.
Arbitrary JSON still requires its own instruction/semantic audit.

## Host per-bank verification CRC

RFlash.dll SHA-256 09586d4b2cfd5d80b20ad3bf2ee2b01fd080260f0753e83c8ec32eaf3b0ec652
implements CRC-8 (poly 07, init 00, refin/refout false, xorout 00) over each 65536-byte bank.
The native comparison at 10002CFD compares this with the scaler CRC result (register 75).
No stored trailer is repaired. All stock banks end in FFFF at FFFE; boot checks remain open.

| Bank | Stock CRC-8 | Full-control prototype CRC-8 |
|---|---|---|
| 0 | 4F | 4F |
| 1 | E9 | E9 |
| 2 | 4A | 4A |
| 3 | 63 | 63 |
| 4 | 8E | 8E |
| 5 | C0 | C0 |
| 6 | 2E | 2E |
| 7 | 72 | 72 |
| 8 | 68 | 68 |
| 9 | 67 | 67 |
| 10 | AA | AA |
| 11 | 3A | 3A |
| 12 | 4F | 29 |
| 13 | 3D | 3D |
| 14 | E6 | E6 |
| 15 | 7E | 7E |
| 16 | 74 | 74 |
| 17 | 2B | 2B |
| 18 | 5D | 5D |
| 19 | 11 | 11 |
| 20 | DE | DE |
| 21 | DE | DE |
| 22 | DE | DE |
| 23 | DE | DE |
| 24 | DE | DE |
| 25 | DE | DE |
| 26 | DE | DE |
| 27 | 98 | 98 |
| 28 | 98 | 98 |
| 29 | 34 | 34 |
| 30 | 34 | 34 |

Verified 25 transformations and 22 distinct site/replacement combinations.
DO NOT FLASH. Local verification is not a finding of zero brick risk.
