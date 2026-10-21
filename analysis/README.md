# FO48U / F08 firmware anatomy

This is a reproducible map of the **F08 (2022-11-15)** firmware image used throughout the repository. All offsets below are **bank-relative** unless called out as file offsets; findings concern this particular image and may not transfer to other revisions.

[Overview](../README.md) · [Research status](../STATUS.md) · [OLED scheduler](panel_protection.md) · [Sidekick HID evidence](sidekick-protocol.md)

## Image and architecture

| Image property | Finding |
| :-- | :-- |
| Target scaler | Realtek RTD2718, banked 8051 |
| Source | `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` |
| Size | `0x1F0000` (31 × `0x10000` bytes) |
| Code | Banks 0–19; common prefix through approximately `0x536B` |
| Unused blocks | Banks 20–26 primarily `FF` |
| Table/tail data | Banks 27–30 |
| MD5 | `d4324c6c88abea48b1ee896f7e14ee9f` |

To locate code in the file, use `file_offset = bank * 0x10000 + address`.

The shared bank switch is at **`0x6000`**, with the target bank passed in **`R7`**. It writes the bank selector at **XDATA `0xFFFF`**. The switch must be accounted for when reasoning about calls to bank-local addresses.

## OLED panel protection

Bank 13 contains the scheduler at approximately `CA4E..CB60`. Its three core settings are:

| Mechanism | Code location | Threshold |
| :-- | :-- | --: |
| APCS | `13:CAA8` | 4 elapsed panel-use hours |
| AOCS | `13:CAD3` | 1500 h divisor |
| TSS | `13:CB1A` | 36 hours since last APCS |

XDATA `D13D:D13E` stores total usage hours (big-endian), `D13F` tracks minutes, `D12E:D12F` stores APCS reference hours and `D12D` holds the APCS/AOCS request bits. The consumers are in bank 18 at `92BC` and `92F1`. See [panel_protection.md](panel_protection.md) for the byte-level paths and their limits.

## Service menu and its action handlers

- Bank 1 includes an OSD string index table near `D707`, with 310 index records. APCS and AOCS correspond to string IDs **279** and **280**.
- Bank 9 includes the service-menu page descriptors around `9783` and action dispatch around `97F0`.
- Actions **23 (APCS)** and **24 (AOCS)** dispatch to bank-9 handlers `A14C` and `A1C0` respectively.
- The handler branches manipulating `0BAD` and `0BAE` do **not** directly update real requests in `D12D`.
- The bank-9 traversal at `D516` invokes action handlers during enumeration and can supply register values that resemble a selection without physical input.
- At `9:D45C`, the incoming `R7` value is stored in XDATA `C501`. Values `0/1/2/5` reach the page/row traversal at `9:D516`, which accesses the descriptors using `C503/C502`. At `9:E4B5`, a row index can be turned into an action ID before dispatch at `9:97DB`.
- Both page-layout tables include actions **23/24** as adjacent items (`9:9783`, page index 3; `9:9797`, page index 1). This verifies their presence in the enumeration data, **not** a joystick selection.
- Calls to `9:E057` at `F77C`, `F787` and `F78E` supply action IDs **11, 11, 14**. Its call site at `E0E2` cannot establish APCS/AOCS activation for IDs 23/24.

These claims are checked against the hash-identified F08 bytes by `python -B analysis/audit_joystick_event_chain.py`. This establishes **menu records and call graphs**, while the physical joystick-event origin, selection route and connection to the `D12D` request bits remain unresolved. Register values from an enumeration path are insufficient proof of a keypress.

## Command routing and host protocols

Bank 12 holds a 100-entry indirect command table near `5D85..5EB0`. The APCS and AOCS commands are mapped as:

| Command | Handler | Request |
| :-- | :-- | :-- |
| `80` | `12:68A9` | `D12D |= 01` if `CFDE == 2` |
| `82` | `12:68B9` | `D12D |= 02` if `CFDE == 2` |

The surrounding dispatch path examines `CFDB == E0` and `CFDA` values including `01`/`03`. The **source and complete framing of incoming bytes are unknown**. `CFDE` is used as an operand/index elsewhere in firmware; it is not identified as a universal service-mode flag.

The bank-12 dispatcher also has a **verified cross-bank caller**. Bank 18 executes `LCALL 0x2DB2` at `18:D6CE`. Shared stub `0:2DB2` contains `90 53 9D 02 0C 54` (`MOV DPTR,#539D; LJMP 0C54`); `0:0C54` builds a synthetic return address, and `0:5030` selects bank 12 through `0:507E` (selector write to XDATA `FFFF`). Execution enters `12:539D`, runs initialization, and falls through to the `CFDB == E0` guard at `12:53FC` on the normal-return path. The bytes and the sole literal `LCALL 2DB2` occurrence among code banks 0–19 are pinned by `analysis/audit_bank12_entry_trampoline.py`.

That bank-18 call has **additional gates**: `18:D6B2` checks a bit of XDATA `D183`; `18:D6BE` reads `CFD2`, with zero bypassing this path; the calls at `18:D6C9` and `18:D6CE` each have a carry-conditional exit. This demonstrates a firmware call route into bank 12, but does **not** prove which external transport, if any, supplies the incoming fields or that any command is accepted. Raw opcode matching cannot rule out other indirect callers.

Both handlers join at `12:68C6` for the conditional `MOVX @DPTR,A` write to XDATA `D12D`, followed by helper calls. Successful writes then branch to `12:68D4` (`SETB C; RET`); rejecting `CFDE != 02` reaches **the same return** directly. Therefore the returned carry flag alone cannot confirm that a request bit was written, let alone that the panel ran compensation. These byte-level paths are checked by `analysis/audit_refresh_command_table.py`.

Distinct paths interpret `CFDA` differently:

| Location | Values / guard | Notes |
| :-- | :-- | :-- |
| `18:D6D3` | `01 03 07 0C F3` | DDC/CI-like command family |
| `7:6945` | `C0 D0` | Alternate command family |
| `10:F801` | `77 AA`, if `CFD8 == 71` | Separate guarded protocol |
| `12:53FC` | `01 03`, with `CFDB == E0` | Bank-12 service-command path |
| `7:B226` | Copies `CFDB..CFDE` to `CF84..CF87` | Buffer handoff |

### Candidate receive-buffer writer

An additional **conditional indirect XDATA write path** is visible in the original F08 bytes. At `13:E3B1`, the code checks `(XDATA FF23 & FE) == 6E`, a value compatible with a DDC/CI address comparison. After calling the shared routine at `2656`, `13:E3BB..E3D1` selects an 0x80-byte buffer beginning at XDATA `CFD8` when `R7 == 0`; the other branch selects an 0x50-byte buffer at `CEE1`. At `13:DD24`, the selection parameters are saved to `C9C2..C9C5`.

The receive path at `13:DD7A` reads XDATA `FF25` and calls `13:EF0D`. That helper retrieves the selected base and computed index, then calls the common routine at `0:36C0`, whose `R3 == 01` branch writes through a computed `DPTR` using `MOVX @DPTR,A` at `0:36CF`. **`CFDA..CFDF` lie at offsets 2..7 of the `CFD8` buffer**, making this a concrete potential writer route that direct DPTR reference scans alone would miss. The original instructions are pinned by `analysis/audit_ddcci_ingress.py`.

A **second receive path is now verified** in bank 13. `13:EAF5` checks `(FE87 & FE) == 6E`; `13:EB04` passes XDATA base **`CF31`** to `13:DE63`. That routine seeds the buffer from **`FE88`**, reads subsequent bytes from **`FE89`** (`13:DEB3`), and uses the *same* indirect writer `13:EF0D`. It checks status bytes `FE8B`/`FE8D`, imposes an 80-byte capacity (`13:DEA2`), and returns `R7=1` on its completed-length path or `R7=0` otherwise (`13:DEFA..DEFF`). The first receiver analogously uses `FF24`/`FF25`, status `FF27`/`FF29`, and returns `R7=1` or `0` (`13:DDBE..DDC3`). This demonstrates two separate **firmware register paths**; their underlying hardware or external transport is not identified.

Further stock-byte checkpoints explain the candidate frame structure: `13:DD3C` seeds the receiver with a byte from `FF24`; `13:EF23` obtains byte 1 of the selected buffer and computes `(byte & 0x7F) + 3`. This is compatible with a length-coded protocol; its physical origin and full frame validation remain open. At `13:DDA4`, conditional code compares selected-buffer offsets 3 and 2 to `FC` and `03`, respectively. A separate path at `13:DEB3` feeds a byte read from XDATA `FE89` into the same `13:EF0D` helper. At `13:C8BF`, another bank-13 routine copies `CFDA/CFDB` to `C9C4/C9C5`; this is an observed consumer/copy, without a proven link to bank 12. These additional original byte ranges are checked by `analysis/audit_ddcci_ingress.py`.

### Conditional buffer handoff

Two cross-bank helpers read the same state byte, XDATA **`D8FE`**, via logical bank 4. In the bank-13 receive branch, `13:E3BB` calls `0:2656 → 4:FCFE` to obtain `D8FE` in `R7`. Zero selects the 128-byte buffer at `CFD8`; nonzero selects the 80-byte buffer at `CEE1`. At `13:E3D4`, the code writes `(CFD2 & FE) | R7` back to `CFD2`, but the intervening `13:DD24` can overwrite `R7` (including a read from `FF24`). **The flag written to `CFD2` cannot be assumed to equal `D8FE`.** `D8FE` is mutable: `4:FB1F` writes its input `R7`, `4:E6F3` clears it, and `4:E70B` copies XDATA `C693` into it.

Two concrete callers of setter `4:FB1F` narrow the origin of `D8FE`. At `4:BA29`, the input `R7` is loaded from `C68A`. An upstream path maps XDATA `D180` to `R7=00/10/20` at `2:FE80`, then passes through `2:FAC5 → 0:2D2E → 4:B9D7` to write `C68A`. At `4:BA31`, a separate selector `0C` writes `C68A` to `D83C` through `3:8AB5`. The getter at `4:F348` uses `0:0FF4 → 3:A98D → 3:AA07` to load `D83C`, returning it in `R7` before the setter call. There are numerous other literal references and writers of `C68A`, so these paths do not establish its exclusive origin. `4:E6D4..E70B` also **saves the old `D8FE` to `C693`, clears it, then restores that saved value**. These byte-level sites are verified by `analysis/audit_d8fe_upstream.py` and `analysis/audit_d8fe_sources.py`.

A different `C693` writer at `3:BF9D..BFA2` uses common trampoline `0:0F52 → 0:0C08 → 0:5020` to enter **bank 8**, `8:EE5E`. That function saves its incoming `R7` in `C6A2`, reads **`D8FE`** through `8:FD3B`, branches on `D8FE == 10/20`, and conditionally examines `D8FC` and `C6A2`. Its direct return sites set `R7` to `03`, `0C`, `0F`, or `10`, which `3:A823` stores in `C693`. Thus this call **uses `D8FE` as an input**, rather than demonstrating its origin. The distinct bank-4 save/restore routine overwrites `C693` before restoring `D8FE`, so these two uses of `C693` cannot be joined into a value-flow claim. See `analysis/audit_d8fe_sources.py` for stock-byte checks.

The bank-18 stage at `18:E22D` iterates **bits 0 then 1** of `CFD2`. On the first enabled bit, `18:E24E` calls `0:2A58 → 4:FE6D`, which also returns `D8FE`. When that value is nonzero, `18:E254..E270` calls the common memory copier (`0:35FC`) with an 80-byte XDATA source at **`CEE1 + slot × 0x50`** and destination **`CFD8`**. The dispatch table `0:359A` selects XDATA-to-XDATA implementation `0:35CF`. Thus slot 0 starts at `CEE1`; slot 1 starts at `CF31`. The selected index is stored at `CFD1` even when the `D8FE` test skips copying.

The receive-result handling also explains **both `CFD2` low bits**. After `13:DD24`, `13:E3D4` combines its final `R7=0/1` with `CFD2 & FE`, writing bit 0. After `13:DE63`, `13:EB0D` calls `13:F7B0`, which doubles the final `R7=0/1` and combines it with `CFD2 & FD`, writing bit 1. Further conditional processing by `13:C8A4` may clear bit 0 (`13:E3E8`) or bit 1 (`13:EB1F`). Bank 18 clears the selected bit using `CFD1` at `18:D712..D72C`. These are **receive completion/processing flags**, not proof that either frame passed every validation stage. The two paths have a common `(buffer[1] & 7F) + 3` computed length, and both contain the conditional `FC 03` check, but exact acceptance semantics remain open.

`13:C8A4` reads command fields from `CFD8` when `D8FE==0`, or from `CEE3 + slot × 0x50` when nonzero (offset 2 of the selected 80-byte slot). This is a further verified link between the receive buffers and downstream field processing; it does not establish a valid APCS/AOCS invocation. The new byte-level evidence is guarded by `analysis/audit_dual_ingress.py` alongside `analysis/audit_buffer_handoff.py`.

Bank 18 calls the handoff at `18:D6C6` **before** its bank-7 and bank-12 calls. Paths feeding `D8FE` have been found, but the runtime origin of `D180`, intervening helper side effects, other possible `C68A` writers, live state, physical framing, hardware register meanings, checksum acceptance and end-to-end service-command reachability remain unresolved.

These findings are evidence for conditional buffer selection, a possible length field, and an internal bank-18 buffer handoff. The physical DDC/CI framing, checksum acceptance, which transport fills `FF25`/`FE89`, and the end-to-end conditions for a successful bank-12 command remain unverified.

Bank 19 contains a conditional internal path at `80A4` that may set both request bits when `C501 == 0x20` and other state checks pass. No evidence currently connects that condition to an external USB command.

## Reproduction

Run from the repository root, using Python 3:

```bash
python analysis/audit_8051_opcodes.py
python analysis/audit_ddcci_ingress.py
python analysis/audit_bank12_entry_trampoline.py
python analysis/audit_buffer_handoff.py
python analysis/audit_dual_ingress.py
python analysis/audit_d8fe_sources.py
python analysis/audit_d8fe_upstream.py
python analysis/audit_menu_reachability.py
python analysis/audit_joystick_event_chain.py
python analysis/audit_packet_field_usage.py
python analysis/audit_packet_route_families.py
python analysis/audit_refresh_command_table.py
python analysis/audit_service_dispatch.py
python analysis/build_variant.py --verify
python analysis/build_custom.py --verify
```

Other useful inputs include `osd_strings.py`, `osd_strings.txt`, `banks/bank_*.bin` and `decompiled_bank*.txt`. Use Ghidra in **8051 raw-binary** mode with a bank image based at address `0x0000`, or use radare2 for independent code-path inspection.

### Linux / WSL2 signature scan

Start with the [portable WSL2 / Linux offline guide](../docs/WSL2_OFFLINE_RESEARCH.md) to check dependencies, validate the stock image hash, and reproduce the scan. Inside a Linux shell, with `FW` pointing to the hash-verified stock F08 file, discover paths rather than assuming an installation directory:

```bash
BINWALK_BIN="$(type -P binwalk || true)"
REA_BIN="$(type -P rea || true)"
test -n "$BINWALK_BIN" || { echo "Binwalk is unavailable on PATH" >&2; exit 1; }
"$BINWALK_BIN" "$FW"
if test -n "$REA_BIN"; then
  REA_BINWALK_COMMAND="$(readlink -f "$BINWALK_BIN")" \
    "$REA_BIN" inspect-firmware-regions "$FW" --format json
else
  echo "REA CLI unavailable; the standalone Binwalk scan above remains usable" >&2
fi
```

The REA invocation requires a Linux-compatible installation and was **not independently completed** in the recorded WSL2 test; the standalone Binwalk scan was tested. A short `gpg_signed`-like signature candidate at `0x5A3F5` lies inside apparent table data and **does not establish the presence of a signed GPG payload**. Treat signature scans as leads rather than proof of embedded formats.

A monitor-connected read-only GET-VCP `E0` probe also yielded a generic-looking reply. It does not prove a callable vendor command. The active work is mapping packet ingress and joystick selection; no firmware is considered ready for hardware flashing.
