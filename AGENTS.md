# AI agent guide (public)

Canonical manual for the FO48U firmware research repo. Read `README.md`, `STATUS.md`, and `analysis/README.md` first.

## 1. Repo map
- Firmware image: `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` (2,031,616 bytes, SHA-256 `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`).
- Banks: `analysis/banks/bank_0.bin` .. `bank_19.bin` (0x10000 each); `file_offset = bank*0x10000 + address`.
- Proven facts: `analysis/knowledge_base.json` (machine-readable) and `STATUS.md` / `analysis/README.md` (human-readable).
- Verification: `analysis/verify_facts.py` (all stock-byte assertions) and `analysis/verify_menu_patch.py`.
- Core tools: `analysis/oplen.py`, `analysis/find_bankswitch.py`, `analysis/osd_strings.py`, `analysis/scan_sfr.py`, `analysis/xref_xdata.py`, `analysis/patch.py`, `analysis/build_custom.py`, `analysis/build_variant.py`, `analysis/build_trampoline_map.py`, `analysis/extract_sidekick_protocol.py`.
- Ghidra dumps/export scripts: `analysis/dumps/`, `analysis/ghidra/`.
- Host protocol ground truth: `osd-sidekick/B21.0707.1/` (`UpdPack.cab`, `Install.exe`, `support.xml`).
- Trampoline map: `analysis/trampoline_map.json`.

## 2. Fast-path 8051 RE rules
- Never read full `analysis/dumps/decompiled_bank*.txt` into context; query `analysis/knowledge_base.json` first and use `analysis/xref_xdata.py` with narrow context (`-C`).
- Do not trust Ghidra decompiler output blindly on Keil C51 `?C?CCASE`/`?C?ICASE` inline switch tables or Bank 0 cross-bank trampolines; verify raw bytes in `analysis/banks/bank_*.bin`.
- 8051 upstream buffer writes often use `INC DPTR` (0xA3), Keil register pointers (R3:R2:R1, R2=0xD8), paged `MOVX @R0/@R1,A` (0xF2/0xF3), or ISR producers. Trace forward from `bank_0.bin` vectors 0x0003, 0x000B, 0x0013, 0x0023, 0x002B.
- Cross-check host-side protocol ground truth in `osd-sidekick/B21.0707.1/`.
- Never create new one-off `audit_*.py` scripts; add proven facts to `analysis/knowledge_base.json` and `STATUS.md`.
- Bank switch at 0x6000, target bank in R7, selector written to XDATA 0xFFFF.
- Use bank:address notation (e.g. 13:CAA8); file_offset = bank*0x10000 + address.

## 3. Current open blockers (Issue #2)
- Solved: byte-level receive paths (FF24/FF25 and FE88/FE89), length gate, FC/03 comparison (value-preserving, cannot reject), buffer handoff (CFD8/CEE1), D8FE paths, bank-12 trampoline (18:D6CE), command table (cmd 80/82).
- Open: physical transport origin of FF24/FF25/FE88/FE89; runtime origin of D180/C68A/D8FE; whether any external command reaches bank-12 handlers; joystick/event origin for menu actions 23/24; inbound checksum (none found); bank-19 0x80A4 (C501==0x20) link to USB.
- APCS (4h), AOCS (1500h), TSS (36h) are static code thresholds, not measured intervals. No firmware is validated for flashing.

## Safety
- Never flash firmware or disable OLED protection. Never add modified/generated binaries. Do not commit secrets or `AGENT.md`.
PY