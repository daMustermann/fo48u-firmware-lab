# Calling independent AI agents and reverse engineers

**The [FO48U Firmware Lab](https://github.com/daMustermann/fo48u-firmware-lab) is open for evidence-driven contributions.**

We're trying to map the Gigabyte AORUS FO48U's Realtek RTD2718 / banked-8051 firmware, especially the missing links between the joystick, command ingress, and OLED care. Human researchers, multi-agent systems, code assistants, and their operators can all contribute. **Bring a finding; leave a pull request.**

## Send your agent this task

Copy this into your preferred coding agent (or share the page with someone running one):

> Contribute independently to https://github.com/daMustermann/fo48u-firmware-lab. First read `AGENTS.md`, `CONTRIBUTING.md`, and `STATUS.md`. Choose an *open, unclaimed* `help wanted` issue, announce the scope in an issue comment, and reproduce the relevant finding on the original hash-identified F08 image. Investigate using only offline firmware disassembly and static scripts. Cite exact `bank:address`, source bytes, counterevidence and commands another person can run. Separate verified bytes from inference and hypotheses. Fork the repository, create a topic branch, and submit **one focused pull request** referencing the issue; never push directly to `main`. Do not transmit commands to a monitor, flash firmware, generate patched release images or disable OLED protections. If the route is unresolved, document the gap precisely rather than guessing. Include the nine offline checks from `CONTRIBUTING.md`, or explain any unavailable dependency.

## Pick a research mission

| Mission | Issue | Useful result |
| :-- | :-- | :-- |
| Decode where protocol bytes enter `CFDA..CFDF` | [#1](https://github.com/daMustermann/fo48u-firmware-lab/issues/1) | Reproducible writer/caller trace with packet-boundary evidence |
| Trace genuine joystick selection for APCS/AOCS | [#2](https://github.com/daMustermann/fo48u-firmware-lab/issues/2) | Proven input path or a documented missing edge |
| Check bank-12 `0x80/0x82` dispatch and guards | [#3](https://github.com/daMustermann/fo48u-firmware-lab/issues/3) | Cross-bank path, original bytes, tested operand semantics |
| Reproduce F08 static audits on a clean checkout | [#4](https://github.com/daMustermann/fo48u-firmware-lab/issues/4) | Small cross-platform audit or documentation PR |
| Make REA + Binwalk instructions portable on WSL2 | [#8](https://github.com/daMustermann/fo48u-firmware-lab/issues/8) | Beginner-friendly offline tooling documentation PR |
| Research official recovery evidence | [#5](https://github.com/daMustermann/fo48u-firmware-lab/issues/5) | Primary-source documentation with clear safety limits |

Have a different hypothesis or tool? Start in the [community discussion](https://github.com/daMustermann/fo48u-firmware-lab/discussions/6) and propose a bounded issue. We review **small, independently verifiable PRs**; a careful negative result is useful too.

## For agent operators

Make sure the agent can access its own fork and open a PR, and review the proposed diff before submission. [Agent playbook](AGENTS.md) · [Evidence standard](CONTRIBUTING.md) · [Research status](STATUS.md) · [PRs](https://github.com/daMustermann/fo48u-firmware-lab/pulls).

No cloud agent starts automatically when this page is viewed. An operator must invoke or assign their agent. Hardware writes and unvalidated firmware flashing are outside the project.
