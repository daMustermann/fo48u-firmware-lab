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
becoming numeric zero readings. OLED decoding still lacks validated response
headers, selector echo, freshness and checksum; those results remain provisional.
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
current unit runs F06 (owner-reported), while the static atlas/patch references
describe F08. Live F06 results do not validate F08 behavior.

Run the offline regressions from the repository root:

```powershell
python -m unittest discover -s controller -p test_live_probe.py -v
```

