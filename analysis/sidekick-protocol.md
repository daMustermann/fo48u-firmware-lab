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
python -B analysis/audit_sidekick_commands.py 'C:\Program Files (x86)\Gigabyte\OSDSidekick\AORUS\osdsidekick.exe'
```

## Relationship to F08 firmware

Stock F08 bank 12 maps incoming command codes `80` and `82` to `12:68A9` and `12:68B9`, which conditionally set the APCS/AOCS request bits in XDATA `D12D` when operand `CFDE == 2`. These command codes align with the Sidekick payloads, but a complete **USB/HID → hardware receiver → firmware buffer → bank-12 handler** path has not yet been proven. In particular, no successful manual compensation cycle or safe host-trigger procedure has been demonstrated.

Research remains confined to official application inspection, offline firmware audits and passive observations. See [firmware anatomy](README.md) and [current status](../STATUS.md).
