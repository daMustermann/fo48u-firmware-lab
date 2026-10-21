# FO48U Firmware Analysis — Working Notes

Status: **in progress**. Goal: reverse-engineer the Gigabyte AORUS FO48U firmware
(Realtek RTD2718, banked 8051) to fix bugs and unlock features (APCS flag bug,
ADCS in OSD, AOCS reliability, ASBL tuning, FreeSync/HDR fixes).

## Target

- File: `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`
- Size: 2,031,616 bytes (0x1F0000)
- MD5: `d4324c6c88abea48b1ee896f7e14ee9f`
- Identified as: `FW: F08  20221115`, panel `LG LE48AOD EPA4`, scaler `RTD2718`.

## Flash layout (observed)

| Region | Range | Notes |
|---|---|---|
| Code (banked) | 0x000000 – 0x13FFFF | 8051 code, ~1.25 MB |
| Erased (0xFF) | 0x140000 – 0x1AFFFF | 384 KB unused flash |
| Gamma/LUT table | 0x1B0000 – 0x1CFFFF | 16-bit gamma curve + brightness table |
| OSD font / LUT | 0x1D0000 – 0x1EFFFF | duplicated 64 KB block (backup) |
| (end) | 0x1F0000 | |

Bank switching on Realtek RTD27xx uses SFRs (typically 0x60/0x61 bank select),
with a common bank (0x0000–0x7FFF) and switchable banks (0x8000–0xFFFF).
The 8051 address space is 64 KB, so the 2 MB image is banked.

## Tools installed

- `radare2` 6.2.4 (8051 arch supported via `rasm2`/`r2 -a 8051`)
- `Ghidra` 12.1.4 (8051:BE:16 processor) — headless project at `F:\Coding\ghidra_proj\FO48U`
  (note: Ghidra clips to 64 KB address space; banked analysis requires splitting)
- Python 3.13 with `capstone`, `unicorn`, `keystone-engine`, `lief`, `pyelftools`
- `binwalk` not available; `strings` (via Python) used.

## Artifacts produced

- `analysis/oplen.py` — 8051 opcode length table.
- `analysis/extract_calls.py` — linear-sweep call-target extractor.
- `analysis/calltargets.txt` — extracted lcall/acall/ljmp/ajmp targets (noisy due to
  banked code; top high-frequency targets are the real utility functions).

## Confirmed findings

- Scaler string: `RTD2718` (at 0xb9b0a and 0xc5378).
- Panel string: `LG LE48AOD EPA4` (0xb9af2).
- Firmware ID: `FW : F08  20221115` (0xb9ada).
- VCP/MCCS descriptor at 0xab381 (monitor responds to DDC/CI VCP codes).
- BootCode / UserCode / UserBoot segment labels at 0xb9ab8.
- Reset vector at 0x0000 → `ljmp 0x4e0c`; interrupt vectors at 0x0003, 0x000b, etc.
- USB control endpoint (from community): Realtek vendor HID `0BDA:1100`.

## OSD string table (corrected)

The string table is **not** a flat `0xFF`-separated blob starting at `0x5400`.
It has an index:

- **Index table**: bank 1, bank-relative `0xD707`, **310 entries × 3 bytes**:
  `offset_hi, offset_lo, 0xFF` (big-endian 16-bit offset, `0xFF` terminator).
- **String data**: bank 1, `0x536C` … `0xD4C2`. Each entry points at a group of
  `0xFF`-separated **language slots** (not necessarily 11 — the slot count
  varies per string).
- End of index table: `0xDAA9`; the bytes after it are glyph/width tables.

Extract/decode with `python analysis/osd_strings.py > analysis/osd_strings.txt`.

### Glyph map (corrected)

Capitals: `A=0x1E` … `M=0x2A`, **`0x2B` = kerning/thin-space (render as nothing)**,
`N=0x2C`, `O=0x2D`, `P=0x2E` … `Z=0x38`.
Small caps: `A=0x3B` … `Z=0x54` (contiguous), `0x55` = trailing special.
Also: `0x01` = space, `0x00` = ignore, `0x0D`/`0xFD` = line break,
`0xFB`/`0xFC` = 2-byte extended glyph.

Earlier notes had `N/O` and `V` off by one; the table above is the verified one
(`AORUS`, `MOVIE`, `VIVID`, `HDMI`, `TYPE C` all decode correctly).

### Corrected string IDs

| ID | String |
|---|---|
| 0 | language names (ENGLISH / DEUTSCH / FRANÇAIS / …) |
| 1 | VOLUME |
| 2 | INPUT |
| 3–9 | VGA / DVI / HDMI / HDMI / DISPLAYPORT / DISPLAYPORT / TYPE C |
| 10–31 | BLACK EQUALIZER, PICTURE MODE, modes, HDR modes |
| 32–57 | DASHBOARD, GAMEASSIST, crosshair, timer, etc. |
| **278** | **IMAGE STICKING PREVENTION** |
| **279** | **APCS** |
| **280** | **AOCS** |
| 281–284 | panel-protection processing / finished messages |
| **285** | **SENDING TIME** |
| **286** | **PANEL USAGE TIME** |
| 287 | PLEASE TURN OFF THE POWER … |
| **288** | **PIXEL SHIFT** |
| **289** | **BRIGHTNESS UNIFORMITY** |
| **290** | **STANDBY QC** |
| **291** | **QC PO** |
| **292** | **QC PFF** |
| **293** | **CHARGE PFF** |
| 294 | PSD SIZE |

(The previous working notes said APCS=277 / AOCS=278; that was off by two
because the language-name block at `0x536C` was missed.)

## Panel protection (APCS / AOCS / TSS)

Full write-up: `analysis/panel_protection.md`.

- Scheduler: **bank 13 `0xCA4E`–`0xCB60`**, one function containing all three rules.
- Hours: big-endian `0xD13D:0xD13E`; minute counter `0xD13F`.
- Last APCS: big-endian `0xD12E:0xD12F`.
- Requests: `0xD12D` bit 0 = APCS, bit 1 = AOCS.
- APCS every **4 h** (`13:0xCAA8  subb a,#4`).
- AOCS every **1500 h** (`13:0xCAD3  mov r4,#5; mov r5,#0xDC`).
- TSS reminder after **36 h** (`13:0xCB1A  subb a,#0x24`).
- Consumers: bank 18 `0x92BC` (APCS), `0x92F1` (AOCS), `0xE5BD` (shared
  completion), `0xC499` (APCS run start).
- Command handlers that set the flags: bank 12 `0x68A9` / `0x68B9`
  (require `0xCFDE == 2`), and bank 19 `0x80A4` (mailbox `0xC501 = 0x20`
  requests **both**).

## BREAKTHROUGH: Bank switching mechanism (RTD2660/RTD2718)

From the RTD2660 spec (page 355-357 "Bank Switch"):

- **PBANK_SEL at XDATA 0xFFFF**: write bank number here to switch program code bank.
- **BANK_EN (bit 0 of XDATA 0xFFFC)** enables bank switching for program address space.
- **SW_MODE (bit 1 of 0xFFFC)**: 0 = P3.5 as A16, 1 = Pbank_switch (0xFFFF).
- **XDATA_BSTART (0xFFFD)**: start bank for XDATA. **XDATA_BSEL (0xFFFE)**: first XDATA bank.
- Up to 256×64KB supported in XFR mode; 64KB default.

**In firmware**, the callable switch routine is **0x6000** (common prefix,
present in every bank):

```
0x6000: mov  0x30, r7           ; remember requested bank
0x6002: clr  EA                 ; disable interrupts while switching
0x6004: mov  dptr, #0xffff      ; PBANK_SEL
0x6007: mov  a, r7
0x6008: movx @dptr, a           ; write bank number -> switch bank
0x600d: movx a, @dptr           ; read back
0x600e: jz   0x6013
0x6010: lcall 0x0000            ; reset if the switch failed
0x6013: ret
```

Call it as `mov r7, #bank; lcall 0x6000`. The switch is **not** a simple
`mov a,#bank; lcall 0x507e`: `0x507e` is the shared tail of a set of stubs at
`0x5060`–`0x507c` that preload `r0` with `0x18`–`0x1f` (the high/data banks),
and it stores the *stub index* in `0x52`. Only one site in the image calls
`0x6000` directly (bank 0 `0xfa58`, with the target bank taken from XDATA
`0xc500`), so cross-bank calls are mostly done by **switching and calling a
fixed trampoline** or by running the target bank as a separate task.

## Service menu / OSD page descriptors

The page descriptor list is in **bank 9 at `0x9783`**. Each entry is four bytes:

```
0xFF, addr_hi, addr_lo, count
```

The list is a **circular carousel of five pages** (it repeats after the fifth
entry):

| Page | Entries | Contents |
|---|---|---|
| `0x9747` | 2 | 16-bit string IDs `0x0100`–`0x0101` (256–257) |
| `0x974B` | 8 | 258–260, **5** (HDMI), 262–265 |
| `0x975B` | 13 | **10** (BLACK EQUALIZER), 267–270, **15** (RTS/RPG), 272, **17–19** (READER/sRGB/VIVID), 276, **21** (CUSTOM), **278** (IMAGE STICKING PREVENTION) |
| `0x9775` | 6 | **279 APCS, 280 AOCS, 281–284** (panel-protection messages) |
| `0x9781` | 1 | **285** (SENDING TIME) |

Each page entry is a **little-endian 16-bit string ID**. The high byte is `0x01`
for IDs 256+, `0x00` for IDs below 256 — which is why the sequence looked like
`(id, flag)` pairs at first. The low IDs (5, 10, 15, 17–19, 21) are genuine
references to normal strings (input and picture-mode names) that the
service/factory pages reuse.

This means the **panel-protection items are already present in the service
menu** (page `0x9775` + the last entry of `0x975B` + `0x9781`). They are hidden
because the whole descriptor list is only used by the service/factory UI.
The menu engine's renderer supports 16-bit IDs, so exposing the page is a
matter of reaching that UI, not of extending the string table.

## Host command mailbox (USB / OSD Sidekick)

- `0xC500` — command code **and** bank selector. `0xFA58` reads it and calls the
  bank switch at `0x6000` with it, so a host command can select a program bank.
- `0xC50D` — command source/class (`2`, `4`, or other).
- `0xC50E` — command index used by the dispatcher.
- `0xC501` — command payload/argument.

The USB/HID command path is in **bank 16 `0xAFC0`–`0xB063`**. For non-special
sources it does:

```
dptr = 0xC50E
lcall 0x6300            ; bank 19 dispatcher, A = command index
```

The dispatcher is at **bank 19 `0x6300`**:

```
0x6300: add a, b        ; A = 3 * index (B = A at entry)
0x6302: add a, 0xf0     ; (b register operand, not immediate)
0x6304: xch a, b
0x6306: jmp @a+dptr
0x6307: 45-entry table of `ljmp` handlers (0x638e … 0x65a9)
```

Handlers of interest (bank 19):

| Index | Handler | Action |
|---|---|---|
| 7 | `0x63BD` | TSS/popup state logic |
| 13 | `0x6499` | sets `0xD35E = 0x14` |
| 37 | `0x64F3` | APCS run-time tick (`0xD380:0xD381`; 60-tick window) |
| 38 | `0x64A9` | panel-time / "next care" check (36 h, uses `0xD12E`, `0xD13D`, `0xD385`) |
| 39 | `0x6531` | toggles `P3.1` and sends `r5=0x28`, `r7:r6=0x03E8` |
| 40 | `0x653B` | calls `0x9824` |

This is a **host-controllable panel-care surface**, but the USB framing that
reaches it is still unknown. It is not reachable through the advertised
DDC/CI VCP list (the VCP descriptor at bank 10 `0xB381` has no VCP 0x20).

### On-demand APCS + AOCS command

Bank 19 `0x80A4` is the cleanest on-demand trigger in the image. It is reached
from the host command parser and does, in effect:

```
if (0xC501 == 0x20) {
    0xD64E |= 0x01;      // panel-care / OSD state
    0xD12D |= 0x03;      // request APCS (bit 0) and AOCS (bit 1)
}
```

So **host command payload `0x20` requests both refreshes**. The request bits
are the same ones the automatic scheduler uses; the consumers are bank 18
`0x92BC` (APCS) and `0x92F1` (AOCS). This is the most likely command behind
the service-menu APCS/AOCS actions, but the host framing that delivers
`0xC501 = 0x20` has not been captured yet.

### Service-menu action handlers

The 30-entry action table at bank 9 `0x97F0` is indexed by menu item. It maps
the page entries above to handlers:

| Item | String | Handler | Observed action |
|---|---|---|---|
| 22 | 278 IMAGE STICKING PREVENTION | `0xA0DA` | toggles `0x6F31` bit 1 |
| 23 | 279 APCS | `0xA14C` | toggles `0x0BAD` / `0x0BAE`, then waits on status bits |
| 24 | 280 AOCS | `0xA1C0` | same pattern for the AOCS state bits |
| 25 | 281 | `0xA232` | panel-protection state |
| 28 | 284 | `0xA388` | panel-protection state |
| 29 | 285 SENDING TIME | `0xA401` | timing/status page |

These handlers are **toggle/status handlers**, not a direct "start a refresh"
call. The actual request is made elsewhere (the `0xD12D` bits above). This is
why the service items can look inert: they flip an enable/state bit, while the
refresh itself is driven by the scheduler or by host command `0x20`.

### Host command class table (bank 3)

Bank 3 `0x8A37` is a second-level dispatcher:

```
0x8A37  a = r7
0x8A38  cjne a,#0x1F,...     ; only 0..0x1E are valid
0x8A40  dptr = 0x8A47
0x8A43  r0 = a
0x8A44  add a,r0
0x8A45  add a,r0
0x8A46  jmp @a+dptr
0x8A47  30-entry table of ljmp handlers (0x8AA4, 0x8B96, 0x8BCF, ...)
```

Bank 19 `0x7E60`–`0x7E99` feeds this path: it sets a power-state bit flag in
`r7` (`0x01`, `0x02`, `0x03`, `0x04`, `0x08`, `0x10`, `0x20`, `0x40`), sets
`r5 = 0x07`, and jumps to `0x8BCF`. `0x8BCF` writes `r5` to `0xC500`, tests a
change flag at `0xD8B3`/`0xD8B4`, and conditionally calls `0x80A4` (the
`0xC501 == 0x20` on-demand refresh handler). This is the strongest lead for
recovering the host framing, but the exact byte layout of the USB/HID report
that reaches it is still unknown.

### `0xD64E` bit 0

`0xD64E` bit 0 is set by the `0xC501 == 0x20` command above. It is checked in
the boot/init block at bank 0 `0xAFC0`–`0xAFC7`; if set, the code sends
`0x719F(0x20)` (which writes `0xC553 = 0x20`, `0xC554 = 0x73`) and calls
`0x6E37` / `0x2EF0`. Bank 11 `0xA7E2` mirrors the bit into `0xFE3A` and
toggle-maintains bit 1. It is a **panel-care/OSD state flag**, not a confirmed
service-menu flag; the service menu entry path is still unresolved.

## Flash layout (confirmed)

- 31 × 64KB banks (0x00000–0x1EFFFF) + 0x1F0000 total (31 × 65536 = 2,031,616). ✓
- Banks 0–19: code banks. Share a common prefix 0x0000–0x536b (~21 KB) containing
  vectors, boot init, and core routines (including the bank switch at 0x6000). Diverge at 0x536c
  (bank-ID/version tag) and the remaining ~44 KB is bank-specific code.
- Banks 20–30: different content (likely XDATA/data/OSD tables or additional banks).
- Bank 0 is the default (reset vector 0x0000 → 0x4e0c).

## How to analyze a specific bank

1. Extract bank N: `dd if=firmware/...bin of=bankN.bin bs=65536 skip=N count=1`
2. Load in Ghidra as 8051:BE:16 raw binary at offset 0.
3. Mark functions at `lcall` targets (common prefix targets are shared; bank-specific
   targets are in the upper region).
4. Run decompiler.

## Next concrete steps

1. Follow the **carousel pointer**: find the code that walks the descriptor
   list at bank 9 `0x9783` and the flag that enables the service carousel.
   The panel page is already defined; only the gate is missing.
2. Find the boot-time service-mode key check (joystick UP at power-on) and
   retarget it to a remote key, or persist the service flag.
3. Verify whether selecting service items 279/280 calls bank 12 `0x68A9` /
   `0x68B9`. If it does, the `0xCFDE == 2` gate is the reason they appear inert.
4. Flash the patched variants on a sacrificial unit; keep the original image.

## Patched variants

`analysis/build_variant.py` generates reproducible variants from the original
image. Each variant is written to `firmware/PATCHED/` with its own MD5 and a
manifest.

| Variant | Patches | Intent |
|---|---|---|
| `F08-unlock` | `unlock_cmd_gate` | Removes the `0xCFDE == 2` gate in front of the APCS/AOCS command entries (bank 12 `0x68AD`, `0x68BD`). Intended to make service-menu APCS/AOCS actions work in normal mode. |
| `F08-care` | `unlock_cmd_gate` + `apcs_2h` + `aocs_750h` + `tss_12h` | Same, plus a more aggressive schedule: APCS every 2 h, AOCS every 750 h, reminder after 12 h. |
| `F08-quiet` | `unlock_cmd_gate` + `apcs_36h` | Same, plus APCS every 36 h — the public F08b popup interval, for fewer interruptions. |

**These are untested.** The original image is the recovery baseline
(`d4324c6c88abea48b1ee896e7e14ee9f`). See `firmware/PATCHED/README.md`.

## Safety

- Always keep the original `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` for recovery.
- Flashing modified firmware may brick the monitor. Test on a sacrificial unit.
- Do not distribute modified firmware without clear "unofficial / at your own risk" labeling.
