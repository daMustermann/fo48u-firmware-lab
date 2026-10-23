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

## bank7:6945 CFDA checks

Disassembly from 7:6930 sets up registers, reads CFDA, and rejects values 0xC0 and 0xD0 before continuing. This is another packet-gate site.

## bank7:6C96 CFDA check

Disassembly from 7:6C96 reads CFDA and rejects 0xD0 before continuing. This is another packet-gate site.

## bank18:D6D3 CFDA dispatch

Disassembly from 18:D6D3 reads CFDA and dispatches on 0xFD, 0xFC, 0xFB and 0x19. This is a packet-family selector site.

## bank18:7BFE CFDB read

Disassembly from 18:7BFE reads CFDB and passes it to helper 3C49. This is another packet-state consumer.

## bank18:85A4 CFDB copy

Disassembly from 18:85A4 reads CFDB and stores it at XDATA 0xCF85, forwarding packet state to another buffer.

## bank18:DBE9 CFDB dispatch

Disassembly from 18:DBE9 reads CFDB and dispatches on values derived from 0xFE, 0xFB and 0x03. This is another packet-family selector site.

## bank13:CAAF D12D bit handling

Disassembly from 13:CA98 checks R6/R7 against 0x0400, then reads D12D and sets bit 0 under a condition. This is a D12D state-update site.

## bank18:911D D180 check

Disassembly from 18:911D reads D180 and, if nonzero, calls helper 2B0C. This is a D180-dependent path.

## bank18:9298 D180 check

Disassembly from 18:9298 reads D180 and, if nonzero, calls helper FC2A. This is another D180-dependent path.

## bank18:AD42 D180 handling

Disassembly from 18:AD42 reads D180 and calls helpers FC24, FC5A, FC30, FC42 and FB0E. This is a D180-dependent output path.

## bank18:D978 D180 dispatch

Disassembly from 18:D978 reads D180 and dispatches on values 0, 1 and 2. This is a D180-dependent control path.

## bank18:E584 D180/D160 handling

Disassembly from 18:E584 tests D180; if zero it reads D160 bit 0 and continues only when D160 bit 0 is set. This is a D180/D160-dependent path.

## bank18:F35C D180 check

Disassembly from 18:F35C reads D180 and, if nonzero, calls helper FC2A. This is another D180-dependent path.

## bank18:F0A2 D180/D160 handling

Disassembly from 18:F0A2 tests D180; if nonzero it reads D160, clears bit 3, and calls 2D4C. This is a D180/D160-dependent path.

## bank18:79B9 D180 handling

Disassembly from 18:79B9 tests D180; if zero it calls E5F2 and conditionally clears bit 0. This is a D180-dependent path.

## bank18:9144 D180 handling

Disassembly from 18:9144 reads D180 and, if nonzero, calls helper 2E6C. This is another D180-dependent path.

## bank18:CA9B D180 handling

Disassembly from 18:CA9B reads D180 at 18:CA9E and calls helpers FC24, FC42, FB0E and FC4E. This is a D180-dependent output path.

## bank18:C499 D12D/D380 handling

Disassembly from 18:C499 checks D380/D381, then tests D12D bit 0. This is a D12D/D380-dependent path.

## bank15:9EE3 D8FE check

Disassembly from 15:9EE3 reads D8FE and, if nonzero, jumps to 9F8D. This is a D8FE-dependent path.

## bank15:77F4 D8FE handling

Disassembly from 15:77F4 reads D8FE and calls helper 104E, then updates XDATA 0x0043 and 0xD327. This is a D8FE-dependent output path.

## bank15:7848 D8FE check

Disassembly from 15:7848 reads D8FE and compares it to 0x10. This is a D8FE-dependent path.

## bank15:B8A7 D8FE check

Disassembly from 15:B8A7 reads D8FE and, if nonzero, jumps to B9E5. This is a D8FE-dependent path.

## bank15:B934 D8FE handling

Disassembly from 15:B934 reads D8FE and sets R7 to 0x55 if nonzero, otherwise 0x50. This is a D8FE-dependent value selection.

## bank15:B9AD D8FE handling

Disassembly from 15:B9AD reads D8FE and sets R7 to 0x55 if nonzero, otherwise 0x50. This is another D8FE-dependent value selection.

## bank15:C4D0 D8FE handling

Disassembly from 15:C4D0 reads D8FE and, if nonzero, sets R5=0x02 and calls helper 111A. This is a D8FE-dependent path.

## bank15:C54A D8FE handling

Disassembly from 15:C54A reads D8FE and, if nonzero, sets R5=0x02 and calls helper 111A. This is another D8FE-dependent path.

## bank15:D225 D8FE handling

Disassembly from 15:D225 reads D8FE and, if nonzero, sets R5=0x10 and calls helper 1D5C. This is another D8FE-dependent path.

## bank15:D265 D8FE handling

Disassembly from 15:D265 reads D8FE and, if nonzero, checks D2F1 against 0x04. This is a D8FE-dependent path.

## bank15:D64C D8FE dispatch

Disassembly from 15:D64C reads D8FE and dispatches on values derived from 0x10. This is a D8FE-dependent path.

## bank15:DE42 D8FE handling

Disassembly from 15:DE42 reads D8FE, writes it to 0x0009, then reads D2F3 and writes it to 0x000A. This is a D8FE/D2F3-dependent path.

## bank15:E8DF D8FE handling

Disassembly from 15:E8DF reads D8FE and, if nonzero, calls helper 114A and checks D2F1 against 0x02. This is a D8FE-dependent path.

## bank15:EE59 D8FE dispatch

Disassembly from 15:EE59 reads D8FE and dispatches on values derived from 0x10. This is a D8FE-dependent path.

## bank15:F4C7 D8FE dispatch

Disassembly from 15:F4C7 reads D8FE and dispatches on values derived from 0x90 and 0x50. This is a D8FE-dependent path.

## bank10:F327 D8FE dispatch

Disassembly from 10:F327 reads D8FE and dispatches on values derived from 0x20 and 0x10. This is a D8FE-dependent path.

## bank10:E16A D8FE dispatch

Disassembly from 10:E16A reads D8FE and dispatches on values derived from 0x20 and 0x10. This is a D8FE-dependent path.

## bank10:CE02 D8FE handling

Disassembly from 10:CE02 reads D8FE and sets R7 to 0x55 if nonzero, otherwise 0x50. This is a D8FE-dependent value selection.

## bank10:CDAA D8FE handling

Disassembly from 10:CDAA reads D8FE and sets R7 to 0x55 if nonzero, otherwise 0x50. This is another D8FE-dependent value selection.

## bank10:BA89 D8FE handling

Disassembly from 10:BA89 reads D8FE and returns D8FE-0x10. This is a D8FE-dependent value transform.

## bank11:9D78 D8FE handling

Disassembly from 11:9D78 reads D8FE and, if nonzero, checks bit 1 of XDATA 0x0043 before continuing. This is a D8FE-dependent path.

## bank11:A022 D8FE handling

Disassembly from 11:A022 reads D8FE and, if nonzero, jumps away; otherwise it checks bit 1 of XDATA 0x0043 before continuing. This is a D8FE-dependent path.

## bank11:BB69 D8FE handling

Disassembly from 11:BB69 reads D8FE and, if it equals 0x10, calls helper C56E. This is a D8FE-dependent path.

## bank11:E665 D8FE dispatch

Disassembly from 11:E665 reads D8FE and dispatches on values derived from 0x10. This is a D8FE-dependent path.

## bank11:FAD9 D8FE dispatch

Disassembly from 11:FAD9 reads D8FE and dispatches on values derived from 0x10 and 0x20. This is a D8FE-dependent path.

## bank12:94AF D8FE handling

Disassembly from 12:94AF reads D8FE and, if zero, jumps away; otherwise it continues to 956F. This is a D8FE-dependent path.

## bank12:999C D8FE handling

Disassembly from 12:999C reads D8FE and, if zero, jumps away; otherwise it continues to 9A5C. This is a D8FE-dependent path.

## bank12:F5B0 D8FE handling

Disassembly from 12:F5B0 reads D8FE and, if nonzero, writes 0x1D1A and calls B1F3. This is a D8FE-dependent path.

## bank12:F601 D8FE handling

Disassembly from 12:F601 reads D8FE and, if nonzero, writes 0x7A1A and calls B584. This is a D8FE-dependent path.

## bank13:CADE D12D bit check

Disassembly from 13:CADE reads D12D and tests bit 0. This is a D12D-dependent path.

## bank10:CD98 D8FE/0x006C handling

Disassembly from 10:CD98 writes and reads XDATA 0x006C, then reads D8FE. This is a D8FE/0x006C-dependent path.

## XDATA 0xD31B

nalysis/xref_xdata.py 0xD31B finds 18+ direct reads and one direct writer at ank4:A12B. D31B is a state byte with a single writer.

## bank4:A12B D31B writer

Disassembly from 4:A12B writes R7 to XDATA 0xD31B, then checks helper 1084. This is the sole direct writer of D31B.

## bank10:C50E 0x0043 writer

Disassembly from 10:C50E calls helper BD4C and writes the result to XDATA 0x0043. This is the sole direct writer of 0x0043.

## bank10:CD98 0x006C update

Disassembly from 10:CD98 reads 0x006C, clears bit 0, ORs R7, and writes it back. This is a 0x006C state-update site.

## bank13:C8C3 0xC9C4/0xC9C5 copy

Disassembly from 13:C8C3 copies CFDA to 0xC9C4 and CFDB to 0xC9C5. This is a packet-forwarding site.

## bank13:C953 CFDB copy to 0xCF85

Disassembly from 13:C953 reads CFDB and writes it to XDATA 0xCF85. This is a packet-forwarding site.

## bank13:C961 0xCF89 write

Disassembly from 13:C961 writes R7 to XDATA 0xCF89, then reads 0xCFD1. This is a 0xCF89 state-update site.

## bank13:C976 0xCF85/0xCF89 handling

Disassembly from 13:C976 reads 0xCF85 and XORs it with 0xB4, then reads 0xCF89 and XORs it with 0x6F. This is a 0xCF85/0xCF89-dependent path.

## bank13:C971 0xCF8A write

Disassembly from 13:C971 writes R7 to XDATA 0xCF8A. This is a 0xCF8A state-update site.

## bank12:5951 0xCF8B write

Disassembly from 12:5951 writes 0 or 0x04 to XDATA 0xCF8B depending on D142. This is a 0xCF8B state-update site.

## bank12:5968 0xCF8C write

Disassembly from 12:5968 writes 0, 1 or 2 to XDATA 0xCF8C depending on D142. This is a 0xCF8C state-update site.

## bank12:5987 0xCF8D write

Disassembly from 12:5987 writes a value derived from D125 to XDATA 0xCF8D. This is a 0xCF8D state-update site.

## bank12:5992 0xCF8E write

Disassembly from 12:5992 writes D127 & 0x1F to XDATA 0xCF8E. This is a 0xCF8E state-update site.

## bank12:599A 0xCF8F write

Disassembly from 12:599A writes D127 to XDATA 0xCF8F. This is a 0xCF8F state-update site.

## bank12:59A4 0xCF90 write

Disassembly from 12:59A4 writes D129 & 0x01 to XDATA 0xCF90. This is a 0xCF90 state-update site.

## bank12:59AC 0xCF91 write

Disassembly from 12:59AC writes D129 to XDATA 0xCF91. This is a 0xCF91 state-update site.

## bank12:59BB 0xCF93 write

Disassembly from 12:59BB writes D128 to XDATA 0xCF93. This is a 0xCF93 state-update site.

## bank12:59C6 0xCF95 write

Disassembly from 12:59C6 writes R7 to XDATA 0xCF95. This is a 0xCF95 state-update site.

## bank12:59CE 0xCF96 write

Disassembly from 12:59CE writes a value to XDATA 0xCF96 after testing D141. This is a 0xCF96 state-update site.

## bank12:59DA 0xCF97 write

Disassembly from 12:59DA writes 0 or 1 to XDATA 0xCF97 depending on D141. This is a 0xCF97 state-update site.

## bank12:59EC 0xCF98 write

Disassembly from 12:59EC writes D129 & 0x01 to XDATA 0xCF98. This is a 0xCF98 state-update site.

## bank12:5B11 0xCF99 write

Disassembly from 12:5B11 writes D134 & 0x01 to XDATA 0xCF99. This is a 0xCF99 state-update site.

## bank12:59FC 0xCF9A write

Disassembly from 12:59FC writes a derived value to XDATA 0xCF9A. This is a 0xCF9A state-update site.

## bank12:5A24 0xCFA0 write

Disassembly from 12:5A24 writes R7 to XDATA 0xCFA0. This is a 0xCFA0 state-update site.

## bank7:7CE5 0xCFB8 write

Disassembly from 7:7CE5 writes R7 to XDATA 0xCFB8 when CFDB != 0x74. This is a 0xCFB8 state-update site.

## bank7:7CD3 0xCFC8 write

Disassembly from 7:7CD3 writes R7 to XDATA 0xCFC8 when CFDE != 0x40. This is a 0xCFC8 state-update site.

## bank18:E277 0xCFD1 write

Disassembly from 18:E277 writes 0x50 to XDATA 0xCFD1. This is a 0xCFD1 state-update site.

## bank18:D729 0xCFD2 write

Disassembly from 18:D729 writes a derived value to XDATA 0xCFD2. This is a 0xCFD2 state-update site.

## bank7:A938 0xCFD3 write

Disassembly from 7:A938 writes 0 to XDATA 0xCFD3. This is a 0xCFD3 state-update site.

## bank13:E3AD 0xCFD4 write

Disassembly from 13:E3AD writes 0 to XDATA 0xCFD4 under a condition. This is a 0xCFD4 state-update site.

## bank13:EAF6 0xCFD5 write

Disassembly from 13:EAF6 writes 0 to XDATA 0xCFD5 under a condition. This is a 0xCFD5 state-update site.

## XDATA 0xCFD6

nalysis/xref_xdata.py 0xCFD6 finds 6 direct reads and no direct writer. CFD6 is likely populated indirectly or via hardware.

## bank0:FC1F 0xCFD7 write

Disassembly from 0:FC1F writes 0 to XDATA 0xCFD7. This is a 0xCFD7 state-update site.

## XDATA 0xCFD9

nalysis/xref_xdata.py 0xCFD9 finds 3 direct reads and no direct writer. CFD9 is likely populated indirectly or via hardware.

## XDATA 0xCFDC

nalysis/xref_xdata.py 0xCFDC finds 18+ direct reads and no direct writer. CFDC is likely populated indirectly or via hardware.

## XDATA 0xCFDD

nalysis/xref_xdata.py 0xCFDD finds 18+ direct reads and no direct writer. CFDD is likely populated indirectly or via hardware.

## XDATA 0xCFDF

nalysis/xref_xdata.py 0xCFDF finds 18+ direct reads and no direct writer. CFDF is likely populated indirectly or via hardware.

## XDATA 0xCFE0

nalysis/xref_xdata.py 0xCFE0 finds one direct read and no direct writer. CFE0 is likely populated indirectly or via hardware.

## XDATA 0xCFE1

nalysis/xref_xdata.py 0xCFE1 finds 2 direct reads and no direct writer. CFE1 is likely populated indirectly or via hardware.

## XDATA 0xD12D (indexed scan)

nalysis/xref_xdata.py 0xD12D --include-indexed finds 19 direct reads and no direct or indexed writer. D12D is likely hardware-mapped or updated through bit-addressable operations.

## ISR IE0 (0:510F) D8F9 handling

Disassembly from 0:510F reads D8F9 and dispatches on values 0x03 and 0x01, calling helpers at 0EBC/0EC2. This is an ISR-side D8F9 path.

## ISR IE1 (0:520B) FFF4 handling

Disassembly from 0:520B reads FFF4, writes it to C9C1, and calls helpers at 0ED4/0EDA/0EE0/0EE6. This is an ISR-side path.

## ISR TF2 (0:508A) FFF4 handling

Disassembly from 0:508A reads FFF4, writes it to C9C7, clears TF2, and updates FFEB/FFEA. This is an ISR-side path.

## ISR TF0 (0:5246) FFF4 handling

Disassembly from 0:5246 reads FFF4 and writes it back. This is a Timer0 ISR-side path.

## XDATA 0xFFEB

nalysis/xref_xdata.py 0xFFEB finds 20+ direct reads across all banks and no direct writer. FFEB is likely hardware-mapped or updated through indirect paths.

## XDATA 0xFFEA

nalysis/xref_xdata.py 0xFFEA finds 18+ direct reads and no direct writer. FFEA is likely hardware-mapped or updated through indirect paths.

## XDATA 0xFFED

nalysis/xref_xdata.py 0xFFED finds 10+ direct reads and no direct writer. FFED is likely hardware-mapped or updated through indirect paths.

## XDATA 0xFFEE

nalysis/xref_xdata.py 0xFFEE finds 2 direct reads and no direct writer. FFEE is likely hardware-mapped or updated through indirect paths.

## bank6:D17C 0xFFF0 write

Disassembly from 6:D17C calls helper BB6C and writes the result to XDATA 0xFFF0. This is a 0xFFF0 state-update site.

## bank3:DA07 FFF1 handling

Disassembly from 3:DA07 reads FFF1 and copies it to 0xC6CA, then checks 0xC6C9. This is an FFF1-dependent path.

## bank0:ACF4 FFF2 handling

Disassembly from 0:ACF4 reads FFF2 and sets bits 0-5. This is an FFF2-dependent path.

## bank8:DD93 FFF3 write

Disassembly from 8:DD93 writes 0x10 to XDATA 0xFFF3 when 0xC704 is nonzero. This is a FFF3 state-update site.

## bank0:4470 FFF4 write

Disassembly from 0:4470 reads D618 and writes it to FFF4. This is a FFF4 state-update site.

## bank8:DD3D FFF6 write

Disassembly from 8:DD3D writes C701 to XDATA 0xFFF6. This is a FFF6 state-update site.

## bank18:BE86 0xFFF8 write

Disassembly from 18:BE86 calls helper 3681 and writes the result to XDATA 0xFFF8. This is a 0xFFF8 state-update site.

## bank8:DD67 FFFB write

Disassembly from 8:DD67 writes 0, 2 or 3 to XDATA 0xFFFB depending on C706. This is a FFFB state-update site.

## XDATA 0xFFFC

nalysis/xref_xdata.py 0xFFFC finds 3 direct reads and no direct writer. FFFC is likely populated indirectly or via hardware.

## bank19:8416 0xFFFD write

Disassembly from 19:8416 writes 0 to XDATA 0xFFFD. This is a 0xFFFD state-update site.

## XDATA 0xFFFF

nalysis/xref_xdata.py 0xFFFF finds many direct reads and no direct writer. FFFF is likely hardware-mapped or updated through indirect paths.

## bank0:FDB2 0xFFEC write

Disassembly from 0:FDB2 writes 0x94 or 0xFC to XDATA 0xFFEC depending on A. This is a 0xFFEC state-update site.

## XDATA 0xFFE9

nalysis/xref_xdata.py 0xFFE9 finds 6 direct reads and no direct writer. FFE9 is likely hardware-mapped or updated through indirect paths.

## bank6:D1A2 0xFFE8 write

Disassembly from 6:D1A2 calls helper BB6C and writes the result to XDATA 0xFFE8. This is a 0xFFE8 state-update site.

## XDATA 0xFFE7

nalysis/xref_xdata.py 0xFFE7 finds 12 direct reads and no direct writer. FFE7 is likely hardware-mapped or updated through indirect paths.

## bank1:EAB9 FFE5 write

Disassembly from 1:EAB9 writes 0 to XDATA 0xFFE5. This is a FFE5 state-update site.
