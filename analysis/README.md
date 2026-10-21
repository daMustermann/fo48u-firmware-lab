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

## Next steps

1. Split the 2 MB image into banks. Determine bank size & count from the
   BootCode/UserCode/UserBoot table and from SFR bank-select writes.
2. Re-analyze each bank in Ghidra (load at 0x8000 with bank0 common at 0x0000)
   and run the decompiler to get C pseudocode.
3. Locate the APCS timer logic (4-hour multiple = modulo) and the completion
   flag that fails to clear (causing the post-APCS popup).
4. Locate ADCS menu gating (why it's hidden) and AOCS trigger condition.
5. Locate ASBL/ABL parameters.
6. Build a patched firmware image and test on a spare unit (or via the updater
   in a VM) — **high risk; keep original F08 binary for recovery.**

## Safety

- Always keep the original `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` for recovery.
- Flashing modified firmware may brick the monitor. Test on a sacrificial unit.
- Do not distribute modified firmware without clear "unofficial / at your own risk" labeling.
