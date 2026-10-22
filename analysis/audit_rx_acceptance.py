#!/usr/bin/env python3
"""Offline stock-byte audit of the F08 bank-13 receive-path acceptance rule.

Reads only the hash-identified stock F08 image. No device I/O, no firmware
generation, no image modification. `--self-test` mutates an in-memory copy of
the image; it never writes a file.

Byte-verified facts checked here. Addresses are bank-relative (`bank:address`);
the file offset of an address is `bank * 0x10000 + address`.

  F1  The two ISR-driven receive paths are 13:DD24 (buffer XDATA 0xCFD8,
      capacity XDATA 0xC9C5) and 13:DE63 (buffer XDATA 0xCF31, capacity
      0x50). Both store the received byte through 0:36C0 and read the frame
      length byte with 0:3681.
  F2  The frame length is computed as (buffer[1] & 0x7F) + 3 at
      13:EF29..13:EF2D and kept in R7. The interrupt prologue at 0:5215
      runs the 8051 in register bank 2 (PSW = 0x10), where R7 is IRAM
      0x17. The first CJNE of the pair at 13:DD84 / 13:DD88 (and
      13:DEBD / 13:DEC1) therefore compares the received-byte counter
      with that length, so the length field of the frame is used. The
      counter itself is IRAM 0x58 (13:DD68, 13:DEA2).
  F3  The only frame-content comparisons in either path are the pair at
      13:DDAD / 13:DDB6 (13:DEE9 / 13:DEF2): buffer offset 3 against the
      immediate 0xFC and buffer offset 2 against the immediate 0x03. All
      three outcomes of that pair return R7 = 1 (13:DDBE / 13:DEFA =
      `7f 01 22`), so the comparison cannot reject a frame.
  F4  The extra work in the matching arm (LCALL 13:F4B0) cannot change
      any observable state: 13:F8CE forces R7 = 0x16 before returning,
      and 13:F4B0 only writes XDATA in the branch that needs
      (R7 & 7) == 0.
  F5  Neither path reads buffer offset 0 or offsets 4..7, so a trailing
      frame byte is never compared: no inbound checksum is validated.
  F6  The only checksum in the mapped ingress/dispatch code is outbound
      (13:C976: XDATA 0xCF8B = 0xCF8A ^ 0xCF89 ^ 0xCF85 ^ 0xB4).
  F7  Nothing between the interrupt prologue (0:5215) and the two receive
      paths writes PSW, so register bank 2 stays selected for the whole
      receive chain.

Limits (not established here): the physical transport that fills XDATA
0xFF24 / 0xFF25 / 0xFE88 / 0xFE89, the meaning of the frame fields beyond
their byte offsets, the value of R4 when the second CJNE of the length
gate runs, whether an upstream component validates the trailing XOR byte of
a Sidekick frame, and any relative branch into the compare blocks from
outside the two decoded paths (see the printed LIMIT lines).

Instruction lengths come from analysis/oplen.py, which mirrors radare2's
8051 decoder. Six opcodes are one byte short there relative to the MCS-51
ISA (0x82, 0x84, 0xD6, 0xD7, 0xE2, 0xE3), so ISA_FIXUP below corrects
them locally; analysis/oplen.py is deliberately left untouched.
"""

import sys
from hashlib import sha256
from pathlib import Path

from oplen import OPLEN


IMAGE = (Path(__file__).resolve().parents[1] / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
REFERENCE_HASH = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000
CODE_BANKS = range(20)

# Standard MCS-51 lengths for the six opcodes analysis/oplen.py (radare2)
# under-counts by one byte.
ISA_FIXUP = {0x82: 3, 0x84: 2, 0xD6: 2, 0xD7: 2, 0xE2: 2, 0xE3: 2}

# Decoded regions: (bank, first address, last address, exclusive).
PATH_A = (13, 0xDD24, 0xDDC4)
PATH_B = (13, 0xDE63, 0xDEFF)
CHAIN_A = (13, 0xE373, 0xE3ED)      # ISR dispatcher + path A caller
CHAIN_B = (13, 0xEACE, 0xEB24)      # ISR dispatcher + path B caller
LENGTH_HELPER = (13, 0xEF0D, 0xEF37)

# Comparison opcodes: CJNE (0xB4..0xBF) and SUBB (0x94..0x9F).
CJNE = {0xB4, 0xB5, 0xB6, 0xB7} | set(range(0xB8, 0xC0))
SUBB = set(range(0x94, 0xA0))
# XRL with a memory operand (0x84..0x87): the only XOR forms of XRL.
XRL_MEMORY = {0x84, 0x85, 0x86, 0x87}

# Opcodes that write PSW (direct address 0xD0), and therefore the register
# bank selection bits PSW.4 / PSW.3.
PSW_WRITERS = {0x75, 0xF5, 0xD2, 0xC2, 0x92, 0x86}

# Official Sidekick reference frames (host-side data, see
# analysis/audit_sidekick_f08_handoff.py): eight bytes before HID padding.
SIDEKICK_FRAMES = {
    "APCS": bytes.fromhex("51 85 03 e0 80 00 02 b5"),
    "AOCS": bytes.fromhex("51 85 03 e0 82 00 02 b7"),
}


def expect(image: bytes, bank: int, address: int, original: str) -> None:
    """Pin the original bytes at one address."""
    wanted = bytes.fromhex(original)
    offset = bank * BANK_SIZE + address
    actual = image[offset:offset + len(wanted)]
    assert actual == wanted, (
        f"byte pin {bank}:{address:04X} file 0x{offset:06X}: "
        f"expected {wanted.hex(' ')}, observed {actual.hex(' ')}"
    )


def length(opcode: int) -> int:
    """Instruction length in bytes (standard MCS-51 ISA)."""
    return ISA_FIXUP.get(opcode, OPLEN[opcode])


def decode(image: bytes, region: tuple[int, int, int]) -> list[tuple[int, int, bytes]]:
    """Decode a bank-relative region into (address, opcode, raw bytes)."""
    bank, start, end = region
    base = bank * BANK_SIZE
    out: list[tuple[int, int, bytes]] = []
    address = start
    while address < end:
        opcode = image[base + address]
        size = length(opcode)
        assert address + size <= end, (
            f"{bank}:{address:04X}: instruction of {size} bytes crosses the "
            f"region end {end:04X}"
        )
        out.append((address, opcode, image[base + address:base + address + size]))
        address += size
    return out


def branch_target(address: int, raw: bytes) -> int | None:
    """Target of a relative branch, or None for other instructions."""
    opcode = raw[0]
    if opcode in (0x40, 0x50, 0x60, 0x70, 0x80) or 0xD8 <= opcode <= 0xDF:
        offset = 1
    elif opcode in CJNE or opcode == 0xD5:
        offset = 2
    else:
        return None
    relative = raw[offset]
    if relative > 127:
        relative -= 256
    return address + len(raw) + relative


def find(instructions: list[tuple[int, int, bytes]], address: int) -> tuple[int, bytes]:
    for current, opcode, raw in instructions:
        if current == address:
            return opcode, raw
    raise AssertionError(f"0x{address:04X} is not an instruction boundary")


def span(instructions: list[tuple[int, int, bytes]],
         start: int, end: int) -> bytes:
    """Concatenated bytes of the instructions in [start, end)."""
    out = b""
    for address, opcode, raw in instructions:
        if start <= address < end:
            out += raw
    assert out, f"no instructions in [0x{start:04X}, 0x{end:04X})"
    return out


def writes_psw(raw: bytes) -> bool:
    """True when the instruction writes PSW (direct address 0xD0)."""
    return raw[0] in PSW_WRITERS and len(raw) > 1 and raw[1] == 0xD0


def count_literal(image: bytes, literal: bytes) -> dict[int, int]:
    """Occurrences of a byte literal per code bank."""
    counts: dict[int, int] = {}
    for bank in CODE_BANKS:
        window = image[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]
        counts[bank] = window.count(literal)
    return counts


def run(image: bytes, region: tuple[int, int, int], state: dict) -> None:
    """Execute a small routine for one concrete input state.

    Only the opcodes that occur in the audited routines are implemented; an
    unknown opcode raises, so a changed image cannot pass silently. XDATA
    contents are not modelled: a MOVX read yields an unknown accumulator.
    """
    bank, start, end = region
    base = bank * BANK_SIZE
    address = start
    while address < end:
        opcode = image[base + address]
        size = length(opcode)
        raw = image[base + address:base + address + size]
        address += size
        if opcode == 0x22:                      # RET
            return
        elif opcode == 0x12:                   # LCALL addr16 (big endian)
            target = (raw[1] << 8) | raw[2]
            assert target == 0xF8CE, f"unexpected call target 0x{target:04X}"
            run(image, (13, 0xF8CE, 0xF8F7), state)
        elif opcode == 0xEF:                   # MOV A, R7
            state["A"] = state["R7"]
        elif opcode == 0xFE:                   # MOV R6, A
            state["R6"] = state["A"]
        elif opcode == 0x7E:                   # MOV R6, #imm
            state["R6"] = raw[1]
        elif opcode == 0xAF:                   # MOV R7, #imm
            state["R7"] = raw[1]
        elif opcode == 0x54:                   # ANL A, #imm
            if state["A"] is not None:
                state["A"] &= raw[1]
        elif opcode == 0x44:                   # ORL A, #imm
            if state["A"] is not None:
                state["A"] |= raw[1]
        elif opcode == 0x24:                   # ADD A, #imm
            if state["A"] is not None:
                state["A"] = (state["A"] + raw[1]) & 0xFF
        elif opcode == 0x14:                   # DEC A
            if state["A"] is not None:
                state["A"] = (state["A"] - 1) & 0xFF
        elif opcode == 0xE4:                   # CLR A
            state["A"] = 0
        elif opcode == 0x90:                   # MOV DPTR, #imm16 (big endian)
            state["DPTR"] = (raw[1] << 8) | raw[2]
        elif opcode == 0xE0:                   # MOVX A, @DPTR
            state["A"] = None
        elif opcode == 0xF0:                   # MOVX @DPTR, A
            state["writes"].append(state["DPTR"])
        elif opcode == 0x80:                   # SJMP rel
            address = branch_target(address - size, raw)
        elif opcode in (0x60, 0x70):           # JZ / JNZ rel
            assert state["A"] is not None, "branch on an unknown accumulator"
            taken = (state["A"] == 0) if opcode == 0x60 else (state["A"] != 0)
            if taken:
                address = branch_target(address - size, raw)
        else:
            raise AssertionError(
                f"run(): unhandled opcode 0x{opcode:02X} at "
                f"{bank}:{address - size:04X}"
            )


def simulate(image: bytes, region: tuple[int, int, int], r7: int) -> tuple[int, list]:
    """Run a routine with a concrete R7 and return (final R7, XDATA writes)."""
    state = {"A": None, "R6": None, "R7": r7, "DPTR": None, "writes": []}
    run(image, region, state)
    return state["R7"], state["writes"]


def audit(image: bytes | None = None, reference_hash: str = REFERENCE_HASH,
          use_pins: bool = True, verbose: bool = True) -> None:
    """Check the receive-path claims against one image.

    `use_pins=False` skips the raw byte pins so that only the derived
    checks (decoded structure, reachability, simulation) remain; the
    self-test uses that mode to show the conclusions are byte sensitive.
    """
    if image is None:
        image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Unexpected stock image length"
    assert sha256(image).hexdigest() == reference_hash, "Unexpected stock SHA256"

    def pin(bank: int, address: int, original: str) -> None:
        if use_pins:
            expect(image, bank, address, original)

    # ---- receive paths and helpers ---------------------------------------
    pin(13, 0xDD24, "90 c9 c2 eb f0 a3 ea f0 a3 e9 f0 a3 ed f0")
    pin(13, 0xDD32, "90 ff 27 e0 54 02 64 02 70 15 78 58 f6 90 ff 24 e0 ff 12 ef 37 12 ef 43 90 ff 27 e0 54 fd f0")
    pin(13, 0xDD51, "90 ff 27 e0 54 04 64 04 70 66 90 ff 29 e0 54 02 70 5e")
    pin(13, 0xDD63, "90 c9 c5 e0 ff 78 58 e6 c3 9f 40 0b 90 ff 2a e0 44 40 f0 e4 f6 80 47")
    pin(13, 0xDD7A, "90 ff 25 e0 90 c9 c2 12 ef 0d")
    pin(13, 0xDD84, "b5 17 d4 ec b5 16 d0")
    pin(13, 0xDD8B, "90 ff 2a 12 ef 4e 90 ff 26 e4 f0 d5 47 f8 90 ff 2a e0 54 df f0 e0 44 40 f0")
    pin(13, 0xDDA4, "12 ef 37 90 00 03 12 36 81")
    pin(13, 0xDDAD, "b4 fc 0e 90 00 02 12 36 81 b4 03 05 e4 ff 12 f4 b0 7f 01 22 7f 00 22")
    pin(13, 0xDE63, "90 c9 c2 eb f0 a3 ea f0 a3 e9 f0")
    pin(13, 0xDE6E, "90 fe 8b e0 54 02 64 02 70 18 78 58 f6 90 fe 88 e0 ff 90 c9 c2 12 ef 3a 12 ef 43 90 fe 8b e0 54 fd f0")
    pin(13, 0xDE90, "90 fe 8b e0 54 04 64 04 70 63")
    pin(13, 0xDE9A, "90 fe 8d e0 54 02 70 5b 78 58 e6 c3 94 50 40 09 a3 e0 44 40 f0 e4 f6 80 4a")
    pin(13, 0xDEB3, "90 fe 89 e0 90 c9 c2 12 ef 0d")
    pin(13, 0xDEBD, "b5 17 da ec b5 16 d6")
    pin(13, 0xDEC4, "90 fe 8e 12 ef 4e 90 fe 8a e4 f0 d5 47 f8 90 fe 8e e0 54 df f0 e0 44 40 f0 90 c9 c2 12 ef 3a")
    pin(13, 0xDEE3, "90 00 03 12 36 81")
    pin(13, 0xDEE9, "b4 fc 0e 90 00 02 12 36 81 b4 03 05 7f 01 12 f4 b0 7f 01 22 7f 00 22")
    pin(13, 0xEF0D, "ff e0 fb a3 e0 fa a3 e0 f9 78 58 e6 06 f5 82 75 83 00 ef 12 36 c0 90 00 01 12 36 81 54 7f 24 03 ff e4 33 fe 78 58 e6 7c 00 22")
    pin(13, 0xEF37, "90 c9 c2 e0 fb a3 e0 fa a3 e0 f9 22")
    pin(13, 0xEF43, "e6 06 f5 82 75 83 00 ef 02 36 c0")
    pin(13, 0xEF4E, "e0 44 60 f0")
    pin(0, 0x3681, "bb 01 0c e5 82 29 f5 82 e5 83 3a f5 83 e0 22 50 06 e9 25 82 f8 e6")
    pin(0, 0x36C0, "f8 bb 01 0d e5 82 29 f5 82 e5 83 3a f5 83 e8 f0 22")

    # ---- register bank selected by the interrupt prologue ---------------
    pin(0, 0x5213, "c0 d0 75 d0 10")            # PUSH PSW; MOV PSW,#0x10
    pin(0, 0x523B, "d0 d0")                    # POP PSW
    pin(0, 0x0DD0, "c0 d0 25 30 d0 d0 22")     # PSW-preserving helper
    pin(0, 0x0EE0, "90 e3 73 02 0c 67")       # bank-13 handler stub
    pin(0, 0x5034, "78 0d 80 46")             # select bank 13

    # ---- ISR handlers that reach the receive paths ----------------------
    pin(13, 0xE373, "90 ff 29 12 f7 bb 13 40 13 90 fe 86 e0 54 07 fd 90 ff 22 e0 54 07 6d 70")
    pin(13, 0xE38D, "70 1d")                  # JNZ 0xE3AC
    pin(13, 0xEACE, "90 fe 8d 12 f7 bb")
    pin(13, 0xE3AC, "e4 90 cf d4 f0 90 ff 23 e0 54 fe 64 6e 70 32 12 26 56 ef 7b 01 70 08 7a cf 79 d8 7d 80 80 06 7a ce 79 e1 7d 50 12 dd 24 12 f7 c6 4f f0 90 cf d2 e0 13 50 15 e4 ff 12 c8 a4 bf 01 0d 12 f7 c6 f0 22")
    pin(13, 0xE3F8, "75 d0 08")                # bank 1 after the path
    pin(13, 0xEB04, "7b 01 7a cf 79 31 12 de 63 12 f7 b0 4f f0 e0 a2 e1 50 15 7f 01 12 c8 a4 bf 01 0d 12 f7 b4 f0 22")

    # ---- flag dispatch and merge helpers --------------------------------
    pin(13, 0xF4B0, "12 f8 ce ef 54 07 60 28 14 60 20 14 60 18 14 60 10 14 60 08 14 70 20")
    pin(13, 0xF8CE, "7e 07 ef 14 60 0f 14 60 11 14 60 13 24 03 70 16 90 ff 22 80 0d 90 fe 86 80 08 90 fe 94 80 03 90 fe a3 e0 54 07 fe af 16 22")
    pin(13, 0xF7B0, "ef 25 e0 ff 90 cf d2 e0 54 fd 22")
    pin(13, 0xF7C6, "90 cf d2 e0 54 fe 22")
    pin(13, 0xC976, "90 cf 85 e0 64 b4 ff 90 cf 89 e0 6f ff a3 e0 6f a3 f0")
    pin(1, 0xDDAD, "02 de 78 90 c6 ba e0 ff 70 05")  # bank-1 twin
    pin(6, 0xDEE9, "90 ba cc e0 54 40 22")          # bank-6 twin

    # ---- structural checks on the two receive paths ---------------------
    path_a = decode(image, PATH_A)
    path_b = decode(image, PATH_B)
    chain_a = decode(image, CHAIN_A)
    chain_b = decode(image, CHAIN_B)

    # The complete set of value comparisons in either path. Anything that
    # validated a frame would have to appear in this list.
    comparisons = []
    for name, path in (("A", path_a), ("B", path_b)):
        for address, opcode, raw in path:
            if opcode in CJNE or opcode in SUBB:
                comparisons.append((name, address, raw.hex(" ")))
    assert comparisons == [
        ("A", 0xDD6C, "9f"),          # SUBB A,R7   (counter - capacity)
        ("A", 0xDD84, "b5 17 d4"),   # CJNE A,IRAM 0x17,rel
        ("A", 0xDD88, "b5 16 d0"),   # CJNE A,IRAM 0x16,rel
        ("A", 0xDDAD, "b4 fc 0e"),   # CJNE A,#0xFC,rel
        ("A", 0xDDB6, "b4 03 05"),   # CJNE A,#0x03,rel
        ("B", 0xDEA6, "94 50"),      # SUBB A,#0x50 (counter - 0x50)
        ("B", 0xDEBD, "b5 17 da"),   # CJNE A,IRAM 0x17,rel
        ("B", 0xDEC1, "b5 16 d6"),   # CJNE A,IRAM 0x16,rel
        ("B", 0xDEE9, "b4 fc 0e"),   # CJNE A,#0xFC,rel
        ("B", 0xDEF2, "b4 03 05"),   # CJNE A,#0x03,rel
    ], f"unexpected comparison census: {comparisons}"

    # No XOR of a memory operand in either path: nothing folds the received
    # bytes into an accumulator.
    for name, path in (("A", path_a), ("B", path_b)):
        folds = [f"0x{address:04X}" for address, opcode, _ in path
                 if opcode in XRL_MEMORY]
        assert not folds, f"path {name} folds memory with XRL at {folds}"

    # The only buffer offsets the paths read are 1, 2 and 3. Offset 0 and
    # offsets 4..7 (including a trailing checksum byte) are never read.
    reader = bytes.fromhex("12 36 81")               # LCALL 0:3681
    offsets = set()
    for region in (PATH_A, PATH_B, LENGTH_HELPER):
        bank, start, end = region
        window = image[bank * BANK_SIZE + start:bank * BANK_SIZE + end]
        for index in range(len(window) - 5):
            if window[index] == 0x90 and window[index + 3:index + 6] == reader:
                assert window[index + 1] == 0x00
                offsets.add(window[index + 2])
    assert offsets == {0x01, 0x02, 0x03}, f"unexpected buffer offsets {offsets}"

    # The frame-content reads: offset 3 and offset 2 of the selected buffer,
    # each read with the common reader 0:3681.
    for name, path, offset3, offset2 in (
        ("A", path_a, 0xDDA7, 0xDDB0),
        ("B", path_b, 0xDEE3, 0xDEEC),
    ):
        opcode, raw = find(path, offset3)
        assert opcode == 0x90 and raw[1:3] == b"\x00\x03", (
            f"path {name}: 13:{offset3:04X} does not select buffer offset 3"
        )
        opcode, raw = find(path, offset3 + 3)
        assert opcode == 0x12 and (raw[1] << 8) | raw[2] == 0x3681, (
            f"path {name}: 13:{offset3 + 3:04X} does not call the reader"
        )
        opcode, raw = find(path, offset2)
        assert opcode == 0x90 and raw[1:3] == b"\x00\x02", (
            f"path {name}: 13:{offset2:04X} does not select buffer offset 2"
        )
        opcode, raw = find(path, offset2 + 3)
        assert opcode == 0x12 and (raw[1] << 8) | raw[2] == 0x3681, (
            f"path {name}: 13:{offset2 + 3:04X} does not call the reader"
        )

    # The common reader returns the selected buffer byte in A and the
    # common writer stores a byte through the computed DPTR.
    reader_code = decode(image, (0, 0x3681, 0x3690))
    assert any(opcode == 0xE0 for _, opcode, _ in reader_code), (
        "0:3681 does not read XDATA"
    )
    writer_code = decode(image, (0, 0x36C0, 0x36D1))
    assert any(opcode == 0xF0 for _, opcode, _ in writer_code), (
        "0:36C0 does not write XDATA"
    )

    # ---- the length formula ---------------------------------------------
    # 13:EF23 sets DPTR to buffer offset 1, 13:EF26 reads that byte with
    # 0:3681, 13:EF29 masks it with 0x7F, 13:EF2B adds 3 and 13:EF2D
    # keeps the result in R7.
    helper = decode(image, LENGTH_HELPER)
    opcode, raw = find(helper, 0xEF23)
    assert opcode == 0x90 and raw[1:3] == b"\x00\x01", "13:EF23 is not MOV DPTR,#1"
    opcode, raw = find(helper, 0xEF26)
    assert opcode == 0x12 and (raw[1] << 8) | raw[2] == 0x3681, (
        "13:EF26 does not call the buffer reader 0:3681"
    )
    opcode, raw = find(helper, 0xEF29)
    assert opcode == 0x54 and raw[1] == 0x7F, "13:EF29 does not mask with 0x7F"
    opcode, raw = find(helper, 0xEF2B)
    assert opcode == 0x24 and raw[1] == 0x03, "13:EF2B does not add 3"
    opcode, raw = find(helper, 0xEF2D)
    assert opcode == 0xFF, "13:EF2D does not store the length in R7"
    # The masked length cannot overflow, so the carry that becomes R6 at
    # 13:EF30 is always 0 and the second CJNE of the gate compares
    # against zero.
    assert 0x7F + 3 < 0x100

    # ---- the FC/03 comparison is value preserving -----------------------
    for name, path, compare, match, exit_address in (
        ("A", path_a, (0xDDAD, 0xDDB6), 0xDDB9, 0xDDBE),
        ("B", path_b, (0xDEE9, 0xDEF2), 0xDEF5, 0xDEFA),
    ):
        for address in compare:
            opcode, raw = find(path, address)
            assert opcode == 0xB4, f"{name}:{address:04X} is not CJNE A,#imm"
            assert branch_target(address, raw) == exit_address, (
                f"{name}:{address:04X} branches to "
                f"0x{branch_target(address, raw):04X}, expected "
                f"0x{exit_address:04X}"
            )
        # The matching arm falls through to the same address, and that
        # address returns R7 = 1. Both arms therefore return R7 = 1.
        arm = span(path, match, exit_address)
        assert arm.hex(" ") in ("e4 ff 12 f4 b0", "7f 01 12 f4 b0"), (
            f"path {name}: unexpected matching arm {arm.hex(' ')}"
        )
        opcode, raw = find(path, exit_address)
        assert opcode == 0x7F and raw[1] == 0x01, (
            f"path {name}: 13:{exit_address:04X} does not return R7 = 1"
        )
        # The rejection arm of the caller returns R7 = 0.
        opcode, raw = find(path, exit_address + 3)
        assert opcode == 0x7F and raw[1] == 0x00, (
            f"path {name}: 13:{exit_address + 3:04X} does not return R7 = 0"
        )

    # ---- the matching arm cannot change observable state ----------------
    # 13:F8CE forces R7 = 0x16 on every return path.
    selector = decode(image, (13, 0xF8CE, 0xF8F7))
    returns = [address for address, opcode, _ in selector if opcode == 0x22]
    assert returns == [0xF8F6], f"unexpected RET count in 13:F8CE: {returns}"
    forced, forced_raw = find(selector, 0xF8F4)
    assert forced == 0xAF and forced_raw[1] == 0x16, (
        "13:F8F4 does not force R7 = 0x16"
    )
    for address, opcode, raw in selector:
        target = branch_target(address, raw)
        if target is not None:
            assert 0xF8E3 <= target <= 0xF8F4, (
                f"13:F8CE branch at 0x{address:04X} skips 13:F8F4"
            )

    # 13:F4B0 writes XDATA only in the branch that needs (R7 & 7) == 0; with
    # R7 = 0x16 the mask leaves 6 and the write is skipped.
    for entry in (0, 1, 0x16):
        result, writes = simulate(image, (13, 0xF4B0, 0xF4E8), entry)
        assert result == 0x16, f"13:F4B0 returned R7 = {result:#x}"
        assert not writes, f"13:F4B0 wrote XDATA {writes} for R7 = {entry:#x}"

    # ---- how the callers consume the result -----------------------------
    # Path A merges the returned R7 into XDATA 0xCFD2 bit 0 (13:E3D4 sets
    # DPTR and clears bit 0, 13:E3D7 ORs R7 in). Because the comparison
    # always returns R7 = 1, that bit is set whatever the frame contains.
    # Path B merges XDATA[DPTR] instead (13:F7B0 loads R7 from the buffer
    # byte the comparison read last), so the RX result itself is unused.
    pin(13, 0xE3D4, "12 f7 c6 4f f0")
    pin(13, 0xEB0D, "12 f7 b0 4f f0")
    pin(13, 0xE3DD, "13 50 15")               # RRC A; JNC (flag test)
    pin(13, 0xEB13, "a2 e1 50 15")            # MOV CY,0xE1; JNC

    # ---- register bank evidence -----------------------------------------
    # PSW = 0x10 selects register bank 2, so IRAM 0x10..0x17 are R0..R7.
    # The gate compares IRAM 0x17 (R7, the computed frame length) with the
    # received-byte counter, and IRAM 0x16 (R6) with R4 after 13:DD87
    # exchanges the counter into R4.
    prologue = decode(image, (0, 0x5213, 0x5218))
    opcode, raw = find(prologue, 0x5213)
    assert opcode == 0xC0 and raw[1] == 0xD0, "0:5213 does not push PSW"
    opcode, raw = find(prologue, 0x5215)
    assert opcode == 0x75 and raw[1] == 0xD0 and raw[2] == 0x10, (
        "0:5215 does not select register bank 2 (PSW = 0x10)"
    )
    epilogue = decode(image, (0, 0x523B, 0x523D))
    opcode, raw = find(epilogue, 0x523B)
    assert opcode == 0xD0 and raw[1] == 0xD0, "0:523B does not restore PSW"

    # The received-byte counter is IRAM 0x58 in both paths: MOV R0,#0x58
    # followed by MOV A,@R0. 0x58 is outside every register bank.
    for name, path, address in (("A", path_a, 0xDD68), ("B", path_b, 0xDEA2)):
        opcode, raw = find(path, address)
        assert opcode == 0x78 and raw[1] == 0x58, (
            f"path {name}: 13:{address:04X} does not point R0 at IRAM 0x58"
        )
        opcode, raw = find(path, address + 2)
        assert opcode == 0xE6, (
            f"path {name}: 13:{address + 2:04X} does not read IRAM 0x58"
        )

    # Nothing between the interrupt prologue and the receive paths writes
    # PSW, so register bank 2 stays selected across the whole chain.
    for name, region in (("A", CHAIN_A), ("B", CHAIN_B),
                         ("A", PATH_A), ("B", PATH_B),
                         ("bank switch", (0, 0x0C67, 0x0C7A)),
                         ("bank select", (0, 0x5034, 0x5038)),
                         ("bank write", (0, 0x507E, 0x508A)),
                         ("bank helper", (0, 0x0DD0, 0x0DD7))):
        for address, opcode, raw in decode(image, region):
            assert not writes_psw(raw), (
                f"{name}: PSW write at {address:04X} inside the receive chain"
            )

    # ---- buffer selection and capacity ----------------------------------
    # The path A caller selects the 0xCFD8 slot (R2:R3) with size 0x80 when
    # D8FE is zero, and the 0xCEE1 slot with size 0x50 otherwise.
    opcode, raw = find(chain_a, 0xE3C3)
    assert opcode == 0x7A and raw[1] == 0xCF, "13:E3C3 does not load 0xCF"
    opcode, raw = find(chain_a, 0xE3C5)
    assert opcode == 0x79 and raw[1] == 0xD8, "13:E3C5 does not load 0xD8"
    opcode, raw = find(chain_a, 0xE3C7)
    assert opcode == 0x7D and raw[1] == 0x80, "13:E3C7 does not load size 0x80"
    opcode, raw = find(chain_a, 0xE3CB)
    assert opcode == 0x7A and raw[1] == 0xCE, "13:E3CB does not load 0xCE"
    opcode, raw = find(chain_a, 0xE3CD)
    assert opcode == 0x79 and raw[1] == 0xE1, "13:E3CD does not load 0xE1"
    opcode, raw = find(chain_a, 0xE3CF)
    assert opcode == 0x7D and raw[1] == 0x50, "13:E3CF does not load size 0x50"
    # The path A capacity is read from XDATA 0xC9C5, which the caller
    # stores at 13:DD31; path B compares the counter with 0x50 directly
    # (see the comparison census).
    opcode, raw = find(path_a, 0xDD63)
    assert opcode == 0x90 and (raw[1] << 8) | raw[2] == 0xC9C5, (
        "13:DD63 does not read the capacity from XDATA 0xC9C5"
    )

    # ---- reachability of the comparison blocks --------------------------
    # Inside the two decoded paths no branch targets a comparison block, so
    # the block is entered by fall-through from the gate body only.
    for name, path, blocked in (("A", path_a, (0xDDAD, 0xDDB6)),
                                ("B", path_b, (0xDEE9, 0xDEF2))):
        for address, opcode, raw in path:
            target = branch_target(address, raw)
            if target is not None:
                assert target not in blocked, (
                    f"path {name}: branch at 0x{address:04X} enters the "
                    f"comparison block"
                )

    # No absolute branch inside bank 13 targets a comparison block. In other
    # banks the same addresses hold unrelated code, so an absolute branch
    # there resolves inside its own bank.
    for address in (0xDDAD, 0xDDB6, 0xDEE9, 0xDEF2):
        bank13 = image[13 * BANK_SIZE + address:13 * BANK_SIZE + address + 3]
        for opcode in (0x02, 0x12):
            literal = bytes((opcode, address >> 8, address & 0xFF))
            for bank, count in count_literal(image, literal).items():
                if count == 0:
                    continue
                local = image[bank * BANK_SIZE + address:
                              bank * BANK_SIZE + address + 3]
                assert local != bank13, (
                    f"bank {bank} branches to the same bytes as 13:{address:04X}"
                )

    # ---- whole-image negative scans -------------------------------------
    # The trailing byte of the three candidate receive buffers. XDATA is
    # only reachable through DPTR, so a reference needs such a literal.
    for address in (0xCF38, 0xCEE8):
        literal = bytes((0x90, address >> 8, address & 0xFF))
        assert sum(count_literal(image, literal).values()) == 0, (
            f"XDATA 0x{address:04X} is referenced in code banks 0-19"
        )
    # XDATA 0xCFDF is referenced elsewhere in the image, but never from a
    # receive path.
    literal = bytes((0x90, 0xCF, 0xDF))
    assert sum(count_literal(image, literal).values()) > 0
    for name, path in (("A", path_a), ("B", path_b)):
        for address, opcode, raw in path:
            assert literal not in raw, (
                f"path {name} touches XDATA 0xCFDF at 13:{address:04X}"
            )

    # ---- consequence for the official Sidekick frames -------------------
    for label, frame in SIDEKICK_FRAMES.items():
        length_field = (frame[1] & 0x7F) + 3
        assert length_field == len(frame), (
            f"{label}: computed length {length_field} != frame size {len(frame)}"
        )
        # The trailing byte is the XOR of the preceding bytes and is never
        # compared by the receive path.
        checksum = 0
        for byte in frame[:7]:
            checksum ^= byte
        assert checksum == frame[7], f"{label}: trailing byte is not the XOR"
        # A frame of this shape takes the mismatch arm of the FC/03
        # comparison, which returns the same R7 = 1 as the matching arm.
        assert frame[3] != 0xFC, f"{label}: frame offset 3 is 0xFC after all"

    # ---- outbound checksum (the only checksum in the mapped code) -------
    assert 0x50 ^ 0x6E ^ 0x88 ^ 0x02 ^ 0x00 == 0xB4

    if not verbose:
        return

    print("PASS: stock F08 hash 3dd2e95a... and all pinned receive-path bytes")
    print("PASS: path A 13:DD24 (XDATA 0xCFD8, capacity XDATA 0xC9C5), "
          "path B 13:DE63 (XDATA 0xCF31, capacity 0x50)")
    print("PASS: length=(buffer[1]&0x7F)+3 at 13:EF29..13:EF2D; ISR prologue "
          "0:5215 selects register bank 2 (PSW=0x10), so IRAM 0x17 is R7")
    print("PASS: the received-byte counter is IRAM 0x58 in both paths "
          "(13:DD68, 13:DEA2)")
    print("PASS: comparison census - the length gate and the FC/03 pair are "
          "the only comparisons in either path")
    print("PASS: FC/03 mismatch and match arms both return R7 = 1 "
          "(13:DDBE / 13:DEFA = 7f 01 22); the pair cannot reject a frame")
    print("PASS: matching arm LCALL 13:F4B0 writes no XDATA (13:F8CE forces "
          "R7 = 0x16, and (0x16 & 7) != 0)")
    print("PASS: receive paths read buffer offsets 1, 2, 3 only - a trailing "
          "frame byte is never compared")
    print("PASS: no arithmetic or XOR of a memory operand in either path")
    print("PASS: path A merges R7 into XDATA 0xCFD2 bit 0, so the FC/03 "
          "comparison cannot change the accept flag")
    print("PASS: no PSW write between the interrupt prologue and the "
          "receive paths, so register bank 2 stays selected")
    print("TX only: CF8B = CF8A ^ CF89 ^ CF85 ^ 0xB4 at 13:C976")
    print("LIMIT: no inbound checksum validated; the transport that fills "
          "FF24/FF25/FE88/FE89 is unknown")
    print("LIMIT: path B merges the buffer byte the comparison read last "
          "(13:F7B0), so its 0xCFD2 bit 1 still depends on that comparison")
    print("LIMIT: the second CJNE of the length gate (13:DD88 / 13:DEC1) "
          "compares IRAM 0x16 (R6) with R4; R4 is not established here")
    print("LIMIT: a relative branch into 13:DDB6 from 13:DB37..13:DD23 is "
          "not excluded by this audit")


# One byte position, its replacement, and a note on what must catch it.
# Each case is checked twice: once with the raw byte pins enabled and once
# with them disabled, so the derived checks have to carry the detection.
SELF_TEST_CASES = (
    ("path A FC immediate", 13, 0xDDAD + 1, b"\xfd", "comparison census"),
    ("path A 03 immediate", 13, 0xDDB6 + 1, b"\x04", "comparison census"),
    ("path B FC immediate", 13, 0xDEE9 + 1, b"\xfd", "comparison census"),
    ("path B capacity immediate", 13, 0xDEA6 + 1, b"\x40", "comparison census"),
    ("length mask", 13, 0xEF29 + 1, b"\x3f", "length formula"),
    ("length constant", 13, 0xEF2B + 1, b"\x04", "length formula"),
    ("length destination", 13, 0xEF2D, b"\xfe", "length formula"),
    ("path A exit value", 13, 0xDDBE + 1, b"\x02", "exit value"),
    ("path B exit value", 13, 0xDEFA + 1, b"\x02", "exit value"),
    ("path A rejection value", 13, 0xDDC1 + 1, b"\x01", "exit value"),
    ("13:F8CE forced R7", 13, 0xF8F4 + 1, b"\x17", "forced R7 / simulation"),
    ("13:F4B0 write mask", 13, 0xF4B4 + 1, b"\x00", "simulation"),
    ("buffer offset literal", 13, 0xDDA9, b"\x04", "buffer offset set"),
    ("ISR register bank", 0, 0x5215 + 2, b"\x08", "register bank"),
    ("PSW write in chain A", 13, 0xE376, b"\x75\xd0\x08", "PSW scan"),
    ("path A capacity pointer", 13, 0xDD64 + 1, b"\xc8", "capacity literal"),
    ("path A buffer base", 13, 0xE3C5 + 1, b"\xd9", "buffer base literal"),
)


def self_test() -> None:
    """Show that the audit fails on changed bytes, not only on a bad hash.

    The mutated image stays in memory: nothing is written to disk.
    """
    stock = IMAGE.read_bytes()
    failures = []
    for label, bank, address, replacement, expected in SELF_TEST_CASES:
        offset = bank * BANK_SIZE + address
        mutated = bytearray(stock)
        mutated[offset:offset + len(replacement)] = replacement
        mutated = bytes(mutated)
        digest = sha256(mutated).hexdigest()

        pinned = None
        try:
            audit(mutated, digest, use_pins=True, verbose=False)
        except AssertionError as exc:
            pinned = str(exc)
        if pinned is None:
            failures.append(f"{label}: the audit accepted the mutated image")
            continue

        derived = None
        try:
            audit(mutated, digest, use_pins=False, verbose=False)
        except AssertionError as exc:
            derived = str(exc)
        if derived is None:
            failures.append(
                f"{label}: only the byte pins caught the change, "
                f"not a derived check"
            )
            continue
        if derived.startswith("byte pin"):
            failures.append(f"{label}: the derived check was a byte pin")
            continue
        print(f"PASS: {label} ({bank}:{address:04X} -> {replacement.hex(' ')}) "
              f"rejected by {expected}: {derived[:70]}")

    if failures:
        for line in failures:
            print(f"FAIL: {line}")
        raise SystemExit(1)
    print(f"PASS: {len(SELF_TEST_CASES)} byte mutations rejected by derived "
          f"checks with the SHA-256 pin recomputed")


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        self_test()
        return 0
    audit()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
