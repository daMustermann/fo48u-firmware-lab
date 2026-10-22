# Claude Code: FO48U research

Follow [AGENTS.md](AGENTS.md) as the canonical instructions and [CONTRIBUTING.md](CONTRIBUTING.md) for the PR workflow. Pick an open [research issue](https://github.com/daMustermann/fo48u-firmware-lab/issues), verify findings against the stock F08 bytes, then propose a focused pull request.

All hardware operations are out of scope: **offline and passive/read-only analysis only**. Never send Set-VCP commands, flash firmware, or present a speculative unlock as verified.

## Advanced FO48U Architecture Shortcuts
See [AGENTS.md](AGENTS.md#advanced-fo48u-architecture-shortcuts) for the four required strategies: (1) extended D8FE upstream searches, (2) ISR-forward tracing from bank_0 vectors, (3) universal cross-bank trampoline map, (4) host-side Sidekick protocol extraction.
