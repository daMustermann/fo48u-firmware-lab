## What changed?

Describe the narrow research question or documentation/code correction, and link related issues.

## Evidence and reproduction

- **Reference:** stock FO48U F08 (2022-11-15), SHA-256 `3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f` (or explain a different input).
- **Locations:** `bank:address` (for example, `13:CAA8`), exact original bytes and relevant file/XDATA offsets, where applicable.
- **Reproduce:** commands, inputs, key output, and tool versions needed for an independent offline check.
- **Confidence:** distinguish byte-verified observations from interpretation, hypotheses, counterevidence, and unresolved paths.

## Checks run

List the offline commands and their results. Explain skipped checks and dependencies (for example, radare2) rather than marking them as passed.

## Safety and submission checklist

- [ ] Work is offline-only. No active monitor commands, DDC/CI/VCP/USB/HID probes, or flashing were used.
- [ ] No generated/modified firmware images, secrets, private notes (`AGENT.md`), or identifying captures are included.
- [ ] Claims about physical inputs, refresh behavior, and recovery are limited to the evidence; unverified behavior is labeled clearly.
- [ ] Diff is focused and ready for review under [CONTRIBUTING.md](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).
