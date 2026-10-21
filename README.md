<div align="center">

<img src="assets/fo48u-banner.svg" alt="FO48U firmware research: OLED panel-care circuitry" width="100%">

<br>

**Reverse engineering the Gigabyte AORUS FO48U, one verified byte at a time.**

[![Platform](https://img.shields.io/badge/MONITOR-AORUS%20FO48U-141d31?labelColor=12192a)](https://www.gigabyte.com/Monitor/AORUS-FO48U)
![Firmware](https://img.shields.io/badge/IMAGE-F08%20%2F%202021115-1d4c62)
![Analysis](https://img.shields.io/badge/ANALYSIS-STATIC%20VERIFIED-205e5b)
![Hardware](https://img.shields.io/badge/MODIFIED%20FLASH-UNTESTED-8f3958)
[![License](https://img.shields.io/badge/CODE-MIT-493c73)](LICENSE)

[**Findings**](STATUS.md) · [**Technical analysis**](analysis/README.md) · [**Panel-care internals**](analysis/panel_protection.md) · [**Join the agent lab**](CONTRIBUTING.md) · [**Open tasks**](../../issues)

</div>

---

## 🤖 Calling all reverse-engineering agents

**Human researchers, autonomous coding agents and their operators are welcome.** Help unravel the FO48U's hidden service paths with **reproducible, byte-backed evidence**. Bring Ghidra, radare2, Python, REA or a fresh perspective. Every contribution arrives as a **pull request**, where it can be checked before publication.

[![AI agents welcome](https://img.shields.io/badge/AI%20AGENTS-WELCOME-2b9e91?style=for-the-badge)](AGENTS.md) [![Pick a task](https://img.shields.io/badge/OPEN%20RESEARCH-HELP%20WANTED-4258af?style=for-the-badge)](../../issues?q=is%3Aissue+is%3Aopen) [![Contribute via PR](https://img.shields.io/badge/CONTRIBUTE-PULL%20REQUESTS-893f9c?style=for-the-badge)](CONTRIBUTING.md)

| Research mission | What would move the investigation forward? |
| :-- | :-- |
| **📡 Protocol archaeology** | Find the incoming packet boundary and writer path for `CFDA..CFDF`. |
| **🎮 Joystick to service action** | Establish whether a real selection event reaches bank-9 actions `23/24`. |
| **🧩 Cross-bank execution** | Trace bank-12 command `80/82` guards to actual request-bit changes. |
| **🔬 Independent verification** | Reproduce byte-level findings; propose narrowly scoped, read-only audits. |

**Start here:** [Agent playbook](AGENTS.md) · [Contribution guide](CONTRIBUTING.md) · [Research backlog](../../issues?q=is%3Aissue+is%3Aopen) · [Evidence baseline](STATUS.md). Claim an issue in a comment, investigate on your own branch, and submit a focused PR with proof and commands to reproduce it. If using an AI agent, give it the issue URL plus [`AGENTS.md`](AGENTS.md).

> [!CAUTION]
> This lab uses **offline analysis and passive/read-only observations**. No unsolicited monitor writes, Set-VCP commands, firmware flashing, or claims of a working unlock. Protect the OLED's compensation routines.

---

## Inside the FO48U

A practical, source-backed investigation of the **48-inch 4K 120 Hz OLED monitor**, its Realtek **RTD2718** scaler, banked **8051** firmware, service-menu logic and pixel-care scheduling. The reference file identifies itself as **F08 / 2022-11-15**.

> [!IMPORTANT]
> **Research release.** The repository contains the unmodified reference image, static analysis and reproducible scripts. **There is no validated modified firmware for flashing, and no verified hardware recovery procedure.** Never flash experimental builds based on these notes.

### The three timers

The original F08 code contains independent conditions for OLED upkeep:

| Mechanism | Static F08 threshold | Evidence | Purpose |
| :-- | --: | :-- | :-- |
| **APCS** | **4 h** | `13:CAA8` | Automatic short compensation request after accumulated use |
| **AOCS** | **1,500 h** | `13:CAD3` | Longer compensation request at scheduled usage intervals |
| **TSS** | **36 h** | `13:CB1A` | Panel-care reminder threshold since the last APCS |

These are **firmware code thresholds**, not verified measurements of how often the physical monitor actually executes each action. **TSS is not the APCS interval.** Automatic protections should remain enabled.

```text
                PANEL-USE COUNTERS
                         │
                 BANK 13 SCHEDULER
              ┌──────────┼──────────┐
          APCS 4h     AOCS 1500h   TSS 36h
              │           │          │
              └──────┬────┘     reminder logic
                     ▼
           XDATA D12D request bits
                bit 0 / bit 1
                     │
                BANK 18
             compensation paths
```

### Manual refresh: what the code establishes

- **Service-page data exists.** The bank-9 action table includes APCS (item **23**) and AOCS (item **24**), dispatched to `9:A14C` and `9:A1C0`.
- **The real request flags exist.** `0xD12D` bit 0 requests APCS; bit 1 requests AOCS.
- **Dedicated command handlers exist.** Bank-12 entries `68A9` / `68B9` require command operand `CFDE == 2`. The surrounding table uses `CFDB = E0` and `CFDA = 03`.
- **The complete physical-input path is unresolved.** Neither a reliable joystick-driven selection route nor the incoming packet framing has been established. The `9:E0E2` call path only handles action IDs **11/14**, so it cannot establish manual APCS/AOCS activation.

**Result:** the code is mapped well enough to guide deeper investigation, but it does **not** demonstrate a working manual-refresh unlock. No potentially destructive host commands have been sent during the documented probes.

## Reference firmware

| Property | Observed value |
| :-- | :-- |
| File | `FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin` |
| Location | [`firmware/F08-20221115/`](firmware/F08-20221115/) |
| Size | **2,031,616 B** (`0x1F0000`) |
| Banks | **31 × 64 KiB**; code banks 0–19 |
| MD5 | `d4324c6c88abea48b1ee896f7e14ee9f` |
| SHA-256 | `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f` |
| Architecture | Realtek RTD2718 / banked 8051 |

The hash identifies **this particular binary**, not every community file bearing the F08 label. Firmware dates and public-release status for other versions have not been independently established here.

### Reproduce the static checks

With Python 3 and the original reference image available:

```bash
python analysis/audit_8051_opcodes.py
python analysis/audit_menu_reachability.py
python analysis/audit_service_dispatch.py
python analysis/audit_refresh_command_table.py
python analysis/audit_ddcci_ingress.py
python analysis/audit_packet_field_usage.py
python analysis/audit_packet_route_families.py
python analysis/build_variant.py --verify
python analysis/build_custom.py --verify
```

Use `python analysis/osd_strings.py` for OSD string-table research. More disassembly, byte offsets and call-path evidence: **[analysis/README.md](analysis/README.md)**.

## Explore the repository

| Path | Contents |
| :-- | :-- |
| [`STATUS.md`](STATUS.md) | Verified observations, limits, open investigations |
| [`analysis/README.md`](analysis/README.md) | Architecture, menu dispatch, host protocols and research workflow |
| [`analysis/panel_protection.md`](analysis/panel_protection.md) | APCS/AOCS/TSS scheduler and request/consumer mapping |
| [`analysis/`](analysis/) | Byte-level audit scripts, extracted banks and disassembly |
| [`firmware/F08-20221115/`](firmware/F08-20221115/) | Hash-identified reference firmware |
| [`firmware/PATCHED/README.md`](firmware/PATCHED/README.md) | Offline research output policy |
| [`osd-sidekick/`](osd-sidekick/) | Archived installer reference material |

## Open research questions

**Which physical input selects a service action?** **Where are `CFDA..CFDF` populated?** **Can the exact manufacturer command frame be proven through passive captures?** The priority is establishing these paths through disassembly and read-only tracing, then evaluating safety and recovery separately.

> **Unofficial community research.** Not affiliated with Gigabyte, Realtek or LG Display. Reverse-engineering findings and tools are offered as-is under the repository's [MIT license](LICENSE). Modified firmware may permanently damage the monitor.
