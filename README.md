# Gigabyte AORUS FO48U OLED Monitor — Firmware Guide, Pixel Refresh (APCS/AOCS/ADCS) & Reverse Engineering

> **The definitive community guide** for the Gigabyte AORUS FO48U 48" 4K OLED gaming monitor: firmware versions, the pixel-refresher popup fix, manual deep pixel cleaning (ADCS), and firmware reverse engineering / feature expansion.
>
> Monitor model: **Gigabyte AORUS FO48U** (47.53" OLED, 3840×2160, 120 Hz, HDMI 2.1, DisplayPort 1.4, USB-C).  
> Panel: LG Display OLED (LE48AOD EPA4 / LE480AQD / LE48AQD).  
> Scaler: Realtek RTD2718 (banked 8051 firmware). Flash: ≥ 4 MB (32 Mbit).

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [Firmware Versions](#-firmware-versions)
3. [Firmware F08b — Recommended](#-firmware-f08b--recommended)
4. [How to Update Firmware (Step-by-Step)](#-how-to-update-firmware-step-by-step)
5. [Pixel Refresh Systems Explained (APCS / AOCS / ADCS)](#-pixel-refresh-systems-explained-apcs--aocs--adcs)
6. [Pixel Refresher Popup Fix (every 4h → 36h)](#-pixel-refresher-popup-fix-every-4h--36h)
7. [Manual Quick Pixel Refresher (APCS)](#-manual-quick-pixel-refresher-apcs)
8. [Manual Deep Pixel Cleaning (ADCS) via Service Mode](#-manual-deep-pixel-cleaning-adcs-via-service-mode)
9. [Forcing AOCS (1-hour deep clean)](#-forcing-aocs-1-hour-deep-clean)
10. [Service Menu Access](#-service-menu-access)
11. [Troubleshooting](#-troubleshooting)
12. [Firmware Reverse Engineering & Feature Expansion](#-firmware-reverse-engineering--feature-expansion)
13. [Files in This Repository](#-files-in-this-repository)
14. [References](#-references)
15. [Disclaimer](#-disclaimer)

---

## ⚡ Quick Start

- **Install firmware F08b** (private beta) — fixes the 4-hour popup, makes the monitor behave like a normal LCD.
- **Run ADCS (deep 1-hour pixel clean) once a month** per screen to keep OLED burn-in away.
- **Always use USB 2.0** (not 3.x) when flashing firmware — 3.x causes errors.
- **Keep the PC on** while manually refreshing pixels (turning off the PC alone won't trigger refresh on F08b).

---

## 🧬 Firmware Versions

| Version | Date | Status | Notes |
|---|---|---|---|
| F04 | 2021 | Public (legacy) | Initial release. Aggressive ABL, dimming quirks. |
| F05 Beta | 2021 | Public beta | — |
| F06 | 2022-09-07 | **Last public build** | Fixes Aim Stabilizer flicker at 4K 60 Hz. |
| F07 | — | Not released | — |
| **F08 / F08b** | 2022-11-15 | **Private beta** (Gigabyte support) | Popup every 36 h, ASBL fix, frame-rate drops fixed, HDR color fixes. **Recommended.** |

> **F06 is the last firmware Gigabyte ever published.** F08/F08b was sent privately to a Reddit user by Gigabyte support and is not on the official support page.

### Where to get F08b

- Google Drive (original upload by `u/Sssra`): https://drive.google.com/file/d/1PRrKIogOz8YvZH0T2BfmucTJGb2jQuB8/view?usp=sharing
- Mirror files (if ZIP extraction fails):  
  - https://drive.google.com/file/d/1w82Co-…/view?usp=sharing  
  - https://drive.google.com/file/d/1i9-EXi…/view?usp=sharing
- **This repo** ships `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` (MD5: `d4324c6c88abea48b1ee896f7e14ee9f`).

### OSD Sidekick (updater) — required version

- **B21.0707.1** (newer Sidekick builds may not flash `.bin` files).  
- Download: https://www.gigabyte.com/ru/Monitor/G27F/support#support-dl-utility (or https://download.gigabyte.com/FileList/Utility/OSD_Sidekick_B21.0707.1 — search "OSD Sidekick B21.0707.1").  
- This repo ships `osd-sidekick/B21.0707.1/` (Install.exe + UpdPack.cab, 305 MB via Git LFS).

---

## 🔄 Firmware F08b — Recommended

**Highly recommended to install.** It's a private beta sent by Gigabyte support to a Reddit user; still not publicly available.

### What changes after installing F08b

- Pixel Refresher popup now appears every **36 hours** (instead of every 4).
- No more constant interruption.
- You can still manually trigger the quick refresh.
- ❗ **Important:** turning off your PC does **not** start refresh — the monitor just goes to sleep.
- (Community-reported, not officially documented by Gigabyte:) ASBL (auto static brightness limiter) less aggressive, frame-rate drops from FreeSync fixed, HDR color/brightness fixes, volume inconsistencies fixed, panel-usage counter fixed.

---

## 🛠️ How to Update Firmware (Step-by-Step)

Based on the community guide (https://www.reddit.com/r/OLED_Gaming/comments/poe3ey/) and the Russian community mirror.

### Prerequisites

1. Windows PC (10/11, 64-bit).
2. **USB 2.0** connection between PC and monitor (USB 3.0/3.2 causes errors).
3. HDMI **or** DisplayPort connected (keep it connected the whole time).
4. **Disconnect all other USB devices** (keep only keyboard, mouse, and the monitor's USB upstream).
5. **Disable antivirus** — it can block Sidekick driver install and the flash process.
6. Disable PC sleep during the update.

### Steps

1. **Connect** the monitor to the PC with the USB-B → USB-A cable that came with the monitor. Disconnect other monitors / KVMs to simplify.
2. **Download & install OSD Sidekick B21.0707.1** (run `Install.exe` as Administrator).
3. **Extract** the F08 firmware ZIP. You'll get a `.bin` file (`FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`).
4. **Launch OSD Sidekick as Administrator.**
5. Open the **About** tab → click **Update Firmware** → select the `.bin` file.
6. The update takes ~13 minutes. The monitor may reboot several times on its own — **do not touch anything**.
   - The progress bar/timer is buggy — ignore it; just let it finish.
   - Keep using the PC (browse, email) so the OLED protection dimming doesn't interrupt the flash.
7. When done, the monitor reboots and a popup with an **OK** button appears — click OK.
8. **Verify** the firmware version in OSD Sidekick → About.

### If something goes wrong

- Interrupted flash? Unplug the power cord, plug it back in — the monitor should recover (it "shouldn't brick").
- "Firmware download failed" / freeze? Unplug all USB except keyboard/mouse/monitor, run everything as Administrator, retry.
- Mac users: panel-usage counter may keep growing in sleep; manual refresh from the OSD may be needed.

---

## 🔬 Pixel Refresh Systems Explained (APCS / AOCS / ADCS)

The FO48U has **three** compensation systems to fight OLED burn-in / image retention:

| System | Trigger | Duration | When it runs |
|---|---|---|---|
| **APCS** — Auto Prevention Compensation System | After 4 h of use | ~5 min | Automatically after monitor power-off (or manually via OSD). |
| **AOCS** — Auto Organic Compensation System | After 1500 h of use | ~1 hour | Automatically after power-off (or manually via OSD). Deep scan with white lines — normal. |
| **ADCS** — (Deep Pixel Cleaning) | Manual only (service mode) | ~1 hour | **Locked in the menu on all firmware**, but unlockable via service mode. |

### How they behave on F06 vs F08b

- **F06 (stock):** popup asks for refresh every 4 h. APCS/AOCS set to "Auto" (cannot change). AOCS often never triggers automatically (bug).
- **F08b:** popup every 36 h. Quick refresh still manually triggerable. Turning off the PC no longer starts refresh (monitor sleeps).

### Manual OSD paths

- APCS: `Settings → System → Other Settings → APCS → ON` (only available after ≥ 4 h continuous use; grayed out otherwise).
- AOCS: `Settings → System → Other Settings → AOCS → ON` (only after ≥ 1500 h; grayed out otherwise).

---

## 🔔 Pixel Refresher Popup Fix (every 4 h → 36 h)

**Problem:** On stock firmware, the "Please turn off the power for panel protection" popup interrupts you every 4 hours.

**Fix:** Install **F08b** (see above). The popup then appears every 36 hours instead.

**Workaround on stock firmware:** press the power button on the **remote** every time you shut the PC down for the night; if you forget, the monitor gets stuck in the popup state. Recovery: unplug power, push the joystick nub several times, wait a minute, plug back in.

---

## 🧼 Manual Quick Pixel Refresher (APCS)

To run the ~10-minute quick refresh manually (F08b):

1. **Do not shut down the PC first.**
2. Use the remote or physical button to turn off the **monitor while the PC is still on**.
3. If it was running for even 1–2 hours, it auto-runs the ~10 min refresh after shutdown.

💡 **Pro tip:** If you use the monitor actively, manually turn it off before your PC to refresh pixels more often and reduce burn-in risk.

---

## 🧠 Manual Deep Pixel Cleaning (ADCS) via Service Mode

ADCS is the **hour-long deep refresh** that is **locked in the menu on every firmware**, even F08b. It can be **enabled manually anytime** through service mode — no 4-hour wait, no popup required.

### Steps to start ADCS manually

1. Keep the PC running with a video signal to the monitor.
2. **Unplug the power cable from the monitor.**
3. **Press and hold the joystick backwards** (toward the back panel).
4. While still holding, **plug the power cable back in.**
5. Wait until the Windows signal appears again, then **release the joystick.**
6. You'll see a small **"F"** in the top-left corner of the menu — that's service mode.
7. Navigate to: `Settings → System → Other Settings → ADCS → ON`
8. Confirm. The monitor enters a **1-hour deep pixel refresh**.

> **Note:** at least on F08 (and reportedly F05/F06 too) you don't have to wait 4 hours or for a popup — trigger it **anytime**.

### Recommended cadence

The guide's author runs **manual ADCS once a month per screen** on monitors with 3000+ hours and reports **zero burn-in** (visual or in tests).

---

## 🔥 Forcing AOCS (1-hour deep clean)

If AOCS (the 1500-hour deep clean) has never triggered automatically (a known bug), you can force it:

1. Unplug the monitor power.
2. Push the joystick **away** (without pressing it in).
3. Plug the power cable back in.
4. Open the OSD menu — an **"F"** appears in the top-left corner (service mode).
5. Run the monitor for **4+ hours straight**, so it prompts for panel protection on power-off.
6. Power off the monitor → the full **~60-minute AOCS** runs for the first time.

After that, burn-in / image retention should be cleared.

---

## 🔧 Service Menu Access

(For disabling ASBL/ASC, power tweaks, panel info, color calibration tools.)

**⚠️ Disclaimer:** messing with the service menu may risk damaging the monitor and/or voiding your warranty. Proceed at your own risk.

1. Power monitor off and unplug the power cord. Leave unplugged ≥ 15 seconds.
2. While **holding UP on the joystick**, plug the power cord back in and power on with the remote (or push the joystick button down while holding up).
3. Open the OSD — an **"F"** appears in the top-left corner. Navigate up and select the **"F"** to open the service menu.

**Side effect (confirmed):** simply booting into service mode disables auto-dimming (ASBL) until the next power cycle / sleep.

**What is in the service menu (from the firmware):** the panel-protection
page exists at bank 9 `0x9775` and lists **IMAGE STICKING PREVENTION** (string
278), **APCS** (279), **AOCS** (280), the panel-protection messages (281–284),
and **SENDING TIME** (285). **PANEL USAGE TIME** (286), **PIXEL SHIFT** (288),
**BRIGHTNESS UNIFORMITY** (289) and the **STANDBY QC / QC ON / QC OFF /
CHARGE OFF** items (290–293) are in the same service string set. If your unit
shows these entries but they do nothing, see the experimental
`firmware/PATCHED/` variants and `analysis/README.md`.

---

## 🐛 Troubleshooting

| Symptom | Fix |
|---|---|
| "Please turn off the power for panel protection…" popup won't go away | Let APCS run (5 min). Or unplug power, push joystick nub several times, wait 1 min, plug back in. |
| APCS/AOCS grayed out in OSD | Monitor hasn't been on ≥ 4 h (APCS) or ≥ 1500 h (AOCS). |
| Firmware update "Firmware download failed" / freeze | Unplug all USB except keyboard/mouse/monitor; run as Admin; use USB 2.0; disable antivirus. |
| Firmware update interrupted | Unplug power cord, plug back in — should recover. |
| Popup every 10 min instead of 4 h | Defective unit or stuck state — reset via unplug + joystick (above). |
| AOCS never ran automatically | Force it (see "Forcing AOCS"). |
| HDR looks dim / blown out | Manually tune Contrast (scales peak brightness / hard-clip point). |
| Burn-in on menus/health bars in HDR | Avoid HDR for static UI, or raise brightness with care; run ADCS monthly. |

### Burn-in prevention tips (from owners)

- Let Windows turn the monitor off after 5 min.
- Auto-hide the taskbar / start menu.
- Keep brightness ~50–75.
- Use a wallpaper rotator / animated wallpaper (WallpaperEngine) or a periodic light-grey bar.
- Windows desktop slideshow interval via registry: `HKEY_CURRENT_USER\Control Panel\Personalization\Desktop Slideshow\Interval` (ms; 3 min = 180000).
- Run APCS on every power-off; run ADCS monthly.

---

## 🧬 Firmware Reverse Engineering & Feature Expansion

> The FO48U is a good panel stuck behind buggy firmware that stopped getting updates in late 2022. F06 is the last public build; F08 exists but was never released. **Nobody is coming to fix this** — so the community is reading the firmware instead.

### What's known (confirmed)

- **Scaler:** Realtek RTD2718 (strongly supported, not photographically proven — chip sits under a heatsink).
- **Code:** banked 8051.
- **Main AV board:** `0171-2272-7600`; power board `25-DTO731-X2P1`; T-Con `LE48AQD(EP)(A4)` rev V0.6.
- **Panel P/N mismatch (open):** firmware string says `LG LE48AOD EPA4`, panel label says `LE480AQD(EP)(A4)`, T-Con says `LE48AQD(EP)(A4)` — not yet reconciled.
- **Flash part:** unknown; updater addresses a window ending at `0x3EFFFF` → at least 4 MB (32 Mbit).
- **USB control endpoint:** Realtek vendor HID, `0BDA:1100`.
- **APCS logic:** fires on exact 4-hour multiples (modulo, not a threshold) — that's why searching for a plain `≥ 4 h` comparison never found it.
- **Bug (confirmed signature):** after APCS completes, the next power-on immediately shows "Please turn off the power for panel protection…" — a request flag the completion path fails to clear on one branch.

### Firmware images held / hashed (5 builds)

F04, F05 Beta, F06 (2022-08-19), F08/F08b (2022-11-15), plus OSD Sidekick B21.0707.1 updater.

### Goals for feature expansion

- Fix the APCS completion flag bug (clear the request flag).
- Unlock ADCS in the normal OSD menu (no service mode).
- Make AOCS trigger reliably.
- Reduce ASBL aggressiveness / allow disabling persistently.
- Fix FreeSync frame-rate drops and HDR color issues.
- Allow APCS interval tuning (e.g., 36 h like F08b, or user-configurable).

### Progress since the first release

- **String table decoded.** The OSD index table is bank 1 `0xD707` (310 entries
  × 3 bytes); string data is bank 1 `0x536C`–`0xD4C2`. APCS = ID 279,
  AOCS = ID 280, IMAGE STICKING PREVENTION = 278.
- **Panel-protection scheduler found.** All three rules live in bank 13
  `0xCA4E`–`0xCB60`: APCS every 4 h, AOCS every 1500 h, reminder after 36 h.
- **Request path mapped.** `0xD12D` bit 0 = APCS, bit 1 = AOCS; consumed by
  bank 18 `0x92BC` / `0x92F1`; completion helper at bank 18 `0xE5BD`.
- **Service-menu pages found.** Bank 9 `0x9783` is a five-page descriptor list;
  page `0x9775` is the panel-protection page (IDs 279–284), and `0x9781`
  contains "SENDING TIME" (285). The APCS/AOCS items already exist in the
  service UI.
- **Host command path found.** Bank 16 `0xAFC0` → bank 19 `0x6300` (45-entry
  handler table at `0x6307`); `0xC500` doubles as a bank selector.
- **Patched variants produced.** See `firmware/PATCHED/` — experimental,
  untested, and clearly labelled.

### Patched firmware variants (experimental)

`analysis/build_variant.py` reproduces two variants from the original F08
image, with every patch checked against the expected original bytes:

| Variant | MD5 | What it changes |
|---|---|---|
| `F08-unlock.bin` | `c94cf874324c9cf0f76e38f5b22308b1` | Removes the `0xCFDE == 2` gate in front of the APCS/AOCS command entries (bank 12 `0x68AD`, `0x68BD`). Intended to make the service-menu APCS/AOCS actions work in normal mode. |
| `F08-care.bin` | `741ae5c02f5362304ed1df728daa48f3` | `F08-unlock` plus APCS every 2 h, AOCS every 750 h, reminder after 12 h. |

> ⚠️ **Neither variant has been flashed on hardware.** The service-menu gate
> removal is a hypothesis: it is confirmed that the gate exists, not confirmed
> that it is the only thing blocking the menu actions. Keep the original image
> (`d4324c6c88abea48b1ee896f7e14ee9f`) and read
> [`firmware/PATCHED/README.md`](firmware/PATCHED/README.md) before trying them.

### Local decompilation quickstart

```bash
# 1. Inspect the binary
python -c "d=open('firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin','rb').read(); print(len(d), hex(len(d)))"
md5sum firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin

# 2. Realtek 8051 toolchain (community). Useful tools:
#    - sdcc (8051 compiler/assembler) for reassembly experiments
#    - radare2 / Ghidra with 8051 processor module for decompilation
#    - binwalk for splitting banked regions / filesystems
binwalk -e firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin

# 3. Search for strings / constants
strings -a -n 6 firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin | grep -iE "apcs|aocs|adcs|panel|protect|0BDA|RTD|LE48"
```

### How you can help (10-minute checks)

From the reverse-engineering thread — owners can verify:
1. **Scaler chip marking** — photograph the chip under the heatsink (RTD2718?).
2. **Flash chip part number** — read the SOIC-8 near the scaler.
3. **Panel label vs firmware string** — photo of the panel sticker.
4. **Whether ADCS menu item exists on your firmware** (F04/F05/F06/F08).
5. **APCS interval on your unit** (hours between popups).

---

## 📦 Files in This Repository

```
.
├── README.md                          # This guide
├── firmware/
│   ├── F08-20221115/
│   │   ├── FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin   # original F08 (2,031,616 bytes)
│   │   └── FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.MD5.md5
│   └── PATCHED/
│       ├── F08-unlock.bin             # experimental: APCS/AOCS command gate removed
│       ├── F08-care.bin               # experimental: unlock + faster care schedule
│       ├── *.bin.md5                  # checksums for the variants
│       └── MANIFEST.md                # generated patch manifest
├── analysis/
│   ├── README.md                      # reverse-engineering notes (strings, banks, panel logic)
│   ├── panel_protection.md            # APCS/AOCS/TSS write-up
│   ├── osd_strings.py / osd_strings.txt   # decoded 310-entry OSD string table
│   ├── build_variant.py               # reproducible patched-firmware builder
│   ├── patch.py                       # extract/reassemble/patch scaffold
│   └── banks/bank_0..19.bin           # per-bank 64 KB code extracts
├── osd-sidekick/
│   └── B21.0707.1/
│       ├── Install.exe                # OSD Sidekick installer
│       ├── support.xml                # Supported models: FO48U, G27F, G27Q
│       └── UpdPack.cab               # Sidekick payload (305 MB, Git LFS)
├── .gitignore
└── LICENSE
```

---

## 📚 References

- Reddit — "The Ultimate Guide to AORUS FO48U firmware and pixel refresh pop-up's" (u/ilya_djin, r/aorus, 2025-06-15): https://www.reddit.com/r/aorus/comments/1lcctl4/
- Reddit — "FO48U F08 Firmware" (u/Sssra, r/OLED_Gaming, 2024-03-22): https://www.reddit.com/r/OLED_Gaming/comments/1bl7ml1/
- Reddit — "Update AORUS FO48U firmware (step-by-step)" (r/OLED_Gaming): https://www.reddit.com/r/OLED_Gaming/comments/poe3ey/
- Reddit — "Burn in on my AORUS FO48U, how to force AOCS?" (r/aorus): https://www.reddit.com/r/aorus/comments/188rbb2/
- Reddit — "Reverse-engineering the AORUS FO48U firmware" (u/tomazany, r/OLED_Gaming, 2026-08-03): https://www.reddit.com/r/OLED_Gaming/comments/1vec8uk/
- Reddit — "You can disable auto static content dimming (ASBL/ASC)…" (r/OLED_Gaming): https://www.reddit.com/r/OLED_Gaming/comments/uvv8qd/
- Gigabyte AORUS FO48U support page: https://www.gigabyte.com/Monitor/AORUS-FO48U/support
- Gigabyte monitor user manual (English): https://download.gigabyte.com/FileList/Manual/AORUS_FO48U_UM_English_20220214.pdf
- TousLesDrivers F06 mirror: https://www.touslesdrivers.com/index.php?v_code=73374
- Eskerahn blog (firmware update notes): https://eskerahn.dk/?p=4772
- Box.co.uk — "How to Update Firmware on a Gigabyte Monitor": https://box.co.uk/blog/update-gigabyte-monitor-firmware

---

## ⚠️ Disclaimer

- Firmware flashing can brick your monitor. Flash at your own risk. Always use USB 2.0 and keep power stable.
- Service-menu tweaks may void your warranty.
- F08/F08b is an **unreleased private beta** — not officially supported by Gigabyte.
- This repository is a community effort and is not affiliated with Gigabyte.
- MD5 of the firmware binary: `d4324c6c88abea48b1ee896f7e14ee9f`. Always verify before flashing.

---

*If this guide helped you, star the repo and share it. Contributions (corrections, new findings, decompilation results) are welcome via pull requests.*
