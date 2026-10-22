# Current research status

**Target:** Gigabyte AORUS FO48U · **Image:** F08 / 2022-11-15 · **Method:** static firmware analysis and read-only host observations.

| Track | Status | Scope |
| :-- | :-- | :-- |
| Stock image identity | **Verified** | 2,031,616 B; MD5 `d4324c6c88abea48b1ee896f7e14ee9f` |
| 8051 bank layout and switch | **Verified in bytes** | Code banks 0–19; PBANK_SEL at `FFFF`; shared switch function `6000` |
| OLED scheduler | **Verified in bytes** | APCS 4 h / AOCS 1500 h / TSS 36 h in bank 13 |
| OLED requests | **Verified in bytes** | `D12D` bit 0 APCS, bit 1 AOCS; bank-18 consumers |
| Service-menu entry records | **Verified in bytes** | Bank-9 entries 23/24 call `A14C` / `A1C0` |
| Bank-12 commands | **Verified in bytes** | `80` → `68A9`; `82` → `68B9`; handler operand `CFDE == 2` |
| Official Sidekick APCS/AOCS commands | **Verified in application bytes; device execution open** | `GOSD.OLEDSet.SetOSD(3)` constructs `E0 80 00 02` (APCS) / `E0 82 00 02` (AOCS) inside Realtek-HID frames. See [Sidekick protocol](analysis/sidekick-protocol.md). |
| Sidekick-frame firmware alignment | **Byte-verified conditional mapping; physical path open** | An intact 8-byte frame placed at `CFD8` meets the RX length rule and yields `CFDA..CFDE = 03 E0 80/82 00 02`, matching the guarded bank-12 command table. `analysis/audit_sidekick_f08_handoff.py` verifies the byte anchors; no live receive proven. |
| Bank-12 caller | **Verified in bytes; input origin open** | Conditional `18:D6CE` call via shared `0:2DB2` trampoline to `12:539D`, then `12:53FC` |
| Internal buffer handoff | **Verified conditional byte path** | `13:E3BB` tests `D8FE`; `18:E22D` can copy 80 B from `CEE1` or `CF31` into `CFD8` before bank-12 dispatch |
| `D8FE` source paths | **Verified byte routes; runtime state open** | `2:FE80` maps `D180` to `00/10/20`, reaching `4:B9D7` through a bank-switch path that writes `C68A`. `4:BA29` feeds `C68A` to the `D8FE` setter; `4:BA31` stores `C68A` in `D83C`, which `4:F348` can read back. Other writers of `C68A` exist. |
| Dual receive slots and completion flags | **Verified in bytes** | `13:DD24` reads `FF24/FF25` for `CFD8` or `CEE1`, sets `CFD2` bit 0 conditionally; `13:DE63` reads `FE88/FE89` for `CF31`, sets bit 1 conditionally. `13:C8A4` and `18:D712` include conditional flag clearing. |
| Firmware interrupt entry | **Verified in bytes; peripheral open** | 8051 INT1 vector `0:0013 → 0:520B` conditionally calls bank-13 receiver routines or bank-7 `BA52`, gated by `D183` bit 2 and IRAM `0x27.5`. See `analysis/audit_receiver_origins.py`. |
| Incoming packet framing | **Byte-verified; acceptance rule established** | Bank-13 paths: length `(buffer[1]&7F)+3` in register bank 2 (IRAM 0x17), counter in IRAM 0x58. The `FC`/`03` comparison pair returns `R7=1` on both arms (cannot reject), the matching arm's `LCALL 13:F4B0` writes no XDATA, only buffer offsets 1,2,3 are read (no inbound checksum). Path B merges the last-compared byte into `CFD2` bit 1 via `13:F7B0`. Transport (`FF24/FF25`/`FE88/FE89`) and the second CJNE's `R4` remain open. `analysis/audit_rx_acceptance.py` |
| Candidate incoming buffer writer | **Verified in bytes; route open** | Conditional bank-13 `CFD8` buffer, `FF24` seed, `FF25`/`FE89` feed and indirect `0:36CF` XDATA writer; its connection to the bank-18 caller is open |
| Manual joystick selection | **Open** | Actual user-event path to APCS/AOCS not demonstrated |
| ASC auto-dimming | **Documented** | Manual documents 10-min 50% dim and 15-min screensaver; not a verified firmware patch target |

The observations are specific to the hash-identified binary. Static analysis alone cannot establish a reliable manual refresh procedure.

## Key addresses

| Bank:address / XDATA | Meaning |
| :-- | :-- |
| `13:CAA8` | APCS elapsed-use threshold `04h` |
| `13:CAD3` | AOCS modulo/divisor `05DCh` (1500) |
| `13:CB1A` | TSS reminder threshold `24h` (36) |
| `D12D` | APCS / AOCS request bits |
| `18:92BC` / `18:92F1` | Request consumers |
| `9:97F0` | Service action dispatch table |
| `9:A14C` / `9:A1C0` | APCS / AOCS service item handlers |
| `12:68A9` / `12:68B9` | Command-table APCS / AOCS handlers |
| `18:D6CE` → `0:2DB2` → `12:539D` | Guarded cross-bank entry into bank-12 protocol setup |
| `18:E254` → `0:35FC` → `0:35CF` | Conditional 80-byte XDATA copy into `CFD8`; enabled by `CFD2` bit 0/1 and `D8FE` |
| `3:BF9D` → `0:0F52` → `8:EE5E` | Maps `D8FE`/`D8FC` and incoming `R7` into `03/0C/0F/10`; `3:A823` stores result in `C693` |
| `19:80A4` | Conditional state-triggered request for both |
| `CFDA..CFDF` | Shared protocol fields; usage differs by command family |

## Host-side evidence

A connected official Sidekick 1.21.0707.1 process was passively observed issuing an HID-backed `E0 50` query using `RtHIDLib.dll`. Its separately byte-verified IL exposes APCS/AOCS **execution** commands `80/82` and OLED **readback** selectors `7F..83`; neither a response value nor compensation execution has been demonstrated. Its Realtek-HID model branch uses VID:PID `0BDA:1100`, and Windows enumerates that HID interface, though the process-to-device handle remains unobserved. Details: [Sidekick protocol](analysis/sidekick-protocol.md).

A read-only DDC/CI probe returned a response to GET-VCP `E0` that resembled the result for `DF`. This **does not prove** an accessible vendor service command: the device does not advertise `E0`, and generic fallback behavior remains plausible. No Set-VCP or USB write tests were performed.

Firmware has several distinct paths using `CFDA`:

- Bank 18: `01/03/07/0C/F3`, DDC/CI-like path.
- Bank 7: `C0/D0`.
- Bank 10: `77/AA` when `CFD8 == 71`.
- Bank 12: `01/03` alongside `CFDB == E0`.

`CFDE` is also a numerical operand or index in other handlers. The `CFDE == 2` test alone does not identify a global service unlock.

## Research priorities

1. Determine the runtime origin of `D180` and the other `C68A` writers, then physical ingress behind the **two identified receive register paths** (`FF24/FF25` and `FE88/FE89`), using **passive or read-only** evidence.
2. Follow physical joystick input to a **true selection event** for service actions 23/24.
3. Correlate selection, request-bit updates and the bank-18 state machine.
4. Determine verified recovery and hardware-test procedures before considering any modified firmware.

The detailed evidence and commands live in [analysis/README.md](analysis/README.md) and [analysis/panel_protection.md](analysis/panel_protection.md).

> **Safety:** OLED compensation is part of panel maintenance. Do not disable it or flash research images based only on static analysis.

## XDATA 0xD12D readers

nalysis/xref_xdata.py 0xD12D lists 20 direct reads across banks 0, 7, 11-13, 18-19 and no direct MOVX @DPTR,A writer. Request bits are therefore likely set through bit-addressable/indirect operations or hardware-mapped paths, not a simple direct store.


## XDATA 0xD180 readers

nalysis/xref_xdata.py 0xD180 lists 36+ direct reads and no direct MOVX @DPTR,A writer. D180 is likely state/ingress updated through indirect or bit-addressable paths.

## XDATA 0xD8FE

nalysis/xref_xdata.py 0xD8FE finds 50+ direct reads and exactly one direct writer at ank4:E6F4. This is a strong candidate for D8FE initialization/state updates.

## bank4:E6F4 D8FE writer bytes

ank_4.bin at `0xE6F4`: 90 D8 FE F0 (MOV DPTR,#0xD8FE; MOVX @DPTR,A). Surrounding bytes: E4 90 D8 FE F0 E4 FD 7F 02 .... This is the only direct writer of D8FE in the code banks.

## bank4 D8FE access snippet

At 4:E6D4 the code reads D8FE, then at 4:E6F4 and 4:E712 writes D8FE (MOV DPTR,#0xD8FE; MOVX @DPTR,A). This localizes D8FE state updates to a small bank-4 routine.

## XDATA 0xCFD8

nalysis/xref_xdata.py 0xCFD8 finds one direct read at ank10:F801 and no direct writer. CFD8 is likely populated indirectly.

## XDATA 0xCFDA

nalysis/xref_xdata.py 0xCFDA finds 8 direct reads and no direct writer. CFDA is populated indirectly or via hardware.

## XDATA 0xCFDB

nalysis/xref_xdata.py 0xCFDB finds 18 direct reads and no direct writer. CFDB is populated indirectly or via hardware.

## XDATA 0xCFDE

nalysis/xref_xdata.py 0xCFDE finds 3 direct reads in bank 12 and no direct writer. CFDE is populated indirectly or via hardware.

## XDATA 0xFF24

nalysis/xref_xdata.py 0xFF24 finds 2 direct reads and no direct writer. FF24 is likely hardware-mapped or indirectly set.

## XDATA 0xFE88

nalysis/xref_xdata.py 0xFE88 finds one direct read at ank13:DE7B and no direct writer. FE88 is likely hardware-mapped or indirectly set.

## bank4:E678 D8FE state handling

Disassembly from 4:E678 shows a routine that reads D8FE, tests bit 0, conditionally sets bit 5, and writes D8FE at 4:E6F4 and 4:E712. It is a concrete D8FE state-update site.

## bank10:F801 CFD2/CFD8/CFDA checks

Disassembly from 10:F7F0 reads CFD2, CFD8 and CFDA, comparing against constants 0x71, 0x77 and 0xAA. This is a concrete packet-validation site.

## bank10:F23A CFDC/CFDB validation

Disassembly from 10:F220 reads CFDC into R3 and CFDB into R6, then validates against R4/R5. This is another packet-validation site.

## bank12:53FC CFDB/CFDA checks

Disassembly from 12:53FC reads CFDB and requires 0xE0, then reads CFDA and requires 0x01 before continuing. This is a packet-gate site.

## bank13:C8BF CFDA/CFDB copy

Disassembly from 13:C8BF copies CFDA to XDATA 0xC9C4 and CFDB to 0xC9C5, forwarding packet bytes to another buffer.
