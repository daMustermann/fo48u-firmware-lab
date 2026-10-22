# WSL2 Ubuntu: reproducible offline FO48U F08 research

This guide supports contributor [Issue #8](../../../issues/8). All **research commands** below inspect **local files only**. They do not contact a monitor, issue DDC/CI or VCP requests, access USB/HID devices, change OLED-care settings, flash firmware, or generate patched firmware. Do not run monitor-connected probes, including scripts described as read-only. Read [AGENTS.md](../AGENTS.md), [README.md](../README.md), [STATUS.md](../STATUS.md), [analysis/README.md](../analysis/README.md), and [CONTRIBUTING.md](../CONTRIBUTING.md) first.

## Tested environment and prerequisites

Verified on **2026-10-21** in an existing **Ubuntu 26.04.1 LTS** WSL2 distribution (Linux `6.18.54.1-microsoft-standard-WSL2`), using Python **3.14.4**, radare2 **6.0.7**, and Binwalk **3.1.0**. The repository was accessed through a WSL-mounted Windows drive; no special fixed mount path was needed. Commands below are intended to run **inside Ubuntu Bash**, from the repository root, unless marked PowerShell.

From **Windows PowerShell**, inspect your installed distro and start its shell:

```powershell
wsl.exe --list --verbose
wsl.exe -d Ubuntu-26.04 -- bash
```

Replace `Ubuntu-26.04` with the distro name printed on your machine. Inside Ubuntu, `pwd` must point to this repository. A Windows checkout may appear below `/mnt/<drive>/...`; a checkout created within Linux has its normal Linux path. Use your own location rather than copying a machine-specific path. Check the checkout with `test -f AGENTS.md && test -f analysis/README.md && test -f STATUS.md`.

On the tested Ubuntu, the following tools were available:

```bash
python3 --version
r2 -v
command -v sha256sum
command -v xxd
command -v binwalk
apt-cache policy python3 radare2 binwalk xxd
```

For a distro missing packages, Ubuntu's package names shown by `apt-cache policy` can be installed using `sudo apt update` and `sudo apt install python3 radare2 binwalk xxd`. **This fresh-install procedure was not run as part of this verification**. Package availability and versions vary by Ubuntu release. The distro's `binwalk` package was **2.4.3** in this test; the `binwalk` command on `PATH` resolved to a separately installed **3.1.0**, so check the executable you are actually running. Package installation may need network access; subsequent research commands do not.

## Confirm the exact stock image before reading offsets

Work from the repository root. The following Bash check was verified against the unmodified source image:

```bash
FW=firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin
EXPECTED=3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f
test "$(stat -c %s "$FW")" -eq 2031616
printf '%s  %s\n' "$EXPECTED" "$FW" | sha256sum -c -
```

Observed result: `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin: OK`, with a size of **2,031,616 bytes** (`0x1F0000`, 31 banks of 64 KiB). **Stop if either check fails.** An F08 label without this hash does not identify the reference used for these findings. `sha256sum -c -` reads the expected digest from stdin; it does not write to the firmware.

## Read bytes and disassemble without device I/O

Bank identifiers in this repository are **decimal** (`13` means bank thirteen), while the four-digit address portion is hexadecimal. Use `file_offset = bank * 0x10000 + address`:

```text
13:CAA8 (bank-relative 8051 code) -> 13 * 0x10000 + 0xCAA8 = file offset 0x0DCAA8
```

This detail matters: `0x13CAA8` would point into **bank 19**, not bank 13. The verified read of the **original** F08 bytes at `13:CAA8` is:

```bash
xxd -s 0xDCAA8 -l 16 "$FW"
r2 -q -n -a 8051 -b 8 -c "px 16 @ 0xdcaa8" "$FW"
r2 -q -n -a 8051 -b 8 -c "pd 5 @ 0xdcaa8" "$FW"
```

The `xxd` line begins:

```text
000dcaa8: 9404 ee94 0040 0e90 d12d e0ff 20e0 0644
```

The first two original bytes are **`94 04`**, consistent with the static APCS 4-hour comparison described in [panel_protection.md](../analysis/panel_protection.md). `r2` was tested against the same file offset with the `8051` architecture and 8-bit setting; its hex view showed the same sixteen bytes, and disassembly started with **`subb a, #0x04`**, `mov a, r6`, `subb a, #0x00`, `jc 0xcabd`, and `mov dptr, #0xd12d`. These commands read the supplied file and print to the terminal. radare2 does **not** automatically resolve the firmware's bank-switching control flow from this raw-file view. For code-path conclusions, account for the common bank-switch routine and confirm references in the repository audits. Distinguish code locations such as `13:CAA8`, **file offsets** such as `0x0DCAA8`, and **XDATA** addresses such as `0xD12D`.

## Binwalk: treat matches as leads

Only scan the hash-verified stock image. These invocations were tested; neither extracts files nor writes image variants:

```bash
binwalk "$FW"
binwalk -a "$FW"
```

To run the existing REA firmware-region command when the REA CLI is installed, resolve both executable paths on your own system. This is an **optional, unverified REA integration step**; the standalone `binwalk` scans above are the tested route:

```bash
BINWALK_BIN="$(type -P binwalk || true)"
REA_BIN="$(type -P rea || true)"
test -n "$BINWALK_BIN" || { echo "Binwalk is unavailable on PATH" >&2; exit 1; }
if test -n "$REA_BIN"; then
  REA_BINWALK_COMMAND="$(readlink -f "$BINWALK_BIN")" \
    "$REA_BIN" inspect-firmware-regions "$FW" --format json
else
  echo "REA CLI unavailable; use the standalone Binwalk scan" >&2
fi
```

On a working Linux/WSL2 installation, setting `REA_BINWALK_COMMAND` to a Linux `binwalk` on `PATH` lets `rea inspect-firmware-regions` run (it was verified in this environment with `binwalk 3.1.0`). A missing or misconfigured REA/Binwalk pair can still fall back to the standalone `binwalk` scans above; no REA result is required to reproduce the Python audits.

Observed results differ by Binwalk version and scan mode:

| Executable / invocation | Observed on stock F08 | What it establishes |
| --- | --- | --- |
| Binwalk 3.1.0, default `binwalk` | `Analyzed 1 file for 85 file signatures (187 magic patterns)`; no match rows | No default-mode signature hit under this version and ruleset. |
| Binwalk 3.1.0, `-a` / `--search-all` | Candidate **GPG signed file** at file offset `0x5A3F5`, reported length **9 bytes** | A short *signature candidate*, not proof of a signed or extractable payload. |
| Distro Binwalk 2.4.3 (`/usr/bin/binwalk`) | Candidate **ESP32 image** signatures at `0xD9751` and `0xDA48A` | Other heuristic candidates; no verification of embedded ESP images. |

Do not infer firmware structure, valid payloads, or hardware functionality from signature matches alone. Avoid `-e`/`--extract`, recursive extraction, or any operation that emits research firmware or payload files. A REA firmware-region MCP inspection was also attempted, but the integration reported that it required Linux and a configured absolute `REA_BINWALK_COMMAND`; **no REA scan result was obtained in this session**. The WSL-native Binwalk commands above supply the tested fallback.

## Repository offline acceptance checks

Run these from the same Ubuntu shell after verifying the SHA-256. The first command needs `r2` on `PATH`. The `-B` flag prevents Python from writing bytecode cache files; builder calls are intentionally restricted to `--verify`:

```bash
python3 -B analysis/audit_8051_opcodes.py
python3 -B analysis/audit_menu_reachability.py
python3 -B analysis/audit_service_dispatch.py
python3 -B analysis/audit_refresh_command_table.py
python3 -B analysis/audit_ddcci_ingress.py
python3 -B analysis/audit_packet_field_usage.py
python3 -B analysis/audit_packet_route_families.py
python3 -B analysis/build_variant.py --verify
python3 -B analysis/build_custom.py --verify
```

**Results on the tested WSL2 Ubuntu:** all nine commands exited **0** against the stock image. The opcode audit printed **`0 / 256 opcode lengths disagree`**. Menu, service-dispatch, command-table, receive-buffer, packet-field, and packet-family audits reported their expected PASS findings and limits. Both builder `--verify` commands finished with **`all patch sites match`** (the custom verifier says **`all patch sites match the original image`**). Their output is a byte check, **not** a generated or hardware-tested firmware image. Do not run image-emitting builder modes, firmware patch generation, or hardware-facing scripts.

## What a reproducible finding must report

Record the stock image's filename, **SHA-256 and size**; Ubuntu, Python, radare2 and Binwalk versions; exact commands and concise terminal output; original bytes with **`bank:address`** and separately labeled file offsets or XDATA; and a confidence level. Separate **byte-verified results**, **code interpretation**, **signature hypotheses**, and **unresolved hardware behavior**. Negative results are scoped to the particular tool, ruleset, and command used, rather than proof that a feature or data structure does not exist.

APCS **4 h**, AOCS **1,500 h**, and TSS **36 h reminder** are **distinct static thresholds**, not measured real-device intervals. Neither visible menu entries nor guarded command handlers prove a joystick selection path, host command framing, or successful manual OLED refresh. Those questions remain open in [STATUS.md](../STATUS.md). Keep OLED protection enabled; no experimental firmware has a validated recovery route.

Review the single intended documentation change before submitting through a contributor fork and pull request. Keep ignored local notebooks (especially `AGENT.md`), personal paths, secrets, raw device captures, and generated binaries out of contributions. Never send research commands to an attached monitor.
