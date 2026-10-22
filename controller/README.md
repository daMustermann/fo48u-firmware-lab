# FO48U host-side controller (experimental)

This is a minimal, safety-gated Python controller for the Gigabyte AORUS FO48U.
It wraps the byte-verified Realtek-HID frames documented in
`analysis/sidekick-protocol.md`.

## Safety

- OLED compensation is part of panel maintenance. Do not disable it.
- No command in this project has been hardware-validated.
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
PY

Currently implements the OLED care readback and execution frames. Standard DDC/CI
controls (brightness, contrast, input selection, etc.) are not bundled yet; add
them through `monitorcontrol` or a `Dxva2` wrapper. Contributions welcome.
PY
## 32-bit helper

The installed RtHIDLib.dll is 32-bit. On 64-bit Python the GUI automatically uses controller/helper (a 32-bit .NET 8 helper). Build it with:

`powershell
cd controller/helper
dotnet publish -c Release -r win-x86 --self-contained false
`

