# OSD Sidekick: OLED maintenance commands

The installed official **OSD Sidekick 1.21.0707.1** exposes APCS and AOCS actions in `GOSD.OLEDSet`. The executable inspected on 2026-10-21 has SHA-256 `a384156924593d88d6c32c141db5b6858923a927ac82971858888a719e42dac0`. This analysis covers that executable and the hash-identified stock F08 image only.

## Byte-verified commands

| UI action | Realtek HID payload prefix | Alternative USB payload |
| :-- | :-- | :-- |
| Execute APCS | `51 85 03 E0 80 00 02 B5` | `6E 51 84 03 E0 80 02` |
| Execute AOCS | `51 85 03 E0 82 00 02 B7` | `6E 51 84 03 E0 82 02` |

Both click handlers call `GOSD.OLEDSet.SetOSD(3, ...)`. Their original IL is located at file offsets `0x2A34` (APCS, token `06000083`, RVA `0x4834`) and `0x2A70` (AOCS, token `06000084`, RVA `0x4870`); `SetOSD` uses token `06000082`, RVA `0x4654`. These method bodies, native imports and the command bytes were independently checked against the executable. The Realtek payload is passed as a zero-padded **32-byte** buffer to `RtHIDLib.dll!HID_i2cwrite(buffer, 32, 0x6E, 0)`; its final byte is an XOR checksum. The alternative `GUSB.dll` route uses `G_usb_control_msg(dev, 0x40, 0xB2, 0, 0, buffer, 7, 1000)`.

The program maps **FO48U** to monitor identifier **GBT4800** and its Realtek HID branch, which searches VID `0x0BDA`, PID `0x1100`. This is evidence of the program's intended device selection, subject to independent hardware-endpoint attribution.

Windows also enumerates a present `HID\VID_0BDA&PID_1100` device, with vendor-defined usage `FFDA/00DA` and the Microsoft `HidUsb` driver, downstream of a Realtek `0BDA:5411` USB hub. The Sidekick native DLL explicitly checks VID/PID using `HidD_GetAttributes` and SetupAPI. The final live `CreateFile` handle connecting this specific interface to the observed Sidekick traffic has not yet been captured. The display's `DISPLAY\GBT4800` EDID instance does not independently prove the USB path.

## Readback selectors

`GetOSD(2, ...)` uses `E0 7F` for panel hours, `E0 80` for APCS status, `E0 81` for APCS count, `E0 82` for AOCS status, and `E0 83` for AOCS count. The Realtek query has prefix `51 83 01 E0 XX XOR`, padded to 36 bytes and followed by `HID_i2cread(0x51, 1, buffer, 36, 0x6E, 0, 100)`.

A passive trace of the connected Sidekick process captured the native **query**, `HID_i2cwrite(..., 36, 0x6E, 0)`, with bytes `51 83 01 E0 50 63`, followed by `HID_i2cread(0x51, 1, ..., 36, 0x6E, 0, 100)` and HID output/input-report calls. The capture confirms this host-side transport is actively used; it did **not** establish the returned panel bytes or observe an APCS/AOCS execution command. It also does not independently identify the physical HID interface that handled the query.

One UI caveat: `APCS_EXE_Click` checks `AOCS_exe == 1` (as does `AOCS_EXE_Click`). The reason for the shared gate, and its effect on actual execution, remain unverified.

To reproduce the method-byte audit with your own official installed executable (no hardware access):

```powershell
python -B analysis/verify_facts.py 'C:\Program Files (x86)\Gigabyte\OSDSidekick\AORUS\osdsidekick.exe'
```

## Relationship to F08 firmware

Stock F08 bank 12 maps incoming command codes `80` and `82` to `12:68A9` and `12:68B9`, which conditionally set the APCS/AOCS request bits in XDATA `D12D` when operand `CFDE == 2`. These command codes align with the Sidekick payloads, but a complete **USB/HID → hardware receiver → firmware buffer → bank-12 handler** path has not yet been proven. In particular, no successful manual compensation cycle or safe host-trigger procedure has been demonstrated.

The Sidekick reference frames have **eight bytes** each, exactly matching the stock bank-13 candidate receive-length rule `(frame[1] & 0x7F) + 3` for byte `85`. **If** the frame arrives intact with its first byte at `CFD8`, offsets `2..6` would populate the five downstream fields `CFDA..CFDE` as `03 E0 80 00 02` (APCS), or `03 E0 82 00 02` (AOCS). This is a **conditional buffer-placement match**, not an observed receive event. Firmware bytes further establish the `E0` path through the bank-13 predicate, the bank-7 `CFDA=03` carry-clear return, and bank-12's `80`/`82` dispatch and `CFDE=02` guard. The exact candidate control-flow anchors and reference-frame XOR are reproducible with `python -B analysis/verify_facts.py`.

The physical USB bridge → `FF24/FF25` or `FE88/FE89` mapping, incoming checksum acceptance, relevant live state and successful panel compensation remain unverified.

Research remains confined to official application inspection, offline firmware audits and passive observations. See [firmware anatomy](README.md) and [current status](../STATUS.md).

## Decompiled control flow (AORUS `osdsidekick.exe`)

`Window_Loaded` calls `GetAPCS_Enable()` (selector `E0 80`) and `GetAOCS_Enable()` (selector `E0 82`), storing the results in `APCS_exe` and `AOCS_exe`. Both `APCS_EXE_Click` and `AOCS_EXE_Click` return immediately unless `AOCS_exe == 1`; otherwise they call `SetOSD(3, [E0, 80/82, 02])`.

Readback selectors used by the UI:

| Method | Selector bytes | Response value |
| :-- | :-- | :-- |
| `GetPanel_Time` | `E0 7F` | panel hours |
| `GetAPCS_Time` | `E0 81` | APCS elapsed time |
| `GetAOCS_Time` | `E0 83` | AOCS elapsed time |
| `GetAPCS_Enable` | `E0 80` | APCS enable/status |
| `GetAOCS_Enable` | `E0 82` | AOCS enable/status |

`GetOSD` sends a Realtek-HID query frame `51 83 01 E0 <selector> <xor>` padded to 36 bytes, sleeps, calls `HID_i2cread(0x51, 1, buffer, 36, 0x6E, 0, 100)`, and decodes the returned uint16 from response bytes 8 and 9 (big-endian). If the Realtek device is absent it falls back to the `GUSB.dll` route: write `6E 51 84 03 E0 <selector> 01 <xor>` (7 bytes) with `G_usb_control_msg(dev, 0x40, 0xB2, 0, 0, buffer, 7, 1000)`, then read 12 bytes with request type `0xC0`, request `0xA2`, index `0x6F`.

`SetOSD` execution buffers:

- Realtek: `51 85 03 E0 <selector> 00 02 <xor>` (8 bytes), padded to 32 bytes, sent with `HID_i2cwrite(buffer, 32, 0x6E, 0)`.
- USB: `6E 51 84 03 E0 <selector> 02` (7 bytes), sent with `G_usb_control_msg(dev, 0x40, 0xB2, 0, 0, buffer, 7, 1000)`.

Device selection uses VID `0x0BDA`, PID `0x1100` via `Get_mutiHID`/`Open_mutiHID`; the USB path operates on the `dev` handle obtained elsewhere in `MainWindow`.

## Verified host-side readback

The controller in controller/ successfully reads panel hours using the documented 51 83 01 E0 7F query frame and decodes response bytes 8/9. This confirms the transport and frame layout on at least one FO48U unit; execution commands remain unverified.


## Hardware crosshair

Crosshair_Click builds a 3-byte frame E0 55 <index> and sends it through the same SetOSD path. Realtek-HID execution form: 51 85 03 E0 55 00 <index> <xor> (padded to 32 bytes). The controller exposes this as OledCare.set_crosshair(index).


## Hardware-verified execution

On 2026-10-22, the controller's APCS trigger (51 85 03 E0 80 00 02 B5) was executed successfully on a real FO48U. This confirms the host-to-firmware APCS path for that device and image; AOCS and other commands remain to be validated per device.

## Observed DDC/CI readout (FO48U)

Read-only dump from the controller (2026-10-22):

- VCP 0x02=1/2, 0x04=0/1, 0x05=0/1, 0x06=0/1, 0x08=0/1, 0x0B=100/0, 0x0C=45/63, 0x10=50/100, 0x12=50/100, 0x14=6/11, 0x16=128/100, 0x18=122/100, 0x1A=107/100, 0x1E=0/1, 0x20=0/1, 0x30=0/1, 0x52=0/1, 0x60=15/3, 0x62=30/100, 0x6C=50/100, 0x6E=50/100, 0x70=50/100, 0x86=2/0, 0x87=5/10, 0xAC=4/59900, 0xAE=6040/65535, 0xB2=1/1, 0xB6=3/5, 0xC6=90/255, 0xC8=9/0, 0xC9=1/65535, 0xCA=1/2, 0xCC=4/13, 0xD6=1/5, 0xDF=514/65535, 0xE0=514/65535, 0xEC=0/0.

