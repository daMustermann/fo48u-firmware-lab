# FO48U OLED panel-protection logic (APCS / AOCS / TSS)

Reverse-engineered from `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`
(banked 8051, RTD2718, panel `LG LE48AOD EPA4`).

All addresses are **bank-relative** unless marked otherwise. Code banks are
64 KiB and are switched through XDATA `0xFFFF` (see `analysis/README.md`).

> **Status: static analysis only.** Nothing here has been run on hardware.
> Patching this firmware can brick the monitor. Keep the original image and
> verify every byte before flashing.

---

## 1. What the three routines are

| Name | Full name (Gigabyte wording) | Trigger | Effect |
|---|---|---|---|
| **APCS** | Auto Pixel Cleaning System (short refresh) | every **4 h** of panel usage | runs a short pixel-refresh cycle |
| **AOCS** | Auto OLED Care System (long/deep refresh) | every **1500 h** of panel usage | runs the long compensation cycle |
| **TSS** | "Time to Screen Saver" / panel-care reminder | **36 h** since the last APCS | OSD reminder popup |

The three rules live in **one function**: bank 13, `0xCA4E`–`0xCB60`.
This matches the parallel reverse-engineering report (`tomazany`,
r/aorus post `1vec8uk`).

---

## 2. Variable map (XDATA)

| Address | Width | Meaning | Notes |
|---|---|---|---|
| `0xD13D` | 8 | panel-usage hours **high byte** | 16-bit big-endian pair `0xD13D:0xD13E` |
| `0xD13E` | 8 | panel-usage hours **low byte** | incremented first, carry into `0xD13D` |
| `0xD13F` | 8 | minute sub-counter | 0–59, incremented per minute tick |
| `0xD12E` | 8 | last-APCS hours **high byte** | big-endian pair `0xD12E:0xD12F` |
| `0xD12F` | 8 | last-APCS hours **low byte** | |
| `0xD12D` | 8 | request flags | **bit 0 = APCS request**, **bit 1 = AOCS request** |
| `0xD380` | 8 | APCS run-time counter low | compared against 60 (`0x3C`) |
| `0xD381` | 8 | APCS run-time counter high | |
| `0xD131` | 8 | APCS completion counter | incremented on successful completion |
| `0xD130` | 8 | AOCS completion counter | incremented on successful completion |
| `0xD644` | 8 | mode/status byte | compared with `0x5A` before a popup update |
| `0xD385` | 8 | TSS popup minute slot | compared with `0xD13F` |
| `0xD35B` | 8 | TSS popup suppression | bit tests in the TSS branch |
| `0xD64E` | 8 | panel-protection flag register | set by the bank-19 command path |
| `0xCFDE` | 8 | panel-protection command selector | APCS/AOCS handlers require `== 2` |

**Endianness warning:** hours are stored **big-endian** (`high` at the lower
address). Do not treat `0xD13D:0xD13E` as a little-endian `uint16`.

---

## 3. The timer / scheduler (bank 13, `0xCA4E`)

Called once per minute (or on a periodic tick).

```
0xCA4E  inc  0xD13F                 ; minute counter++
0xCA54  lcall 0xC099                ; RTC/tick helper on 0xD13D
0xCA64  jnc  0xCA7B                 ; no hour rollover -> skip
0xCA66  ; sanity clamp: if 0xD13F >= 0x3B, force 0xFF/0xFF/0x3B
0xCA7B  a = 0xD13F
        subb a,#0x3C                ; < 60 ?
        jc   0xCAEF                 ; yes -> skip hour++
0xCA84  inc  0xD13E                 ; low byte++
        jnz  0xCA97
        inc  0xD13D                 ; carry into high byte
0xCA97  ; elapsed = current_hours - last_apcs_hours
        ; if current < last -> clamp last = current
```

### APCS rule

At `0xCAA2` the elapsed hours are compared with **4**:

```
0xCAA8  subb a,#0x04        ; <-- APCS interval (4 hours)
0xCAAA  jc   ...            ; elapsed < 4 -> no APCS
0xCAB7  orl  0xD12D,#0x01   ; request APCS
0xCABA  lcall 0x2B9C        ; wake / notify the panel-protection task
```

### AOCS rule

At `0xCACD` the **current** hours are divided by **1500** (`0x05DC`):

```
0xCAD3  mov  r4,#0x05
0xCAD5  mov  r5,#0xDC       ; divisor = 0x05DC = 1500
0xCAD7  lcall 0x36F4        ; 16-bit divide, remainder in r4:r5
0xCADB  mov  a,r4
0xCADC  orl  a,r5
0xCADE  jnz  ...            ; remainder != 0 -> no AOCS
0xCAE9  orl  0xD12D,#0x02   ; request AOCS
0xCAEC  lcall 0x2B9C
```

### Clamp / counter-reset path

```
0xCAEF  lcall 0xC162
0xCAF6  jnc  0xCB03         ; current >= last -> normal path
0xCAF8  mov  0xD12E,r4      ; current < last (hours reset / wrap):
0xCAFC  mov  0xD12F,r5      ;   store current as the new "last" value
0xCB00  lcall 0x2B9C
```

### TSS rule (36 h reminder)

```
0xCB03  r6:r7 = current_hours - last_apcs_hours
0xCB1A  subb a,#0x24        ; <-- 0x24 = 36 hours
0xCBrr  jc   ...            ; elapsed < 36 -> no popup
0xCB21  a = 0xD13F ; b = 0x3C ; div ab
        ; compare remainder (0xD13F) with 0xD385
0xCB2E  cjne a,0xF0,...
0xCB35  r5 = 0x27           ; popup / message id 0x27 (39)
0xCB39  lcall 0x2B54        ; show OSD message
```

Because `0xD13F < 60`, the `div ab` quotient is 0 and the remainder is just
`0xD13F`. So the popup is shown once per hour, at the minute value stored in
`0xD385` (normally 0), after 36 h have elapsed since the last APCS.

---

## 4. Request flags and consumers

`0xD12D` is only a **request** register. The actual work is done by a
state machine in **bank 18**.

### APCS consumer — bank 18 `0x92BC`

```
0x92BC  a = 0xD12D
0x92C0  jb  acc.0, 0x92C6      ; APCS requested?
0x92C3  ljmp 0x934F            ; no
0x92C6  r7 = 0x1E
0x92C8  lcall 0x936B           ; "can run?" / start sequence
0x92CB  jnc 0x92E4             ; not ready -> re-set request
0x92CD  lcall 0xE5BD           ; completion bookkeeping (clears bit 0)
0x92D0  jnz  0x92D8
0x92D2  inc  0xD130            ; AOCS completion counter (shared path)
0x92D8  a = 0xD644 ; cjne a,#0x5A ...
0x92EB  lcall 0x9355
0x92EE  ljmp 0x934C
0x92E4  orl  0xD12D,#0x01      ; re-arm the request
```

### AOCS consumer — bank 18 `0x92F1`

```
0x92F1  a = 0xD12D
0x92F6  rrc a                  ; shift bit 1 into carry
0x92F7  jnb  acc.0, 0x934F     ; AOCS requested?
0x92FA  r7 = 0x1F
0x92FC  lcall 0x936B
0x92FF  jnc  0x9337            ; not ready
0x9301  lcall 0xE5BD           ; completion bookkeeping (clears bit 0)
0x9304  jnz  0x930C
0x9306  inc  0xD130
0x930C  a = 0xD644 ; cjne a,#0x5A ...
0x9316  lcall 0x9355
0x9319  lcall 0x2932
0x931C  clr  a
0x931D  mov  0xD380,a          ; reset APCS run-time counter
0x9322  mov  0xD381,a
0x9323  r5 = 0x26 ; r7:r6 = 0xEA60  -> lcall 0x2B54   ; message
0x932C  r5 = 0x28 ; r7:r6 = 0x03E8  -> lcall 0x2B54   ; message
0x9337  lcall 0xFC60           ; retry / error path
```

`0xE5BD` is the **shared completion helper**:

```
0xE5BD  anl  0xD12D,#0xFE      ; clear APCS bit
0xE5C4  r7 = 0xD13D (high)
0xE5C9  a  = 0xD13E (low)
0xE5CB  mov  0xD12E,r7?        ; copy current hours -> last-APCS hours
0xE5D1  mov  0xD12F,a
0xE5D3  inc  0xD131            ; APCS completion counter++
0xE5D9  ret
```

Note the **bit-1 (AOCS) request is not cleared here**. It is cleared later in
bank 18 `0xC4E4` (`anl 0xD12D,#0xFD`) after the run finishes.

The AOCS consumer calls **both** paths:

```
0x9301  lcall 0xE5BD      ; APCS bookkeeping: clear bit 0, copy hours, inc 0xD131
...
0xC4E4  anl   0xD12D,#0xFD ; clear bit 1
0xC4EB  copy  current hours -> 0xD12E/0xD12F
0xC4FA  inc   0xD133        ; AOCS counter
```

So an AOCS completion also performs the APCS bookkeeping and increments the
**APCS** counter (`0xD131`), even though no APCS ran. This shared-path
double-count is a **bookkeeping defect**: the request and the last-hours
timestamp are updated on a path that is not the APCS path. It is not a missing
clear — the code does clear both bits eventually.

Its visible effect is **not proven**. `0xE5BD` also copies the current panel
hours into `0xD12E`/`0xD12F` (the last-APCS record), which would tend to
*suppress* a future APCS request, not create an extra popup. The power-on
"panel refresh needed" nag is better explained by the stock 4 h APCS / 36 h
reminder schedule and the minute-slot check at `0xCB1A`–`0xCB2D`. Treat the
`0xE5BD` call as a candidate cleanup, not as a confirmed popup fix.

### APCS run-time / start — bank 18 `0xC499`

```
0xC499  a = 0xD12D
0xC49E  jb  acc.0, 0xC4A4      ; APCS requested?
0xC4A4  clr 0xD380 / 0xD381    ; reset run-time counter
0xC4AB  r7 = 0x20 ; lcall 0xC08A
0xC4B4  r7:r6 = 0x0032 ; lcall 0x2A04
0xC4B7  r7 = 0x02 ; lcall 0x1000   ; <-- APCS execution start
0xC4BC  r7:r6 = 0x0DAC ; lcall 0x292C
```

The run-time counter `0xD380:0xD381` is compared with `60` at `0xC487`:

```
0xC488  a = 0xD381
0xC48C  subb a,#0x3C
0xC491  a = 0xD380
0xC492  subb a,#0x00
0xC494  jnc 0xC499             ; >= 60 -> start/continue
```

So APCS runs for roughly **60 ticks** before the start path is taken.

---

## 5. Command paths that set the flags

### Bank 12 `0x68A9` / `0x68B9` — panel-protection command handler

```
0x68A9  a = 0xCFDE ; xrl a,#2 ; jnz 0x68D4   ; only in mode 2
0x68B1  orl 0xD12D,#0x01                     ; APCS request
0x68C7  lcall 0x2C50 ; lcall 0x2B9C

0x68B9  a = 0xCFDE ; cjne a,#2,0x68D4
0x68C0  orl 0xD12D,#0x02                     ; AOCS request
0x68C7  lcall 0x2C50 ; lcall 0x2B9C
```

These are **two entry points in the bank-12 command dispatcher**
(`0x66E0`–`0x68D4`). They are the cleanest "start APCS / start AOCS"
primitives in the firmware.

### Bank 19 `0x80A4` — mailbox command `0x20`

```
0x80A4  mov 0xC501,r7
0x80A9  lcall 0x0E86
0x80AC  a = r7 ; jnz 0x80C9
0x80AF  a = 0xC501 ; cjne a,#0x20,0x80C9
0x80B6  ... set 0xD64E bit 0
0x80BD  orl 0xD12D,#0x03        ; request BOTH APCS and AOCS
```

Writing `0x20` to the `0xC501` mailbox therefore requests both routines at
once. This path is also referenced from bank 19 `0x8BE2`.

### Bank 7 `0xC4A9` / bank 11 `0xA7AD` — reset/clear paths

Both reset `0xD13D`–`0xD13F` and clear `0xD12D`. They are likely
factory-reset / power-off handlers and are **not** useful as triggers.

---

## 6. Exact patch sites

Offsets are **file offsets** = `bank * 0x10000 + address`.

| Feature | Bank:addr | Original bytes | Meaning |
|---|---|---|---|
| APCS interval (hours) | `13:0xCAA8` | `94 04` | `subb a,#4` |
| AOCS period (hours) | `13:0xCAD3` | `7C 05 7D DC` | `mov r4,#5; mov r5,#0xDC` |
| TSS reminder (hours) | `13:0xCB1A` | `94 24` | `subb a,#0x24` |
| TSS popup minute slot | `13:0xCB29` | `90 D3 85` | loads `0xD385`, compared at `0xCB2D` |
| Force APCS request | `13:0xCAB7` | `44 01` | `orl a,#1` |
| Force AOCS request | `13:0xCAE9` | `44 02` | `orl a,#2` |
| Both requests (mailbox) | `19:0x80BD` | `44 03` | `orl a,#3` |
| Service-menu APCS key path | `9:0xA161` | `90 C6 93` | redirect to trampoline at `0xFEFA` |
| Service-menu AOCS key path | `9:0xA1D5` | `90 C6 93` | redirect to trampoline at `0xFF08` |

A patch that starts APCS on demand must either:

1. call the bank-12 entry `0x68A9` / `0x68B9` from a new key or menu hook, or
2. set `0xD12D |= 0x01` / `0x02` from any code that runs in a switched bank.

Because bank switching is explicit, a hook must switch to the target bank
before calling a bank-local address. The common-prefix bank-switch routine is
`0x507E` (write bank number to XDATA `0xFFFF`).

---

## 7. Open questions

1. **Menu gating**: the panel-protection page is not yet located. The strings
   exist (`IMAGE STICKING PREVENTION` = 278, `APCS` = 279, `AOCS` = 280), but
   no menu table referencing them has been found. The page may be built in
   code, or shown only when the service flag is set.
2. **`0xCFDE`**: acts as a command selector in the bank-12 dispatcher
   (`== 2` enables APCS/AOCS commands). What writes `0xCFDE` and when?
3. **`0xD64E`**: panel-protection flag register set by the bank-19 mailbox
   command. It is read in bank 11 `0xA7E2`–`0xA880` (bit 0/1/2). Its exact
   role (enable / test mode / UI state) is unresolved.
4. **Service-mode entry**: the joystick-UP-at-power-on check has not been
   located. Candidate flags are `0xD64E`, `0xCFDE`, and the boot key path in
   bank 0 `0x4E0C`.
5. **Bounds**: `0xD13F` clamp at `0x3B` and the `0xC099` helper need a
   hardware trace to confirm the tick rate (1 minute vs. another unit).

---

## 8. Reproducing the disassembly

```powershell
r2 -q -e scr.color=0 -a 8051 -b 8 -m 0x0 `
   -c "s 0xCA4E; pd 200" analysis/banks/bank_13.bin
```

The full captured listings are in:

- `analysis/panel_protection_disasm.txt` (bank 13, `0xCA4E`–`0xCB60`)
- `analysis/panel_consumers_disasm.txt` (bank 18 / 19 / 12 consumers)
