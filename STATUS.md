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
| Incoming packet framing | **Open** | Physical packet source of `CFDA..CFDF` not established |
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

1. Trace the physical ingress that fills `CFDA..CFDF` and establish frame boundaries using **passive or read-only** evidence.
2. Follow physical joystick input to a **true selection event** for service actions 23/24.
3. Correlate selection, request-bit updates and the bank-18 state machine.
4. Determine verified recovery and hardware-test procedures before considering any modified firmware.

The detailed evidence and commands live in [analysis/README.md](analysis/README.md) and [analysis/panel_protection.md](analysis/panel_protection.md).

> **Safety:** OLED compensation is part of panel maintenance. Do not disable it or flash research images based only on static analysis.
