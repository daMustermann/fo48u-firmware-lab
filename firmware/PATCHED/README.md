# Patched FO48U firmware (experimental)

These images are **unofficial modifications** of
`FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` (MD5
`d4324c6c88abea48b1ee896f7e14ee9f`).

> **Status: static analysis only. None of these variants has been flashed on
> hardware.**
>
> Flashing modified firmware can brick the monitor. Keep the original image,
> use a sacrificial unit if possible, and do not interrupt power during a
> flash. If you are not comfortable recovering a dead monitor, do not flash
> these files.

---

## Variants

| File | MD5 | Changes |
|---|---|---|
| `F08-unlock.bin` | `c94cf874324c9cf0f76e38f5b22308b1` | Removes the `0xCFDE == 2` gate in front of the APCS/AOCS command entries (bank 12 `0x68AD` and `0x68BD`). Schedule unchanged. |
| `F08-care.bin` | `741ae5c02f5362304ed1df728daa48f3` | `F08-unlock` plus APCS every 2 h, AOCS every 750 h, and the panel-care reminder after 12 h. |

Both are 2,031,616 bytes (31 × 64 KiB banks), the same size as the original.

---

## What the patches actually do

### `unlock_cmd_gate` (both variants)

The cleanest "request a refresh" code in the firmware is bank 12
`0x68A9` (APCS) and `0x68B9` (AOCS). Both entries begin by re-checking a
command variable:

```
0x68A9  mov  dptr, #0xCFDE
0x68AC  movx a, @dptr
0x68AD  xrl  a, #2
0x68AF  jnz  0x68D4          ; bail out unless 0xCFDE == 2
0x68B1  mov  dptr, #0xD12D
0x68B4  movx a, @dptr
0x68B5  orl  a, #1           ; request APCS
...
0x68B9  mov  dptr, #0xCFDE
0x68BC  movx a, @dptr
0x68BD  cjne a, #2, 0x68D4   ; bail out unless 0xCFDE == 2
0x68C0  mov  dptr, #0xD12D
0x68C3  movx a, @dptr
0x68C4  orl  a, #2           ; request AOCS
```

The patch replaces the two checks with `clr a` + `nop` padding, so the
request is always made when the entry is reached:

| Site | Original | Patched |
|---|---|---|
| bank 12 `0x68AD` | `64 02` (`xrl a,#2`) | `E4 00` (`clr a; nop`) |
| bank 12 `0x68BD` | `B4 02 14` (`cjne a,#2,0x68D4`) | `E4 00 00` (`clr a; nop; nop`) |

The entry is still only reached by whatever command/case selects it; the patch
does **not** add a new menu item or a new key. The hypothesis is that the
service-menu APCS/AOCS actions reach these entries but were inert because
`0xCFDE` is not `2` in normal mode. That is **not yet proven**.

### `apcs_2h` (`F08-care` only)

Bank 13 `0xCAA8`: `94 04` (`subb a,#4`) → `94 02` (`subb a,#2`).
APCS runs every 2 h of panel usage instead of every 4 h.

### `aocs_750h` (`F08-care` only)

Bank 13 `0xCAD3`: `7C 05 7D DC` (1500) → `7C 02 7D EE` (750).
AOCS runs every 750 h instead of every 1500 h.

### `tss_12h` (`F08-care` only)

Bank 13 `0xCB1A`: `94 24` (`subb a,#0x24`) → `94 0C` (`subb a,#0x0C`).
The "time to screen saver"/panel-care reminder appears after 12 h instead of
36 h.

---

## How they were built

```powershell
python analysis/build_variant.py --verify   # check every site against the original
python analysis/build_variant.py            # rebuild all variants + MANIFEST.md
```

The builder refuses to run if the source size or MD5 is wrong, or if any patch
site does not contain the expected original bytes. The diff is limited to the
bytes listed above; everything else is byte-identical to the original.

---

## Flashing

Use the same procedure and OSD Sidekick version as for the original image
(see the main README, "How to Update Firmware"). In short:

1. Verify the original image MD5 is `d4324c6c88abea48b1ee896f7e14ee9f`.
2. Verify the variant MD5 against the table above.
3. Flash over a **USB 2.0** port with OSD Sidekick `B21.0707.1`.
4. Do not power off or unplug during the flash.
5. After the first boot, check the OSD and the panel-protection behaviour
   before relying on the monitor.

The updater may reject a file whose name/version does not match what it
expects. If that happens, **do not rename or hex-edit the file further** —
report it instead. The exact acceptance rules of the updater have not been
reverse-engineered.

---

## Recovery

There is **no verified recovery path** for a failed flash on this model in this
repository. Before flashing:

- keep the original `.bin` and its MD5 on a second device;
- note the monitor's current firmware version and OSD Sidekick version;
- make sure you can reach the service menu and the firmware update screen.

If the monitor does not come back after a flash, the practical options are the
vendor service path or a hardware flash of the SPI part. Do not assume the
bootloader will accept a re-flash over USB after a corrupted image.

---

## Why this is not marked "working"

- The `0xCFDE == 2` gate is confirmed to exist, but it has not been confirmed
  that the service-menu APCS/AOCS actions are the caller that hits it.
- The APCS/AOCS completion path has a known flag bug in the original firmware;
  running the routines more often may make that bug more visible.
- No hardware validation of any kind has been done.
- The updater's acceptance/verification rules are unknown.

Treat these images as a **reproducible starting point for testing**, not as a
finished product.
