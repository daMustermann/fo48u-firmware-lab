# Safety and completeness audit — 2026-10-24

**Release verdict: FAIL / DO NOT FLASH.** Engineering fixes below pass their
local checks. Boot authentication, physical menu selection, code-cave ownership,
maximum interrupt stack depth, end-to-end patched execution and recovery remain
unproved. An offline prototype is not a flashable release.

Static reference: F08 / 2022-11-15, 2,031,616 bytes, SHA-256
`3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`.
Live monitor: **F06**, initially owner-reported, now independently returned by
validated Sidekick status query E0/38 (`0x4606`, ASCII F plus numeric 06).
No F06 binary has been supplied for static comparison. F06 live responses do
not validate F08 patch addresses or behavior.

## Task outcomes

| Requested work | Current result |
|---|---|
| Carry-safe AOCS gate | Resolved locally: `C3 74 02`; 131,072 interpreted operand/carry/flag combinations |
| Generic patch length/bank/range/overlap/output guards | Implemented and regression-tested |
| Reassembly with absent bank files 20–30 | Implemented: hash-verified stock tail preserved; output is exactly 0x1F0000 bytes |
| Exact Sidekick checksum calculator | Host per-bank CRC-8 identified and implemented; vendor routine independently emulated; scaler boot checks remain open |
| Actual service item selector | Byte-verified page/ID/flag selectors added to menu verifier; deliberate joystick event still unproved |
| Distinct full-control implementation | Real E0/FE allowlisted offline hook prototype; 133,376 interpreter cases; not executed on hardware |
| Read-only HID telemetry | Enforced helper allowlist built and run on F06; valid framed/checksummed replies |
| Complete flash/brick/stack safety | Not established; release remains blocked |

## Carry fix and byte tables

The accepted stock AOCS comparison at `12:68BD` is `B4 02 14`:
`CJNE A,#02,68D4`, with A=2 and CY=0 on equality. Both builders now use
`C3 74 02` (`CLR C; MOV A,#02`), reproducing that accepted state exactly.
`12:68C0` loads DPTR=D12D and `12:68C3` reloads A before ORL/MOVX. There is no
requirement for A=0 at the continuation. This fixes the old `E4 00 00` sequence,
which preserved incoming carry.

The call stubs `0:2C50` and `0:2B9C` target `18:F5B9` and `18:FC60` via shared
stub `0:0CC6` and selector `0:5048` (bank 18). The first routine explicitly
clears carry before its rotate test. The fix does not depend on that downstream
clobber: state equivalence is checked before the first call for both incoming
carries, all 256 operands and all 256 D12D values.

The APCS patch stays `12:68AD 64 02 -> E4 00`. The gate-only unlock still changes
five bytes. The complete [byte tables](PATCH_BYTE_TABLES.md) include every patch
byte, Keil pointer data explicitly distinguished from instructions, relative
branch targets, surrounding disassembly and per-bank CRCs. They are generated
from RAM using `oplen.OPLEN` and independent radare2 disassembly.

## Validated patch/reassembly scaffold

`analysis/patch.py` checks full-image size/SHA-256 before extracting or applying
patches. Input banks must match the selected stock slice. Every JSON record must
identify that same bank, provide matching stock bytes and have equal nonzero
old/new lengths; negative/out-of-bank, boolean integer fields and overlaps are
rejected before mutation. Output is separate, exclusively created, and cannot
resolve to any stock bank, source image, input file or existing output.

Reassembly overlays exactly code banks 0–19 onto a verified full image and
preserves banks 20–30 directly. Missing data-bank files are therefore irrelevant.
No firmware image was emitted during implementation or verification. File-writing
CLI modes require an explicit offline-research flag. Arbitrary patch JSON still
requires its own instruction and semantic audit.

[Host checksum evidence and algorithm](sidekick-checksum.md): installed RFlash
uses CRC-8/poly07/init00/no reflection/xorout00 over complete 64 KiB banks and
compares it with a scaler CRC-register result. This is not a whole-image CRC32,
sum16, stored FFFE/FFFF footer, or proof of all boot validation. The exact native
routine matched the Python calculator in isolated emulation on zero, incrementing
and stock-bank test vectors. None of the inspected ISP register commands were
sent to hardware.

## Menu selector and full-control prototype

The true service selectors are `9:E481` (page CODE pointer), `9:E4B8` (item ID)
and `9:E4C7` (item flag). Page 3 includes IDs 23–28; APCS/AOCS records are
`9:9775`/`9:9777`, dispatched by the LJMP records at `9:9835`/`9:9838` to
`9:A14C`/`9:A1C0`. `verify_menu_patch.py` checks these bytes and all 30 page
members. Enumeration can reach 23/24 without a deliberate selection event.
The existing UI-only E0E2 prototype remains inert for those items; hooking the
shared enumeration call could request unsolicited compensation. Its emission
continues to require the existing explicit unreachable-prototype override.

`full-control` now adds a distinct, bounded **E0/FE prototype**, implemented by
`analysis/control_hook.py`. FE is absent from both fully decoded stock bank-12
GET and SET tables. Their default pointer words at `12:5520` and `12:5EB3` route
to `12:FF60` and `12:FF00`, respectively. The corresponding ranges are byte-verified
FF-filled. Absence of a direct table assignment does not prove that every
undocumented external sender or indirect code path is absent.

The prototype changes 189 bytes overall, including the five gate-unlock bytes.
It deliberately does not add unrestricted writes or compensation triggers:

- GET permits byte reads only at D12D, D13D, D13E and D8FE. Its frame must have
  header 51, length 85 and a valid XOR. Only the conditional prototype buffer
  layout is established; no host sender is supplied or used.
- SET permits only D8FE values 00/10/20, requires header 51, length 86 and valid
  XOR, and rejects every other address/value. D8FE is a receive-buffer routing
  selector, not a demonstrated joystick or protection-execution event.
- These correspond internally to CFDC=FE, CFDD/CFDE=address high/low, and CFDF=value
  for SET. Unsupported commands tail-jump to the original defaults.
- `control_hook.control_request` can construct these logical frames offline,
  with the same allowlists and XOR. It has no transport. The enforced F06 probe
  refuses selector FE; no prototype frame was sent to the monitor.
- GET fills the existing reply fields then tail-jumps to stock checksum/send
  code at `12:5D5A`. `0:258A -> 10:FD8F` XORs the length-framed response with seed
  50. SET has one RET per terminal path. No injected PUSH/POP/LCALL/SP write
  occurs; the existing return address is consumed once or passed to the stock
  tail. The bounded interpreter checks reads, writes, termination and local
  stack effects over all 65,536 addresses, all values and all command IDs.

This is functional offline code, distinct from the unlock alias. It is not a
claim of safe flashing, physical transport ingress or unused code-cave ownership.
**No FE command was sent to stock F06.**

## Read-only F06 hardware evidence

`controller/live_hid_probe.py` launches the helper with `--read-only`. The helper
itself rejects arbitrary I2C read/write commands in that mode and constructs only
allowlisted GET frames: `51 83 01 E0 selector XOR`, padded to 36 bytes. In
particular E0/80 and E0/82 use GET opcode 01, not compensation SET opcode 03.
The helper was rebuilt using the requested `dotnet publish` command. Python
helper responses now also have a five-second deadline.

The [sanitized HID observation](observations/f06-hid-status-2026-10-24.json)
contains eight vendor-status replies, seven standard GET attempts through HID,
and a contemporaneous seven-code Dxva2 comparison. The owner-local report remains ignored by Git. Discovery and parser
validation also used an initial firmware query and an earlier six-status pass;
23 vendor-status queries total were sent during this follow-up, plus seven
standard GETs through HID and seven GETs through Dxva2. No settings, EEPROM,
reset, compensation, ISP or flash operation was performed.

| Selector | Decoded value | Meaning / limit |
|---|---:|---|
| E0/38 | 0x4606 | F06 revision returned by the device |
| E0/02 | 10 | Sidekick black equalizer query |
| E0/07 | 3 | Gamma raw value; Sidekick masks the low nibble |
| E0/7F | 55 | Panel-hours readout |
| E0/80 | 1 | APCS status field; no setting changed |
| E0/81 | 56 | APCS time/count field; units not independently established |
| E0/82 | 0 | AOCS status field; does not by itself establish disabled protection |
| E0/83 | 0 | AOCS time/count field |

The reply parser requires a 36-byte bridge buffer, `6E 88 02` frame header,
success result, E0 family, exact selector echo and XOR(frame)=50 before exposing
a number. It validates the 11 framed bytes; buffer bytes beyond that can contain
repeated bridge data. Without a transaction ID it cannot prove freshness.

The wider GUI still has no selected-monitor binding for writes, and its busy
worker can skip refresh requests. Editable sliders/profiles are not validated
telemetry. Raw controller I2C APIs remain available outside enforced probe mode;
this audit does not certify general GUI/CLI hardware writes.

The installed Sidekick CIL independently identifies firmware query E0/38
(`GetCurrentFirmwareVer`, token 060001C9), black equalizer E0/02 (0600018A) and
gamma E0/07 (0600018E). REA Evidence and executable hash are recorded in the
checksum notes. Successful replies establish these queries on this F06 unit,
not universal compatibility of every Sidekick command.

## Identical standard DDC replies

The comparison reproduced 10/12/6C/6E/70 = 50/100 and DF/E0 = 0202/FFFF through
Dxva2. Direct HID-bridged GETs for 10/12/6C/6E/70 returned valid checksums and the
correct echoed code, each with value 50/max100. These are genuine framed replies,
not a synthetic fallback inserted by our controller.

The previous labels were incorrect: **6C/6E/70 are red/green/blue video black
levels**, not black equalizer and gamma. DF is **MCCS/VCP version**, not the Fxx
firmware revision. The [maintained ddcutil feature definitions](https://www.ddcutil.com/vcpinfo_output/)
and [example readouts](https://www.ddcutil.com/getvcp_known_u3011_output/) document
these standard meanings. The controller/GUI labels and knowledge base have been
corrected. Equal RGB black levels at 50 and brightness/contrast also at 50 do
not establish aliasing; independent controls can contain the same value.
Vendor E0/02 and E0/07 return black equalizer 10 and gamma 3 instead.

Direct DF returned `6E 88 02 00 DF 00 FF FF 02 02 6B`: a valid standard reply
whose value is MCCS 2.2. The unqualified standard E0 request is
`51 82 01 E0 32`; through HID it returned
`6E 88 02 00 E0 32 00 07 00 01 60`. This checksum-valid packet has byte 5=32,
which is not a valid standard VCP type (00/01). It has the shape of a vendor
E0/32 response. The request checksum is itself 32, consistent with consumption
as the missing vendor selector; **that causal explanation remains an inference
without F06 code**. The strict parser rejects it and exposes no standard E0
number. The diagnostic intentionally returns nonzero for that anomaly while
saving the complete report. The old Dxva2 E0=0202 reply cannot be used as a
vendor-unlock observation or assumed equivalent across these transports.

F08 raw dispatch evidence gives distinct paths: 18:8657 reads D127 for 10,
18:8663 reads D128 for 12, and 18:87C6/87CF/87D8 read D8BA/D8B7/D8B9 through
18:D0FF for 6C/6E/70. DF explicitly returns 0202 through 18:892D and 18:D178.
E0 and EC have no explicit case in that F08 standard GET table; default
18:8946 sets the failure result. These are F08 facts, not proof of an identical
F06 implementation. Exact Dxva2-to-F06 behavior still needs F06 code or passive
runtime evidence.

## Validation and remaining release blockers

The stock-fact suite, 2,304-case menu-wrapper suite, patch safety verifier, both
builders' verify-only modes and all controller/analysis regression tests pass.
The patched byte tables cover the new carry sequence and control-hook code/data.
The helper publishes successfully. No modified firmware file was generated.

Still OPEN: verified physical selection for menu 23/24; full interrupt/cross-bank
stack bounds; ownership of the erased cave against indirect execution; all
boot-time authentication; end-to-end patched transport and responses; recovery;
exact explanation of F06 standard-code fallback behavior. These are evidence
limits, not closed by changing an audit label to PASS.
