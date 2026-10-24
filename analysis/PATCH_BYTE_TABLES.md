# Patch byte and instruction verification

Audited base commit: `5fa02eb5ffb605afd10c72c835cec869a1100d2f`. Stock SHA-256: `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`.

All 20 extracted code banks match the stock image. Remaining 11 banks are covered by the image hash. Mutations below occur only in RAM.
PASS applies to local encoding/layout only. Global stack, interrupts, bank switching,
firmware integrity checks, hardware behavior and recoverability are not certified.

`full-control` changes exactly five bytes and is identical to `unlock_cmd_gate`.
There is no additional XDATA/event-control firmware implementation in that profile.

## unlock_cmd_gate: 12:68AD

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:68AD | 64 | E4 | `68AD: xrl a, #0x02` +0 | `68AD: clr a` +0 |
| 12:68AE | 02 | 00 | `68AD: xrl a, #0x02` +1 | `68AE: nop` +0 |

## unlock_cmd_gate: 12:68BD

| Bank:address | Stock byte | After byte | Stock instruction / byte position | After instruction / byte position |
|---|---|---|---|---|
| 12:68BD | B4 | E4 | `68BD: cjne a, #0x02, 0x68d4` +0 | `68BD: clr a` +0 |
| 12:68BE | 02 | 00 | `68BD: cjne a, #0x02, 0x68d4` +1 | `68BE: nop` +0 |
| 12:68BF | 14 | 00 | `68BD: cjne a, #0x02, 0x68d4` +2 | `68BF: nop` +0 |

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
| 12:68BD | `b40214` cjne a, #0x02, 0x68d4 | `e4` clr a |
| 12:68BE | operand of preceding instruction | `00` nop |
| 12:68BF | operand of preceding instruction | `00` nop |
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
Removing CJNE also removes its carry update: an accepted stock AOCS operand
clears C, whereas CLR A; NOP; NOP preserves incoming C. Callee sensitivity
to that difference remains unproven; encoding safety is not semantic equivalence.
Cross-bank synthetic returns and ISR stack depth are outside this local proof.
An unchanged call graph does not prove absence of overflow or balanced runtime SP.

All selected ranges end at instruction boundaries; no trailing instruction fragments.
Unchanged bytes are included in the tables. Erased FF bytes decode as MOV R7,A;
that does not prove the erased region is unreachable or available for a trampoline.
Parameter samples cover all named presets and endpoints; arbitrary valid values only
replace immediate operands (94 xx / 7C hi 7D lo), preserving the same boundaries.
Caller-provided JSON for patch.py is unbounded and has no universal byte inventory.
It lacks equal-length, bank, range, image-identity and instruction-layout guards.

Verified 24 transformations and 18 distinct site/replacement combinations.
DO NOT FLASH. Local verification is not a finding of zero brick risk.
