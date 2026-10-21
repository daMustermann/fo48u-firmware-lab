# OLED panel care: APCS, AOCS and TSS

Bank-relative locations and XDATA addresses from the hash-identified **FO48U F08 / 2022-11-15** image. These are **static-code observations**, not proof of physical panel behavior.

[Main guide](../README.md) · [Analysis map](README.md) · [Current status](../STATUS.md)

## Scheduler in bank 13

The shared scheduling logic is near `13:CA4E..CB60`.

| Mechanism | Decision site | Stock constant | Observed effect |
| :-- | :-- | :-- | :-- |
| APCS | `13:CAA8` | `94 04` | Request after 4 elapsed panel-use hours since last APCS |
| AOCS | `13:CAD3` | `7C 05 7D DC` | Periodic 1500-hour condition |
| TSS | `13:CB1A` | `94 24` | Reminder threshold after 36 hours since last APCS |

The firmware tracks accumulated panel use. The timers have different purposes: **APCS and AOCS are compensation requests; TSS is reminder logic**. An 8-bit threshold of 255 hours is a finite maximum, not proof of a disable state.

## XDATA state

| XDATA | Role established in code |
| :-- | :-- |
| `D13D:D13E` | Panel usage, hours, big-endian |
| `D13F` | Minute subcounter (0–59) |
| `D12E:D12F` | Last-APCS hour reference, big-endian |
| `D12D` | Request flags: **bit 0 APCS**, **bit 1 AOCS** |
| `D131` / `D130` | APCS / AOCS completion counters |
| `D380:D381` | APCS runtime counter |
| `D385` | TSS popup minute slot |
| `D35B` | Popup suppression bits |
| `D64E` | Panel-care / OSD state bits; full meaning unresolved |
| `CFDE` | Shared command operand, used by the bank-12 entries |

APCS requests set `D12D |= 01` near `13:CAB7`; AOCS requests set `D12D |= 02` near `13:CAE9`. Runtime state handling and completion live in **bank 18**.

## Request consumers and completion

The bank-18 consumers near `92BC` (APCS) and `92F1` (AOCS) read `D12D`, while other conditions determine whether and when work proceeds.

The APCS completion helper at `18:E5BD` clears the APCS request, stores an updated reference hour and increments the APCS completion counter. The AOCS path may also reach this helper. This indicates **shared bookkeeping behavior**, but its observable effects on the monitor or any reminder popup are **not verified**. The AOCS code also contains a path clearing its own request bit near `18:C4E4`.

Do not interpret the flag bits as safe writeable user controls. Their execution context, prerequisites and recovery behavior matter.

## Other request paths

**Bank 12 commands.** A table around `12:5D85..5EB0` selects handler `68A9` for command `80` (APCS) and `68B9` for `82` (AOCS). The surrounding handler checks `CFDB = E0` and a command-family value in `CFDA`. Each refresh handler requires operand **`CFDE == 2`**. This is not evidence of a global service-mode enable.

**Bank 19 state transition.** A conditional path around `19:80A4` may set both `D12D` bits when `C501 == 0x20`. Its precursor state from `D8B3` and subsequent checks have not been connected to a genuine external USB command.

**Bank 9 service menu.** Action IDs 23 and 24 call `9:A14C` and `9:A1C0`. A common enumerator at `9:D516` can call those handlers without a proven key event. Their `0BAD/0BAE` state bits are distinct from the actual `D12D` requests. The call route through `9:E0E2` cannot receive IDs 23/24 because `9:E057` is directly called with IDs 11/14.

## Useful byte anchors

| Bank:address | Original bytes | Meaning |
| :-- | :-- | :-- |
| `13:CAA8` | `94 04` | APCS interval comparison |
| `13:CAD3` | `7C 05 7D DC` | AOCS period constant |
| `13:CB1A` | `94 24` | TSS threshold |
| `13:CAB7` | `44 01` | APCS request-bit OR |
| `13:CAE9` | `44 02` | AOCS request-bit OR |
| `12:68AD` | `64 02` | APCS command operand check |
| `12:68BD` | `B4 02 14` | AOCS command operand check |

For file offset conversion: `bank * 0x10000 + address`. Bank switching is performed via the common routine at `0x6000` with target bank in `R7`; XDATA `FFFF` is the selector.

## Reproducibility and remaining questions

```bash
python analysis/audit_refresh_command_table.py
python analysis/audit_menu_reachability.py
python analysis/audit_service_dispatch.py
python analysis/audit_packet_field_usage.py
python analysis/audit_packet_route_families.py
```

The evidence still needs a physical joystick selection trace, the packet ingress that fills `CFDA..CFDF`, and a proven safety/recovery approach. **No modified image is validated for flashing.** The automatic care functions should remain enabled.
