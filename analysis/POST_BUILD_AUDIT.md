# Safety and completeness audit — 2026-10-24

**Release verdict: FAIL / DO NOT FLASH.** Base commit
`5fa02eb5ffb605afd10c72c835cec869a1100d2f` passes local patch encoding checks;
zero brick risk and globally balanced runtime stack are not established.
This audit also fixes specific controller failure paths in the working tree.
No firmware binary was generated, modified on disk, or flashed. No Set-VCP,
HID command, compensation request, or protection-setting change was sent.

**Firmware scope correction:** the owner subsequently confirmed that the monitor
is running **F06** and has not been updated to F08. All live observations in this
audit therefore apply to the owner's F06 unit (owner-reported revision; not
independently detected by the probe). All patch bytes, addresses and static
control-flow findings apply to the hash-identified **F08 file**. Comparing those
sources is a cross-version comparison, not live validation of F08. No F06
firmware binary has been supplied or byte-audited in this work.

## Firmware byte audit

The reference image matches SHA-256
`3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f`.
All 20 extracted code banks match their corresponding image slices; the full
image hash covers the remaining 11 banks. Both builders' `full-control` profiles
select only the existing command-gate removal. The composed image differs from
stock at precisely these five bytes:

| Bank:address | Stock | Replacement | Instruction effect |
|---|---|---|---|
| 12:68AD | 64 | E4 | XRL A,#02 becomes CLR A |
| 12:68AE | 02 | 00 | remaining operand becomes NOP |
| 12:68BD | B4 | E4 | CJNE A,#02,68D4 becomes CLR A |
| 12:68BE | 02 | 00 | operand becomes NOP |
| 12:68BF | 14 | 00 | displacement becomes NOP |

The complete [byte-by-byte before/after disassembly tables](PATCH_BYTE_TABLES.md)
also cover every fixed patch site, all named interval values, custom immediate
endpoints, and both menu-hook sites. They include unchanged bytes inside each
patch and the relative branches in the surrounding windows. Reproduce without
emitting a firmware image:

```powershell
python analysis/verify_patch_safety.py --report analysis/PATCH_BYTE_TABLES.md
```

The verifier applies the real patch functions in memory, checks the allowed
mutation ranges, checks signed relative destinations using `oplen.OPLEN`, and
independently disassembles each replacement with radare2 in anonymous memory.
It checks 24 transformations and 18 distinct site/replacement combinations.
The window starts are explicit raw-code anchors, not whole-bank linear sweeps
through Keil tables. This is a local layout proof, not a complete CFG recovery.

Findings and limits:

- **PASS, local alignment:** no fixed replacement partially overwrites an
  instruction. The two command gates retain their original footprint with NOPs.
  All old boundaries remain available outside the explicitly injected erased
  region; no checked relative branch points into an operand or outside its window.
- **PASS, local stack effect:** gate and timer replacements add no stack
  operation. The menu call remains an LCALL returning to `9:E0E5`; its wrapper
  adds no PUSH/POP/call and tail-jumps to `9:97DB` on every path. The wrapper
  interpreter independently passes 2,304 cases. Return balance depends on the
  unchanged dispatcher and cross-bank callees returning correctly.
- **OPEN, global stack safety:** the retained calls through `0:2C50` and
  `0:2B9C`, synthetic bank returns, ISR interleavings and maximum stack depth are
  not proved by this audit. Counting LCALL and RET bytes would not prove them.
- **OPEN, carry semantics:** stock AOCS CJNE clears carry when the operand equals
  2. Its replacement preserves incoming carry. The subsequent D12D update does
  not overwrite carry before the calls. Sensitivity of the callees to that
  changed state has not been established. Encoding validity is insufficient.
- **FAIL, completeness:** `full-control` has exactly the same firmware bytes as
  `unlock`; it implements no additional arbitrary-XDATA or event-control path.
- **FAIL, menu functionality:** the hook at `9:E0E2` receives IDs 11/14, never
  23/24 through the documented E057 callers. Erased bytes alone also do not
  prove that a trampoline region is unused by every indirect path.
- **FAIL, generic patch scaffold:** `patch.py` accepts arbitrary caller JSON,
  permits unequal replacement lengths (resizing/shifting a bank), ignores the
  `bank` field, and lacks range, overlap, image-identity and instruction checks.
  It can overwrite its input bank. It has no finite built-in patch inventory;
  arbitrary JSON is outside the fixed-site proof. `reassemble` also requires
  banks 20–30, which are absent from `analysis/banks` in this checkout. These
  scaffold problems are recorded, not hidden behind the fixed-site result.
- **Fixed, preset plumbing:** the custom builder's parser omitted `full-control`
  from choices, and its output-name map omitted the entry used by the `all`
  path. Both entries are now present, tested with the file-writing function
  replaced in the test. No experimental image was emitted.
- **OPEN, release safety:** no verified image integrity/checksum update,
  flashing procedure, recovery mechanism or hardware execution validation.
  Timer experiments can defer panel protection and were inspected only in RAM.

## Controller implementation audit

The native bindings are real implementations. The dangerous behavior at the
base commit was ignored failure status and unvalidated replies, rather than a
large hidden mock backend. The explicit dry-run backend did contain a zero-filled
read stub; that stub has been removed. Production failure paths now fail closed.

| Source | Base-commit finding | Working-tree correction / remaining limit |
|---|---|---|
| `ddcci.py` | Calls real User32/Dxva2 functions, but omitted argtypes/restype; pointer-sized monitor arguments could be truncated. Duplicated scan and label dictionaries; weak error/handle lifecycle. | Explicit Win32 signatures and packed physical-monitor layout; callback errors propagated; range checks; idempotent cleanup; duplicates removed. A live GET brightness read returned 50/100. Compatibility scan still merges first responses across monitors; use the probe for attribution. |
| `transport.py` | Real cdecl RtHIDLib calls; read status ignored, so a failed read could return its zero-initialized buffer. Failed multi-device open did not raise. | Open result checked; nonzero read/write status raises; byte/range validation; tracks open state. The DLL ABI/return convention remains version-specific. |
| `helper_transport.py` | Starts a real x86 helper. Primary discovery path pointed outside `controller`; missing result defaulted to success and reply bytes were unvalidated. | Correct discovery path, exact result check and read length/byte validation. Requires helper protocol 2 so stale published executables are rejected. Its line protocol still lacks a response deadline. |
| `helper/Program.cs` / `helper.csproj` | Real native imports in win-x86/net8.0. Returned `ok=true` even on native failure, copied an uninitialized unmanaged buffer into JSON, ignored multi-open failure, and truncated lengths to byte. | Native return statuses checked; failed reads have no bytes field; buffers initialized and freed in finally; bounded lengths and byte conversions; requires an open device; closes on EOF. Builds with zero warnings/errors. |
| `oled.py` | Sends the documented request then reads bytes 8/9. No response-length/content validation. `execute_aocs` was missing although CLI/GUI referenced it. | Rejects short, invalid, all-zero and all-FF buffers; relies on checked transports; adds the gated AOCS wrapper. Dry-run readings are None. **Remaining:** selector echo, freshness, header/length fields and checksum are not validated; numeric OLED results remain provisional. No live HID reads were used for this audit. |
| `cli.py` | Explicit dry-run transport returned fake zeros if accidentally called; dry-run scan/dump still accessed real DDC. `scan-vcp --send` needlessly opened HID first. | Dry-run transport raises if used, scan/dump skip hardware without --send, and DDC-only scan does not open HID. AOCS command resolves to a real gated method. The direct HID CLI still needs matching Python/DLL architecture. |
| `gui.py` | Uses real transports and DDC. Editable defaults/stale values are not proof of successful reads; controls address all enumerated monitors. AOCS button only logged and returned. APCS path supplied `confirmed=True` without a per-action dialog. Failed connects leaked resources. | Explicit APCS confirmation and connection cleanup added. AOCS GUI now explicitly says no command was sent. **Remaining:** no selected-monitor binding for writes, no validated OLED reply parser, and worker/busy behavior can skip requested refreshes. Existing sliders/profiles are editable values, not validated telemetry. |

These changes do **not** certify the entire controller for hardware writes.
Low-level HID methods remain capable of sending arbitrary frames if invoked by
other code. The new probe neither imports them nor exposes any write command.

Native status evidence was read from installed `RtHIDLib.dll`, SHA-256
`b20b55ff4c637a2f78ce03695c5ad52636e9d313b504dfe894d065b5215ca3d8`:
`Open_HID` at `0x10003240` returns the match count; `Open_mutiHID` returns 1 on
failure (`0x100034E5`) and 0 on success (`0x10003559`). `HID_i2cread` at
`0x10002FF0` forwards `0x100028E0`, whose error returns are 2/-1/-2 and whose
success return is 0 at `0x100029D7`. `HID_i2cwrite` at `0x100030D0` returns 1
for an oversized buffer, -1 on the transport failure path, and 0 at
`0x10003186` on success. This is static evidence, not a live HID transaction.

An existing published helper must be rebuilt for protocol 2:

```powershell
dotnet publish controller/helper/helper.csproj -c Release -r win-x86 --self-contained false
```

## Live GET-only probe

Implemented [controller/live_probe.py](../controller/live_probe.py). It has an
independent, typed Win32 backend with only enumeration, capabilities, GET-VCP
and handle cleanup. It has no HID fallback, Set-VCP entry point, OLED execution
path, raw I2C method or controller imports. Failed GETs carry Win32 errors and
no numeric readings. Codes not reached before interruption/deadline remain
`not_attempted`. A separate worker bounds driver hangs; JSON snapshots are saved
atomically throughout the sweep.

```powershell
python controller/live_probe.py --list
python controller/live_probe.py --monitor 0 --firmware-label F06 --output controller/live-probe.json
```

Monitor indices must be checked each run. Automatic selection requires exactly
one physical description containing FO48U. Generic descriptions require explicit
selection. On this host, WMI showed exactly one active display, AORUS FO48U /
GBT4800, and Dxva2 showed one physical monitor at index 0, described as Generic
PnP Monitor. That independent evidence selected the target for this audit.

The completed local report is `controller/live-probe-2026-10-24.json` (ignored
by Git). It includes all 256 results, raw capabilities, per-code advertised
status, source hashes, knowledge-base declarations and literal atlas case
matches with heading/line/target. Atlas cases are not automatically VCP IDs;
incomplete/misidentified tables and unrelated numeric overlap remain possible.
The `80`/`82` vendor subcommands are kept distinct from standard GET-VCP codes.
The [sanitized published observation](observations/f06-vcp-get-2026-10-24.json)
retains all 256 GET results and capabilities without host paths, serials, PnP
instance identifiers or monitor handles.
The JSON records F06 as an owner-supplied firmware label separately from its
F08 static references; the captured response values are unchanged. Future
reports default to unknown firmware unless `--firmware-label` is supplied.
Neither the GET sweep nor the raw `C9` reply establishes the installed Fxx label.

Observed on the owner's **F06** unit at `2026-10-24T02:36:19Z`
(04:36 Europe/Berlin):

- **256 attempted; 37 responded; 219 GET failures; zero unattempted.**
- All 36 codes declared in the captured knowledge-base VCP list responded;
  `EC` also responded with current=0, maximum_raw=0. A zero response alone is
  not evidence of a useful implementation.
- 11 responding codes were unadvertised: `1E 20 30 62 6C 6E 70 86 C9 E0 EC`.
- `E0` and `DF` both returned current=`0x0202`, maximum_raw=`0xFFFF`, with the
  same raw type. `DF` was advertised; `E0` was not. This supports the existing
  ambiguity, not a vendor-command unlock claim.
- Several other reply groups were identical, including `10/12/6C/6E/70`.
  Identical values may be legitimate or fallback behavior and are flagged for
  review, not automatically rejected or promoted to supported features.

The report records what responded to GET. It cannot establish SET acceptance,
transport-to-bank-12 reachability, firmware version identity, or correctness of
existing VCP labels. MCCS table controls are not decoded by this API, and raw
maximum values are not meaningful for every control type. Microsoft documents
the [GET-VCP API and monitor-implementation limitations](https://learn.microsoft.com/en-us/windows/win32/api/lowlevelmonitorconfigurationapi/nf-lowlevelmonitorconfigurationapi-getvcpfeatureandvcpfeaturereply):
issuing only GET requests is not a universal guarantee of side-effect-free
behavior on arbitrary hardware.

## Validation

Stock facts, both builders' verify-only modes, and the 2,304-case menu wrapper
check pass. The added offline tests cover failed native/helper reads, zero
success status, invalid OLED buffers, stale helper rejection, dry-run isolation,
capability nesting, partial-report semantics, relative branches and preset
resolution without firmware output. The helper builds to a temporary directory
with zero warnings/errors; a closed-device helper read returns an error with no
bytes. The isolated probe completed on the attached monitor. No compensation,
Set-VCP, HID query or experimental firmware was exercised.
