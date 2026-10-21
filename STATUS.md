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
| Bank-12 caller | **Verified in bytes; input origin open** | Conditional `18:D6CE` call via shared `0:2DB2` trampoline to `12:539D`, then `12:53FC` |
| Internal buffer handoff | **Verified conditional byte path** | `13:E3BB` tests `D8FE`; `18:E22D` can copy 80 B from `CEE1` or `CF31` into `CFD8` before bank-12 dispatch |
| Dual receive slots and completion flags | **Verified in bytes** | `13:DD24` reads `FF24/FF25` for `CFD8` or `CEE1`, sets `CFD2` bit 0 conditionally; `13:DE63` reads `FE88/FE89` for `CF31`, sets bit 1 conditionally. `13:C8A4` and `18:D712` include conditional flag clearing. |
| Incoming packet framing | **Partial byte evidence; open** | Bank-13 candidate buffer length formula `(buffer[1] & 7F) + 3`; transport and checksum acceptance not established |
| Candidate incoming buffer writer | **Verified in bytes; route open** | Conditional bank-13 `CFD8` buffer, `FF24` seed, `FF25`/`FE89` feed and indirect `0:36CF` XDATA writer; its connection to the bank-18 caller is open |
| Manual joystick selection | **Open** | Actual user-event path to APCS/AOCS not demonstrated |
| Modified firmware / recovery | **Unverified** | No hardware-validated modification and no verified recovery route |

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
| `19:80A4` | Conditional state-triggered request for both |
| `CFDA..CFDF` | Shared protocol fields; usage differs by command family |

## Host-side evidence

A read-only DDC/CI probe returned a response to GET-VCP `E0` that resembled the result for `DF`. This **does not prove** an accessible vendor service command: the device does not advertise `E0`, and generic fallback behavior remains plausible. No Set-VCP or USB write tests were performed.

Firmware has several distinct paths using `CFDA`:

- Bank 18: `01/03/07/0C/F3`, DDC/CI-like path.
- Bank 7: `C0/D0`.
- Bank 10: `77/AA` when `CFD8 == 71`.
- Bank 12: `01/03` alongside `CFDB == E0`.

`CFDE` is also a numerical operand or index in other handlers. The `CFDE == 2` test alone does not identify a global service unlock.

## Research priorities

1. Trace upstream `D8FE`/`C693` state and physical ingress behind the **two identified receive register paths** (`FF24/FF25` and `FE88/FE89`) using **passive or read-only** evidence.
2. Follow physical joystick input to a **true selection event** for service actions 23/24.
3. Correlate selection, request-bit updates and the bank-18 state machine.
4. Determine verified recovery and hardware-test procedures before considering any modified firmware.

The detailed evidence and commands live in [analysis/README.md](analysis/README.md) and [analysis/panel_protection.md](analysis/panel_protection.md).

> **Safety:** OLED compensation is part of panel maintenance. Do not disable it or flash research images based only on static analysis.
