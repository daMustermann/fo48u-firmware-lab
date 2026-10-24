# Sidekick host bank verification

This is static analysis and isolated CPU emulation, **not a flash test**.
The installed `RFlash.dll` has SHA-256
`09586d4b2cfd5d80b20ad3bf2ee2b01fd080260f0753e83c8ec32eaf3b0ec652`.
The vendor DLL is not redistributed here. The package `UpdPack.cab` was listed
with 7-Zip: it carries an InstallShield `OSDSidekick/setup.exe`; listing that
executable exposes a large `[0]` overlay rather than individual DLLs. The DLL
analysis below is bound to the installed file hash, not an asserted extraction
match against that overlay.

## Exact host verification algorithm

`RFlash.dll!fnNewFlashBIOS` at `0x10002AB0` loads the input file and obtains the
number of complete 64 KiB banks (`size >> 16`, `0x10002B13`). In the per-bank
loop, `0x10002CDF` prepares the bank buffer, `0x10002CE4` calls `0x10002540`,
and `0x10002CF8` calls `0x10002020` with the bank base address. The comparison
`CMP BL,AL` at `0x10002CFD` compares software and device results; mismatch takes
the error-6 path at `0x10002D7E`.

`0x10002540..0x1000272F` (file offset `0x1940`, 496 bytes, SHA-256
`d97be5736c67e3a0e87cb749fe0d115941fb7dea5d8be2a10c68d3313920d686`)
implements **CRC-8, polynomial 0x07, init 0x00, no reflection, xorout 0x00**.
It starts eight state bits at zero and iterates exactly `0x10000` bytes from
`0x1003E2F8`. The fully expanded bit equations are equivalent to processing each
byte MSB first through polynomial `x^8 + x^2 + x + 1`.

`0x10002020` writes start/end address registers at I2C slave `0x94`, with the
inclusive end equal to start+`0xFFFF`; it starts the CRC engine using register
`0x6F` bit 2, polls completion, then reads one result byte from register `0x75`
at `0x100021A6`. These operations were inspected only; **none were sent**.

`analysis/verify_patch_safety.py:bank_crc8` implements the exact host calculator
and prints stock/patched per-bank CRCs. It never repairs or appends a footer.
Every one of the 31 stock banks has `FF FF` at offsets `FFFE..FFFF`; those
bytes are included in this CRC, not established stored checksum words.

## Independent checks

The actual vendor routine was run in an isolated Unicorn x86 emulator with
synthetic RAM, not loaded as a native library. The image was mapped into the
emulator and only the MSVC security-cookie check was replaced with RET in
emulated memory. No DLL/device APIs were executed. Its result matched the Python
calculator for:

| 65,536-byte input | CRC-8 |
|---|---|
| All zeroes | 00 |
| Bytes 00..FF repeated 256 times | 17 |
| Hash-verified F08 bank 12 | 4F |

Reproduce the Python side with the offline controller test suite. Independently
inspect the proprietary DLL, when available, using radare2:

```powershell
r2 -q -e scr.color=0 -c 'pD 496 @ 0x10002540;q' RFlash.dll
r2 -q -e scr.color=0 -c 'pD 740 @ 0x10002B57;q' RFlash.dll
```

The optional `analysis/verify_native_crc.py` reproduces the isolated native
comparison when `dnfile` and `unicorn` are available:

```powershell
python analysis/verify_native_crc.py 'C:\Program Files (x86)\Gigabyte\OSDSidekick\AORUS\RFlash.dll'
```

It refuses a different DLL/function hash and requires return to the emulated
sentinel, so a timeout cannot be mistaken for successful verification.

The official `osdsidekick.exe` was also inspected through REA metadata/CIL
Evidence `ev_96aae07c82c1a89a54d8ca8a76f4b20c601963a7cc96a9534d38fc76af3420ea`,
SHA-256 `a384156924593d88d6c32c141db5b6858923a927ac82971858888a719e42dac0`,
MVID `6a7c5d46-aaeb-42ea-bd1e-69e5035c8d58`.
`check_monitor_fw_correct` (token `06000274`) checks embedded model strings.
The method name alone would be misleading evidence of a whole-image checksum.
Likewise `RtHIDLib!HID_verifyupdatefw` forwards to `HID_ispauthentication` and
does not itself calculate an image CRC.

## Limits

This establishes one installed host flash/readback verification path. It does
not establish all scaler ROM/bootloader authentication, boot-time checks,
hardware address mappings, bank-offset configuration or a recovery procedure.
Those remain release blockers; neither matching CRC nor valid instructions
make a modified image flash-safe. No F06 firmware image was available for static
comparison.
