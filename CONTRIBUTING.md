# Contributing to FO48U firmware research

Independent researchers and AI coding agents are welcome. Contributions should make an **offline finding easier to reproduce or a limitation clearer to understand**. Start with [README.md](README.md), [STATUS.md](STATUS.md), and [analysis/README.md](analysis/README.md). The public agent rules are in [AGENTS.md](AGENTS.md).

## Fork, branch, pull request

1. **Fork** the upstream repository to your own account, then clone your fork.
2. Create a **topic branch** for one focused change. Make commits on your fork's branch.
3. Run the checks below, review your diff, and **open a pull request** against upstream. All contributions go through PR review; do not push to upstream branches or merge directly.

Good contributions include corrected disassembly, independently checked cross-references, clearer evidence trails, offline audit improvements, and documented dead ends. Limit work to static analysis and reproducible offline checks. **Do not send any command or probe to a connected monitor**, including DDC/CI or VCP reads/writes, USB/HID traffic, and service-menu actions. **Never flash, generate release firmware, or recommend flashing** experimental builds. There is no hardware-validated modification or verified recovery path.

## Evidence required in each PR

- **Reference image:** identify `F08 / 2022-11-15`, source file `firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin`, size **2,031,616 bytes**, and verified SHA-256 **`3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`**. If your source differs, stop and identify it as a separate, unverified image.
- **Locations and bytes:** write bank-relative references as **`bank:address`** (for example, `13:CAA8`), with `file_offset = bank * 0x10000 + address`. Identify absolute file offsets and XDATA (for example, `XDATA 0xD12D`) explicitly. Show original bytes, relevant disassembly/call path, and any expected/observed differences.
- **Reproduction:** include exact offline commands, inputs, environment/tool versions where material, and concise output or test results. Explain how another contributor can independently check the claim.
- **Confidence and limits:** distinguish observed bytes from interpretations, state unknowns and counterevidence, and label hardware behavior **unverified** unless independently established. Do not claim that a service-menu entry proves physical selection or that a handler implies a valid host packet.

The known static scheduler thresholds are APCS **4 h**, AOCS **1,500 h**, and TSS **36 h**. TSS is a reminder threshold, **not** the APCS interval. These numbers do not prove runtime frequency on a real monitor.

## Offline acceptance checks

Use Python 3 and the hash-verified stock image. The first check also needs **radare2** (`r2`) on `PATH`. From the repository root, run the acceptance commands documented in `README.md`:

```bash
python analysis/verify_facts.py
python analysis/verify_menu_patch.py
python analysis/build_variant.py --verify
python analysis/build_custom.py --verify
```

These audit and `--verify` commands inspect offline data. **Do not run builder modes that emit images or monitor-facing scripts.** State each check's outcome in the PR; if a dependency is missing, state that instead of claiming it passed. Also run `git diff --check` and `git status --short` to review what will be submitted.

## Publication hygiene

Do not commit credentials, tokens, private captures, host-specific paths, or identifying device data. **`AGENTS.md` (plural) is tracked and public; `AGENT.md` (singular) is an ignored local-only file.** Do not stage or quote the latter. Do not submit new/modified/generated/unvalidated firmware binaries, including PR attachments or release assets. The existing unmodified stock reference is the only published firmware; `firmware/PATCHED/` contains local offline experiments excluded from Git. Use text evidence, scripts, and hashes to make proposed research independently reviewable.
