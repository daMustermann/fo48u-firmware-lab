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
| `F08-quiet.bin` | `15eb5100dd3404a29e58152422808cd6` | `F08-unlock` plus APCS every 36 h, matching the public F08b popup fix (fewer interruptions). |
| `F08-menu.bin` | `fcab11e12a855fe7d7f3622b7b38410e` | `F08-unlock` plus the **service-menu action patch**: selecting **APCS** or **AOCS** now sets the real `0xD12D` request bit before the stock handler runs. Stock schedule. |
| `F08-menu-quiet.bin` | `b9716bc3c916492909503d7f5586343e` | `F08-menu` plus APCS every 36 h (the F08b popup interval). |
| `F08-menu-no-nag.bin` | `1034a9dcc86f19dc1ae3ab35ef88c040` | `F08-menu-quiet` plus the 36 h panel-care reminder disabled (`0xFF`). Least intrusive profile. |
| `F08-menu-care.bin` | `fdb1a011dfed7b3fed2f0df9f3d666e7` | `F08-menu` plus APCS every 8 h, AOCS every 750 h, reminder after 12 h. Aggressive care profile. |

All variants are 2,031,616 bytes (31 × 64 KiB banks), the same size as the
original.

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

### `apcs_36h` (`F08-quiet` only)

Bank 13 `0xCAA8`: `94 04` (`subb a,#4`) → `94 24` (`subb a,#0x24`).
APCS runs every 36 h of panel usage instead of every 4 h. This is the same
popup interval as the public F08b build: far fewer interruptions, at the cost
of less frequent automatic refresh.

### `aocs_750h` (`F08-care` only)

Bank 13 `0xCAD3`: `7C 05 7D DC` (1500) → `7C 02 7D EE` (750).
AOCS runs every 750 h instead of every 1500 h.

### `tss_12h` (`F08-care` only)

Bank 13 `0xCB1A`: `94 24` (`subb a,#0x24`) → `94 0C` (`subb a,#0x0C`).
The "time to screen saver"/panel-care reminder appears after 12 h instead of
36 h.

### `menu-actions` (all `F08-menu-*` variants)

The stock service menu already shows **APCS** (item 23, handler `0xA14C`) and
**AOCS** (item 24, handler `0xA1C0`). Those handlers have two paths:

- `R5 == 0` — draw/status path, left untouched;
- `R5 != 0` — key path, which toggles internal test bits (`0x0BAD` / `0x0BAE`)
  but does **not** set the real request flag `0xD12D`.

The patch redirects only the key path through a 14-byte trampoline in erased
bank-9 flash:

| Site | Original | Patched |
|---|---|---|
| bank 9 `0xA161` | `90 C6 93` (`mov dptr,#0xC693`) | `02 FE FA` (`ljmp 0xFEFA`) |
| bank 9 `0xA1D5` | `90 C6 93` (`mov dptr,#0xC693`) | `02 FF 08` (`ljmp 0xFF08`) |

The trampolines do:

```
0xFEFA  mov  dptr,#0xD12D
0xFEFD  movx a,@dptr
0xFEFE  orl  a,#1          ; APCS request
0xFF00  movx @dptr,a
0xFF01  mov  dptr,#0xC693  ; restore the original handler state
0xFF04  movx a,@dptr
0xFF05  ljmp 0xA165        ; continue the stock key path
```

and the same with `orl a,#2` / `ljmp 0xA1D9` at `0xFF08` for AOCS.

This is additive: the original handler still runs, and the `0xD12D` bits are
idempotent. If the stock handler already did something useful, it still does.
The request is **volatile** — it runs the refresh for the current session, it
does not rewrite the schedule.

Selecting the item **requests** the refresh; it does not bypass the normal
state machine. The APCS/AOCS consumer still checks whether the panel is ready
(bank 18 `0x936B`) and may defer the run until power-off/standby. If the
monitor is actively displaying an image, expect the request to be honoured
when the panel is turned off, exactly like an automatic refresh.

> **What this does not do:** it does not add a page to the normal OSD, and it
> does not let you type a new interval on the monitor. Interval changes are
> made at build time with `analysis/build_custom.py` (below). The service-menu
> labels remain the stock **APCS** / **AOCS** strings.

---

## Custom builder

`analysis/build_custom.py` is the flexible version of the fixed variants:

```powershell
# Verify all patch sites against the original image
python analysis/build_custom.py --verify

# Build all four menu presets + MANIFEST-custom.md
python analysis/build_custom.py --preset all

# One custom image: 8 h APCS, 750 h AOCS, 12 h reminder, menu actions
python analysis/build_custom.py --name F08-my-care --unlock --menu-actions `
    --apcs 8 --aocs 750 --tss 12

# Interval only, no menu patch
python analysis/build_custom.py --name F08-apcs36 --apcs 36
```

| Option | Meaning |
|---|---|
| `--unlock` | Remove the `0xCFDE == 2` command gate. |
| `--menu-actions` | Make the service-menu APCS/AOCS items request a real refresh. |
| `--apcs N` | APCS every `N` hours; `0` = never. |
| `--aocs N` | AOCS every `N` hours; `0` = never. |
| `--tss N` | Panel-care reminder after `N` hours; `0` = never. |
| `--preset menu` | Stock schedule + menu actions. |
| `--preset menu-quiet` | APCS 36 h + menu actions. |
| `--preset menu-no-nag` | APCS 36 h + reminder off + menu actions. |
| `--preset menu-care` | APCS 8 h + AOCS 750 h + reminder 12 h + menu actions. |

Every site is checked against the original bytes; the tool refuses to write an
image if the source size/MD5 is wrong or if a patch site has drifted.

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
- The AOCS consumer at bank 18 `0x92F1` calls the APCS completion helper
  `0xE5BD`. That helper clears the APCS request, copies the current hours to
  the last-APCS record, and increments the APCS completion counter. Because
  the AOCS path does not re-check the APCS bit before the call, this can record
  an APCS that never ran. It is a real bookkeeping defect, but its **visible**
  effect is not proven: refreshing the last-APCS timestamp would tend to hide
  an APCS request, not create an extra popup. Do not expect `--menu-actions`
  or the interval patches to fix this by themselves.
- The power-on "panel refresh needed" popup is best explained by the stock
  schedule (4 h APCS, 36 h reminder) plus the minute-slot check at bank 13
  `0xCB1A`–`0xCB2D`. `F08-menu-quiet` and `F08-menu-no-nag` reduce or remove
  that nag; they do not rewrite the completion bookkeeping.
- No hardware validation of any kind has been done.
- The updater's acceptance/verification rules are unknown.

Treat these images as a **reproducible starting point for testing**, not as a
finished product.
