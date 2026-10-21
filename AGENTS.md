# AI agent guide (public)

Welcome, independent coding agents. This tracked `AGENTS.md` is the public onboarding guide for work on the Gigabyte AORUS FO48U firmware research repository. Read [README.md](README.md), [STATUS.md](STATUS.md), and [analysis/README.md](analysis/README.md) before proposing changes; use [analysis/panel_protection.md](analysis/panel_protection.md) for panel-care claims.

**Do not confuse these files:** `AGENTS.md` (plural) is public and belongs in Git. `AGENT.md` (singular) is an **ignored, local-only** notebook. Never commit, quote, copy, or depend on `AGENT.md` in a public contribution. Your checkout may not contain it.

## Safety and scope

- Work on **static analysis, offline reproducibility, and documentation only**. Do not send any commands to a physical monitor, including DDC/CI, VCP, USB/HID, service-menu actions, or other active probes. Do not run monitor-connected probe scripts, even if labeled read-only.
- **Never flash firmware or instruct others to flash research images.** No modified firmware has been hardware-validated, and there is no verified recovery procedure. Do not change or disable OLED protection on a device.
- Never add or distribute modified, generated, or unvalidated firmware binaries. The existing stock reference is the sole published firmware image; experimental outputs remain local and ignored.
- Do not publish secrets, credentials, personal identifiers, local machine paths, private notes, or raw captures containing sensitive data.
- Respect the scope of your assigned files, preserve unrelated changes, and do not commit or push unless specifically authorized for that task.

## Reference and evidence

- The source of truth is `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`, **2,031,616 bytes**, SHA-256 **`3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`**. Check the digest before interpreting offsets; a shared version label alone is insufficient.
- Use **`bank:address`** notation for bank-relative code addresses (for example, `13:CAA8`). Each bank is `0x10000` bytes; `file_offset = bank * 0x10000 + address`. Clearly label file offsets and XDATA addresses separately (for example, `XDATA 0xD12D`).
- Cite exact source bytes, paths, offsets, script commands, and observed output. Separate byte-verified findings, inferences, hypotheses, and unresolved behavior. Negative findings also need reproducible evidence.
- Keep APCS (**4 h**), AOCS (**1,500 h**), and TSS (**36 h reminder**) distinct. These are **static code thresholds**, not measured hardware intervals. Manual activation, input framing, and modified-image safety remain unverified; see `STATUS.md`.

## Contribution workflow

1. **Fork the repository**, make a topic branch on your fork, and submit a **pull request** to upstream. Do not push directly to upstream branches or merge your own contribution.
2. Keep changes focused and reviewable. Record the stock hash, bank:address references, original bytes, reproduction commands, output, and confidence limits in the PR.
3. Run the **offline acceptance commands in [CONTRIBUTING.md](CONTRIBUTING.md)** (taken from `README.md`), and report results and unavailable dependencies. Use builders **only with `--verify`** for acceptance; never generate firmware as part of CI or a PR.
4. Check the diff for secrets, accidental binaries, ignored `AGENT.md`, and unrelated changes before opening the PR. If evidence is insufficient, document the question instead of asserting a working feature.
