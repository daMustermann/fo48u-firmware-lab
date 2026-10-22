# AI agent guide (public)

Welcome, independent coding agents. This tracked `AGENTS.md` is the public onboarding guide for work on the Gigabyte AORUS FO48U firmware research repository. Read [README.md](README.md), [STATUS.md](STATUS.md), and [analysis/README.md](analysis/README.md) before proposing changes; use [analysis/panel_protection.md](analysis/panel_protection.md) for panel-care claims.

**Do not confuse these files:** `AGENTS.md` (plural) is public and belongs in Git. `AGENT.md` (singular) is an **ignored, local-only** notebook. Never commit, quote, copy, or depend on `AGENT.md` in a public contribution. Your checkout may not contain it.


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


## Safety and scope

- Work primarily on static analysis and offline reproducibility. Gated host-side commands are permitted for research on hardware you own, with explicit confirmation and read-only defaults; never flash firmware or disable OLED protection.
- **Never flash firmware or instruct others to flash research images.** No modified firmware has been hardware-validated, and there is no verified recovery procedure. Do not change or disable OLED protection on a device.
- Never add or distribute modified, generated, or unvalidated firmware binaries. The existing stock reference is the sole published firmware image; experimental outputs remain local and ignored.
- Do not publish secrets, credentials, personal identifiers, local machine paths, private notes, or raw captures containing sensitive data.
- Respect the scope of your assigned files, preserve unrelated changes, and do not commit or push unless specifically authorized for that task.

## Reference and evidence

- The source of truth is `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`, **2,031,616 bytes**, SHA-256 **`3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`**. Check the digest before interpreting offsets; a shared version label alone is insufficient.
- Use **`bank:address`** notation for bank-relative code addresses (for example, `13:CAA8`). Each bank is `0x10000` bytes; `file_offset = bank * 0x10000 + address`. Clearly label file offsets and XDATA addresses separately (for example, `XDATA 0xD12D`).
- Cite exact source bytes, paths, offsets, script commands, and observed output. Separate byte-verified findings, inferences, hypotheses, and unresolved behavior. Negative findings also need reproducible evidence.
- Keep APCS (**4 h**), AOCS (**1,500 h**), and TSS (**36 h reminder**) distinct. These are **static code thresholds**, not measured hardware intervals. Manual activation, input framing, and modified-image safety remain unverified; see `STATUS.md`.

## Advanced FO48U Architecture Shortcuts

### 1. Why `0xD8FE` / Buffer Handoff Upstream Searches Missed Writers
Do NOT restrict upstream searches for `0xD8FE` (or `0xD8xx` buffers) to `MOV DPTR, #0xD8FE` (`90 D8 FE`). On Keil C51 + Realtek RTD2718, buffer population and handoffs frequently use:
- **Keil 3-Byte Generic / 2-Byte XDATA Pointers in Registers:** Scan all `analysis/banks/bank_*.bin` for `MOV R2, #0xD8` (`7A D8`) or `MOV R6, #0xD8` (`7E D8`), where the High Byte `0xD8` is passed in `R2`/`R6` and the Low Byte (`0xFE` or buffer base) in `R1`/`R7` into `bank_0.bin` helper routines (`?C?CSTPTR`, `?C?CLDPTR`, `?C?COPY`).
- **Paged 8-bit `MOVX @R0, A` (`0xF2`) / `MOVX @R1, A` (`0xF3`):** Scan for `MOV P2, #0xD8` (`75 A0 D8`) or XPAGE SFR writes combined with `MOV R0, #0xFE` (`78 FE`) / `MOV R1, #0xFE` (`79 FE`) followed by `0xF2` or `0xF3`.
- **Hardware-Mapped DDC/CI & Scaler Registers:** Remember that high XDATA on Realtek scalers includes hardware-mapped I2C/DDC-CI slave buffers (`MCU_DDCCI_*`) and status latches updated directly by the RTD2718 hardware engine or copied inside an ISR.

Reproduction: `python analysis/audit_d8fe_upstream_patterns.py`

### 2. Trace `dual_ingress` & `rx_acceptance` Forward from 8051 Interrupt Vectors (`bank_0.bin`)
Stop tracing `dual_ingress` and `receiver_origins` solely backward from the main-loop service dispatcher — ISR producers and main-loop consumers are decoupled via ring buffers and ready flags (`bRxReady`), so there is no `LCALL` link between them.
- Disassemble forward from the hardware interrupt vector table at the start of `analysis/banks/bank_0.bin`:
  - `0x0003` (`IE0` - External Int 0, primary Scaler / DDC-CI IRQ)
  - `0x000B` (`TF0` - Timer 0)
  - `0x0013` (`IE1` - External Int 1, secondary I2C / AUX / USB bridge IRQ)
  - `0x0023` (`RI/TI` - UART0 serial ingress from USB hub/bridge)
  - `0x002B` (`TF2` - Timer 2 / UART1)
- Map every XDATA buffer base, write index, and completion flag written inside these ISRs and match them against the readers in `audit_ddcci_ingress.py`, `audit_dual_ingress.py`, and related scripts.

Reproduction: `python analysis/audit_isr_forward_trace.py`

### 3. Build a Universal Cross-Bank Trampoline Map (`analysis/trampoline_map.json`)
Instead of analyzing trampolines one by one (like `audit_bank12_entry_trampoline.py`), parse the entire bank-switching stub table in the common area of `analysis/banks/bank_0.bin` (building on `analysis/find_bankswitch.py`) and export a complete `analysis/trampoline_map.json` mapping:
`common_trampoline_addr -> {target_bank, target_addr}` across all 20 banks (`bank_0.bin`..`bank_19.bin`).

Reproduction: `python analysis/build_trampoline_map.py`

### 4. Extract Ground-Truth Sidekick Protocol from `osd-sidekick/B21.0707.1/`
Instead of guessing packet field usage, command sub-opcodes, and the F08 handoff purely from 8051 disassembly (`audit_sidekick_commands.py`, `audit_sidekick_f08_handoff.py`, `audit_packet_field_usage.py`), inspect the host-side sender already in the repo (`osd-sidekick/B21.0707.1/UpdPack.cab`, `Install.exe`, `support.xml`) to extract exact command IDs, payload offsets, checksums, and ISP handoff sequences.

Reproduction: `python analysis/extract_sidekick_protocol.py`

## Contribution workflow

1. **Fork the repository**, make a topic branch on your fork, and submit a **pull request** to upstream. Do not push directly to upstream branches or merge your own contribution.
2. Keep changes focused and reviewable. Record the stock hash, bank:address references, original bytes, reproduction commands, output, and confidence limits in the PR.
3. Run the **offline acceptance commands in [CONTRIBUTING.md](CONTRIBUTING.md)** (taken from `README.md`), and report results and unavailable dependencies. Use builders **only with `--verify`** for acceptance; never generate firmware as part of CI or a PR.
4. Check the diff for secrets, accidental binaries, ignored `AGENT.md`, and unrelated changes before opening the PR. If evidence is insufficient, document the question instead of asserting a working feature.
