# FO48U Firmware Analysis — Working Notes

Status: **in progress**. Goal: reverse-engineer the Gigabyte AORUS FO48U firmware
(Realtek RTD2718, banked 8051) to fix bugs and unlock features (APCS flag bug,
ADCS in OSD, AOCS reliability, ASBL tuning, FreeSync/HDR fixes).

## Target

- File: `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`
- Size: 2,031,616 bytes (0x1F0000)
- MD5: `d4324c6c88abea48b1ee896f7e14ee9f`
- Identified as: `FW: F08  20221115`, panel `LG LE48AOD EPA4`, scaler `RTD2718`.

## Flash layout (observed)

| Region | Range | Notes |
|---|---|---|
| Code (banked) | 0x000000 – 0x13FFFF | 8051 code, ~1.25 MB |
| Erased (0xFF) | 0x140000 – 0x1AFFFF | 384 KB unused flash |
| Gamma/LUT table | 0x1B0000 – 0x1CFFFF | 16-bit gamma curve + brightness table |
| OSD font / LUT | 0x1D0000 – 0x1EFFFF | duplicated 64 KB block (backup) |
| (end) | 0x1F0000 | |

Bank switching on Realtek RTD27xx uses SFRs (typically 0x60/0x61 bank select),
with a common bank (0x0000–0x7FFF) and switchable banks (0x8000–0xFFFF).
The 8051 address space is 64 KB, so the 2 MB image is banked.

## Tools installed

- `radare2` 6.2.4 (8051 arch supported via `rasm2`/`r2 -a 8051`)
- `Ghidra` 12.1.4 (8051:BE:16 processor) — headless project at `F:\Coding\ghidra_proj\FO48U`
  (note: Ghidra clips to 64 KB address space; banked analysis requires splitting)
- Python 3.13 with `capstone`, `unicorn`, `keystone-engine`, `lief`, `pyelftools`
- `binwalk` not available; `strings` (via Python) used.

## Artifacts produced

- `analysis/oplen.py` — 8051 opcode length table.
- `analysis/extract_calls.py` — linear-sweep call-target extractor.
- `analysis/calltargets.txt` — extracted lcall/acall/ljmp/ajmp targets (noisy due to
  banked code; top high-frequency targets are the real utility functions).

## Confirmed findings

- Scaler string: `RTD2718` (at 0xb9b0a and 0xc5378).
- Panel string: `LG LE48AOD EPA4` (0xb9af2).
- Firmware ID: `FW : F08  20221115` (0xb9ada).
- VCP/MCCS descriptor at 0xab381 (monitor responds to DDC/CI VCP codes).
- BootCode / UserCode / UserBoot segment labels at 0xb9ab8.
- Reset vector at 0x0000 → `ljmp 0x4e0c`; interrupt vectors at 0x0003, 0x000b, etc.
- USB control endpoint (from community): Realtek vendor HID `0BDA:1100`.

## BREAKTHROUGH: Bank switching mechanism (RTD2660/RTD2718)

From the RTD2660 spec (page 355-357 "Bank Switch"):

- **PBANK_SEL at XDATA 0xFFFF**: write bank number here to switch program code bank.
- **BANK_EN (bit 0 of XDATA 0xFFFC)** enables bank switching for program address space.
- **SW_MODE (bit 1 of 0xFFFC)**: 0 = P3.5 as A16, 1 = Pbank_switch (0xFFFF).
- **XDATA_BSTART (0xFFFD)**: start bank for XDATA. **XDATA_BSEL (0xFFFE)**: first XDATA bank.
- Up to 256×64KB supported in XFR mode; 64KB default.

**In firmware**, bank switch routine at **0x507e** (present in every bank's common prefix):

```
0x507e: xch  a, r0
0x507f: mov  dptr, #0xffff      ; PBANK_SEL
0x5082: mov  0x52, a            ; save current bank in IRAM 0x52
0x5084: lcall 0x0dd0            ; a += IRAM[0x30]  (bank offset adjust)
0x5087: movx @dptr, a           ; write bank number -> switch bank
0x5088: mov  a, r0
0x5089: ret
```

Callers: `mov a, #bank; lcall 0x507e` (bank number in A).

## Flash layout (confirmed)

- 31 × 64KB banks (0x00000–0x1EFFFF) + 0x1F0000 total (31 × 65536 = 2,031,616). ✓
- Banks 0–19: code banks. Share a common prefix 0x0000–0x536b (~21 KB) containing
  vectors, boot init, and core routines (including bank-switch at 0x507e). Diverge at 0x536c
  (bank-ID/version tag) and the remaining ~44 KB is bank-specific code.
- Banks 20–30: different content (likely XDATA/data/OSD tables or additional banks).
- Bank 0 is the default (reset vector 0x0000 → 0x4e0c).

## How to analyze a specific bank

1. Extract bank N: `dd if=firmware/...bin of=bankN.bin bs=65536 skip=N count=1`
2. Load in Ghidra as 8051:BE:16 raw binary at offset 0.
3. Mark functions at `lcall` targets (common prefix targets are shared; bank-specific
   targets are in the upper region).
4. Run decompiler.

## Next concrete steps

1. Enumerate all distinct bank numbers passed to the bank-switch routine (0x507e)
   to learn which banks are actually used and what each contains.
2. Search all 20 code banks for the APCS 4-hour threshold constant and the
   menu-gating condition; search for the service-mode GPIO check in bank 0's
   common prefix.
3. Patch and rebuild; test on spare unit.

## Safety

- Always keep the original `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` for recovery.
- Flashing modified firmware may brick the monitor. Test on a sacrificial unit.
- Do not distribute modified firmware without clear "unofficial / at your own risk" labeling.
