# Gemini CLI: FO48U research

Use [AGENTS.md](AGENTS.md) for the research rules and [CONTRIBUTING.md](CONTRIBUTING.md) for reproducibility and the mandatory pull-request workflow. Choose a scoped [open issue](https://github.com/daMustermann/fo48u-firmware-lab/issues), reference exact bank-relative addresses and evidence, and submit a PR.

Work **offline/read-only**. No monitor writes, Set-VCP tests, firmware flashing, speculative protocol commands or unverified binary releases.

## Advanced FO48U Architecture Shortcuts
See [AGENTS.md](AGENTS.md#advanced-fo48u-architecture-shortcuts) for the four required strategies: (1) extended D8FE upstream searches, (2) ISR-forward tracing from bank_0 vectors, (3) universal cross-bank trampoline map, (4) host-side Sidekick protocol extraction.
