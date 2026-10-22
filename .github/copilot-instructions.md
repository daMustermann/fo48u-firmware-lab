# Copilot guidance for FO48U research

Follow the public [AGENTS.md](../AGENTS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md) before making suggestions or edits. Ground each finding in the hash-verified stock F08 image, exact `bank:address`/bytes, and reproducible offline commands. Separate verified evidence from hypotheses and unknowns.

Keep all work offline and submit changes by pull request for review. Do not send any active monitor commands (including DDC/CI, VCP, USB/HID, or probes), flash firmware, generate modified firmware, or weaken OLED protection. Never use or publish local-only `AGENT.md`, secrets, or private captures.

## Advanced FO48U Architecture Shortcuts
See [AGENTS.md](../AGENTS.md#advanced-fo48u-architecture-shortcuts) for the four required strategies: (1) extended D8FE upstream searches, (2) ISR-forward tracing from bank_0 vectors, (3) universal cross-bank trampoline map, (4) host-side Sidekick protocol extraction.
