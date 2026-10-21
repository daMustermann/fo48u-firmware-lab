# FO48U / F08 firmware anatomy

This is a reproducible map of the **F08 (2022-11-15)** firmware image used throughout the repository. All offsets below are **bank-relative** unless called out as file offsets; findings concern this particular image and may not transfer to other revisions.

[Overview](../README.md) · [Research status](../STATUS.md) · [OLED scheduler](panel_protection.md)

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
- Calls to `9:E057` at `F77C`, `F787` and `F78E` supply action IDs **11, 11, 14**. Its call site at `E0E2` cannot establish APCS/AOCS activation for IDs 23/24.

This establishes **menu records and call graphs**, while the exact physical selection route remains unresolved. Register values from an enumeration path are insufficient proof of a keypress.

## Command routing and host protocols

Bank 12 holds a 100-entry indirect command table near `5D85..5EB0`. The APCS and AOCS commands are mapped as:

| Command | Handler | Request |
| :-- | :-- | :-- |
| `80` | `12:68A9` | `D12D |= 01` if `CFDE == 2` |
| `82` | `12:68B9` | `D12D |= 02` if `CFDE == 2` |

The surrounding dispatch path examines `CFDB == E0` and `CFDA` values including `01`/`03`. The **source and complete framing of incoming bytes are unknown**. `CFDE` is used as an operand/index elsewhere in firmware; it is not identified as a universal service-mode flag.

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

This is evidence for a buffer-selection/write mechanism, **not proof** of a physical DDC/CI frame, which transport fills `FF25`, or the path into bank-12 command dispatch at `12:53FC`. The meaning of the `2656` result and the full framing/checksum conditions still require tracing.

Bank 19 contains a conditional internal path at `80A4` that may set both request bits when `C501 == 0x20` and other state checks pass. No evidence currently connects that condition to an external USB command.

## Reproduction

Run from the repository root, using Python 3:

```bash
python analysis/audit_8051_opcodes.py
python analysis/audit_ddcci_ingress.py
python analysis/audit_menu_reachability.py
python analysis/audit_packet_field_usage.py
python analysis/audit_packet_route_families.py
python analysis/audit_refresh_command_table.py
python analysis/audit_service_dispatch.py
python analysis/build_variant.py --verify
python analysis/build_custom.py --verify
```

Other useful inputs include `osd_strings.py`, `osd_strings.txt`, `banks/bank_*.bin` and `decompiled_bank*.txt`. Use Ghidra in **8051 raw-binary** mode with a bank image based at address `0x0000`, or use radare2 for independent code-path inspection.

### Linux / WSL2 signature scan

The working CLI route uses REA on Linux with Binwalk on the same image:

```bash
REA_BINWALK_COMMAND="$HOME/.cargo/bin/binwalk" \
  "$HOME/.local/bin/rea" inspect-firmware-regions \
  firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin \
  --format json
```

A short `gpg_signed`-like signature candidate at `0x5A3F5` lies inside apparent table data and **does not establish the presence of a signed GPG payload**. Treat signature scans as leads rather than proof of embedded formats.

A monitor-connected read-only GET-VCP `E0` probe also yielded a generic-looking reply. It does not prove a callable vendor command. The active work is mapping packet ingress and joystick selection; no firmware is considered ready for hardware flashing.
