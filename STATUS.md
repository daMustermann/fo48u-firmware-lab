# Project status

Last updated: 2026-10-21

This page separates **what is confirmed**, **what is experimental**, and
**what is still unknown**. The main guide is [`README.md`](README.md); the
reverse-engineering notes are in [`analysis/README.md`](analysis/README.md).

> The FO48U firmware in this repository (F08, 2022-11-15) is an **unreleased
> private beta**. Everything here is unofficial. Flashing modified firmware
> can brick the monitor.

---

## Confirmed

| Area | Finding |
|---|---|
| Image | `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`, 2,031,616 bytes (31 × 64 KiB), MD5 `d4324c6c88abea48b1ee896f7e14ee9f` |
| CPU / layout | Banked 8051, code banks 0–19, common 21 KB prefix, bank switch via XDATA `0xFFFF` (routine `0x6000`, bank in R7) |
| Strings | Index table bank 1 `0xD707` (310 entries × 3 bytes), data bank 1 `0x536C`–`0xD4C2`; APCS = 279, AOCS = 280 |
| Panel protection | Scheduler bank 13 `0xCA4E`–`0xCB60`: APCS every 4 h, AOCS every 1500 h, reminder after 36 h |
| Request bits | `0xD12D` bit 0 = APCS, bit 1 = AOCS; consumed by bank 18 `0x92BC` / `0x92F1`; completion helper `0xE5BD` |
| Service pages | Bank 9 `0x9783`: five-page carousel; page `0x9775` = IDs 279–284, page `0x9781` = ID 285 |
| Service actions | Bank 9 `0x97F0`: 30-entry action table; item 23 (APCS) = `0xA14C`, item 24 (AOCS) = `0xA1C0` |
| Host mailbox | `0xC500` command/bank selector, `0xC50D` source, `0xC50E` index, `0xC501` payload; USB path bank 16 `0xAFC0` → bank 19 `0x6300` |
| On-demand command | Payload `0x20` sets `0xD12D |= 0x03` (both refreshes) and `0xD64E |= 1` at bank 19 `0x80A4` |
| VCP list | Bank 10 `0xB381`; advertised VCPs include `C6 C8 CA CC`, no VCP `0x20` |

## Experimental

Two patched images are in [`firmware/PATCHED/`](firmware/PATCHED/). They are
**built reproducibly** and every patch site is checked against the original
bytes, but **none has been flashed on hardware**.

| Variant | MD5 | Intent |
|---|---|---|
| `F08-unlock.bin` | `c94cf874324c9cf0f76e38f5b22308b1` | Remove the `0xCFDE == 2` gate in front of the APCS/AOCS command entries (bank 12 `0x68AD`, `0x68BD`) |
| `F08-care.bin` | `741ae5c02f5362304ed1df728daa48f3` | `F08-unlock` + APCS 2 h / AOCS 750 h / reminder 12 h |

Rebuild and verify:

```powershell
python analysis/build_variant.py --verify
python analysis/build_variant.py
```

## Unknown / open

1. **Service-menu gate.** The panel-protection page is defined, but the code
   that enables the service carousel (and the boot-time joystick-UP check)
   has not been located. `0xD64E` bit 0 is a panel-care/OSD state flag, not a
   confirmed service flag.
2. **Whether the service APCS/AOCS items actually start a refresh.** The
   handlers at `0xA14C` / `0xA1C0` toggle state bits; the real request is
   `0xD12D`. The link between the two is not proven.
3. **Host framing.** The USB HID / OSD Sidekick packet format that delivers
   `0xC501 = 0x20` is unknown, so command `0x20` cannot yet be sent from a PC.
4. **Updater acceptance.** The exact checks OSD Sidekick / the bootloader
   perform on a modified `.bin` are unknown. A successful write is not
   guaranteed.
5. **Recovery.** No verified recovery path for a failed flash on this model.

## Recommended next steps

- Capture USB traffic from OSD Sidekick while the service/panel-care actions
  are used; look for payload `0x20`.
- Trace the caller of the bank 9 menu renderer and the flag that selects the
  service carousel.
- Test the patch variants on a sacrificial unit with a hardware flash backup.
- If a variant works, record the exact OSD Sidekick version, USB port, and
  post-flash behavior in an issue.

## Safety

- Keep the original image and its MD5 on a second device.
- Do not interrupt power during a flash.
- Do not flash a modified image if you cannot recover the monitor.
- OLED protection logic (APCS/AOCS/ABL) is deliberately left functional; the
  variants change *when* it runs, not *whether* it exists.
