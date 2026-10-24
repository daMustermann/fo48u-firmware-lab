# FO48U host-side controller (experimental)

This is a minimal, safety-gated Python controller for the Gigabyte AORUS FO48U.
It wraps the byte-verified Realtek-HID frames documented in
`analysis/sidekick-protocol.md`.

## Safety

- OLED compensation is part of panel maintenance. Do not disable it.
- The independent GET-only sweep is documented in
  [the post-build audit](../analysis/POST_BUILD_AUDIT.md). This does not validate
  compensation execution, firmware flashing or hardware writes.
- The OLED care execution path is disabled by default. `info` and frame
  generation run in dry-run mode unless `--send` is supplied.
- `execute-apcs` / `execute-aocs` additionally require
  `--allow-unverified-oled-execution --yes`.
- Only use this on hardware you own and can recover.

## Usage

```powershell
cd controller
python -m fo48u_controller info
python -m fo48u_controller execute-apcs
python -m fo48u_controller --send info
```

## GUI

```powershell
cd controller
python run_gui.py
```

The GUI is read-only by default. Enable "Connect to monitor" for readback and
"Enable write access" (plus confirmation) before any execution attempt.
Standard DDC/CI uses real Win32 Dxva2 calls. HID failures now raise instead of
becoming numeric zero readings. OLED/status decoding now validates headers,
length, result, selector echo and XOR before exposing values. Transaction
freshness and counter units remain unproved.
The GUI's AOCS execution action is unavailable and sends no command. Editable
sliders/profile values are settings, not proof of successful hardware reads.
## 32-bit helper

The installed RtHIDLib.dll is 32-bit. On 64-bit Python the GUI automatically uses controller/helper (a 32-bit .NET 8 helper). Build it with:

```powershell
dotnet publish controller/helper/helper.csproj -c Release -r win-x86 --self-contained false
```

Run this from the repository root. The transport requires helper protocol 2 and
rejects older published executables that can return invalid data on read failure.

## Independent read-only diagnostic

```powershell
python controller/live_probe.py --list
python controller/live_probe.py --monitor 0 --firmware-label F06 --output controller/live-probe.json
```

Check the monitor index before each run; generic descriptions require explicit
selection. The probe requests GET-VCP codes `00..FF`, records capabilities and
Win32 errors, compares replies with the knowledge base and atlas, and saves JSON
snapshots, including partial results on timeout. It never loads the HID helper
or exposes SET commands. Unadvertised or identical replies do not prove feature
support. Reports are ignored by Git. A complete GET sweep can take several
minutes; Ctrl+C preserves the completed results.

Set `--firmware-label` to the installed version reported by the owner or monitor
OSD; this is an annotation, not device verification. Omit it when unknown. The
current unit runs F06 (also confirmed by a validated E0/38 HID reply), while the static atlas/patch references
describe F08. Live F06 results do not validate F08 behavior.

Run the offline regressions from the repository root:

```powershell
python -m unittest discover -s controller -p test_live_probe.py -v
```

## Enforced status-only HID diagnostic

```powershell
dotnet publish controller/helper/helper.csproj -c Release -r win-x86 --self-contained false
python controller/live_hid_probe.py --firmware-label F06 --compare-vcp --output controller/live-hid-probe.json
python -m unittest discover -s controller -p 'test_*.py' -v
```

The helper itself blocks arbitrary I2C commands in `--read-only` mode. The probe
uses only byte-verified firmware, black-equalizer, gamma and OLED-counter GETs.
HID output reports carry those read requests; they are not settings writes.
Replies must pass framing, selector and checksum checks. Published F06 results
are in `analysis/observations/f06-hid-status-2026-10-24.json`. The probe has no
support for the offline F08 E0/FE control-hook prototype.

`--compare-vcp` also validates seven allowlisted standard GETs through HID.
The F06 E0 reply has vendor rather than standard shape and is correctly rejected;
the command returns nonzero and preserves that anomaly in JSON. Codes 6C/6E/70
are RGB video black levels, while the Sidekick gamma query is E0/07.

