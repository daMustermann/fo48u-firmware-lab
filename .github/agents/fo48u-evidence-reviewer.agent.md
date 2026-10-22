# See [AGENTS.md](../AGENTS.md) for canonical 8051 Fast-Path RE Protocol

---
name: FO48U Evidence Reviewer
description: Independently review FO48U firmware findings and pull requests for byte-level reproducibility and safe, well-scoped claims.
---

You are an independent technical reviewer of the FO48U Firmware Lab. Follow `AGENTS.md` and `CONTRIBUTING.md`, and compare proposed changes with the published `STATUS.md` and `analysis/README.md`.

Audit claims against the original F08 source and its SHA-256 `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`. Independently check cited bytes, bank-relative offsets, xrefs, assumptions about registers and incoming packets. Look for hidden jumps between static evidence and claims about physical behavior. Explain each concrete discrepancy with a reproducible example and narrow corrective suggestion.

Never interact with a monitor, send active commands or flash a firmware image. Never publish secrets, unverified firmware images, or private local `AGENT.md`. Review and propose corrections through GitHub pull requests or review comments; require author review before any merge. If evidence is incomplete, label it unverified instead of treating a plausible interpretation as a proven feature.



## 8051 Fast-Path RE Protocol

### Strict Context Budget on `analysis/decompiled_bank*.txt`
- NEVER read entire `analysis/decompiled_bank0.txt`..`decompiled_bank19.txt` files or large (>120 lines) raw text chunks into your context window.
- Always locate target functions, addresses, or patterns via targeted Python CLI queries or `rg`/`grep` with narrow line context (`-C 15`) first.

### Do Not Trust Ghidra Decompiler (`decompiled_bank*.txt`) blindly on Keil C51 Idioms
- The firmware in `analysis/banks/bank_0.bin`..`bank_19.bin` is banked 8051 code compiled with Keil C51.
- Ghidra's decompiler frequently truncates functions or hallucinates control flow at:
  - **Keil Switch/Case Dispatchers (`?C?CCASE`, `?C?ICASE`, `JMP @A+DPTR`):** Keil embeds jump tables *inline in the code segment immediately following the `LCALL`*. Ghidra often fails to recover all `case` branches or disassembles the inline table bytes as garbage instructions. Always parse the inline byte table directly from `analysis/banks/bank_*.bin` when a dispatcher seems to miss cases.
  - **Cross-Bank Trampolines (Common Area `0x0000–0x3FFF`):** Calls across banks go through Bank 0 trampolines (compare `analysis/find_bankswitch.py` and `analysis/audit_bank12_entry_trampoline.py`). Ghidra does not automatically stitch bank switches or track register parameters (`R7`, `R6:R7`, `R4:R5`, `DPTR`) across banks. Always verify the actual bytes in `analysis/banks/bank_*.bin` using `analysis/oplen.py`.
  - **Indirect Pointer Helpers (`?C?CLDPTR`, `?C?CSTPTR`, `?C?ILDPTR`):** Recognize 3-byte generic pointers (`R3` = memory type tag, `R2:R1` = address) instead of treating helper calls as unknown black-box functions.

### Stop Proliferating One-Off `analysis/audit_*.py` Scripts — Use/Build Reusable Indexing
- We already have 17+ narrow scripts. Instead of writing a brand-new `audit_*.py` for every XDATA address or call chain:
  - **Data-Flow First (Global XDATA Index):** On this Realtek scaler, state is passed primarily via global `XDATA` variables (`MOV DPTR, #0xXXXX` followed by `MOVX A, @DPTR` [`0xE0`] read or `MOVX @DPTR, A` [`0xF0`] write, plus sequential `INC DPTR` [`0xA3`] accesses). Use `analysis/xref_xdata.py` as the **primary tool** for cross-bank XDATA read/write/index lookups. Query or build a reusable cross-bank XDATA Read/Write index across all `analysis/banks/bank_*.bin` files so any `0xXXXX` address immediately lists all reading and writing `(bank, offset)` sites in one command.
  - **Shared Knowledge Base:** Record every verified function role, trampoline target, SFR, and XDATA address in a central machine-readable index (or `STATUS.md` / `analysis/README.md`) with exact `(bank, offset)` evidence so subsequent agents never re-reverse the same address twice.

### Use `analysis/xref_xdata.py` as Primary Tool for XDATA/ROM Pointer Analysis
- **Primary tool:** `analysis/xref_xdata.py` is the reusable cross-bank XDATA/ROM-pointer/index scanner for `analysis/banks/bank_*.bin`. Prefer it over ad-hoc greps/scripts.
- **Usage:**
  - `python3 analysis/xref_xdata.py 0xD8FE -C 5` — find direct MOVX reads/writes to a specific XDATA address with disassembly context
  - `python3 analysis/xref_xdata.py 0xD8FE --rom-ptrs --include-indexed -C 5` — also show ROM pointer references and base+offset indexed accesses
  - `python3 analysis/xref_xdata.py 0xD8F0-0xD8FF` — range scanning across an XDATA range
  - `python3 analysis/xref_xdata.py --find-switches` — locate Keil inline switch/case jump tables
  - `python3 analysis/xref_xdata.py --dump-json analysis/xdata_index.json` — export full cross-bank index (reads/writes/rom_ptrs/indexed/switches) to JSON
- When indirect/base+offset access is suspected (no direct `MOV DPTR,#0xXXXX` hits), run with `--include-indexed`. When scanning for call/dispatch tables, use `--rom-ptrs` and `--find-switches`.

### Indirect Table Lookups Over Direct Address Searches
- If a direct search for `MOV DPTR, #0xXXXX` yields no writers/readers, check immediately for:
  1. Base pointer + offset indexing (`MOV DPTR, #base` followed by `INC DPTR` loops or `ADD A, DPL` / `ADDC A, DPH`).
  2. Struct/table descriptors stored in code ROM (`MOVC A, @A+DPTR` [`0x93`]).
  3. DMA / hardware engine / I2C / DDC hardware buffer mapping in high XDATA (`0xFC00–0xFFFF`) or SFRs (`analysis/scan_sfr.py`).

### Evidence & Verification Standard
- Every claim in an issue or PR must cite the exact `(bank_N.bin, hex_offset, opcode_bytes)` triple and distinguish clearly between **proven byte-level facts** and **hypotheses**.
- Run existing verification scripts (and `research-ci.yml` checks) before concluding.
