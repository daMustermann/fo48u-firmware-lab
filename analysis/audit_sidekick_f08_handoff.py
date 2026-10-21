#!/usr/bin/env python3
"""Offline F08 audit of a *conditional* Sidekick-frame-to-bank-12 route.

The two reference frames come from the separately audited official Sidekick
binary (see audit_sidekick_commands.py). This script checks only stock firmware
bytes and hypothetical frame placement; it performs no device I/O. It does not
prove HID-to-receiver mapping, packet validation, or compensation execution.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parents[1] / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000

# Eight-byte Realtek branch data frame, *before* HID padding/wrapping.
# This is host-side reference data, not a captured receive buffer.
SIDEKICK_FRAMES = {
    "APCS": bytes.fromhex("51 85 03 e0 80 00 02 b5"),
    "AOCS": bytes.fromhex("51 85 03 e0 82 00 02 b7"),
}


def expect(image: bytes, bank: int, address: int, opcodes: str) -> None:
    wanted = bytes.fromhex(opcodes)
    offset = bank * BANK_SIZE + address
    actual = image[offset:offset + len(wanted)]
    assert actual == wanted, (
        f"{bank}:{address:04X} file 0x{offset:06X}: "
        f"expected {wanted.hex(' ')}, got {actual.hex(' ')}"
    )


def audit() -> None:
    image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Expected the exact stock F08 image length"
    assert sha256(image).hexdigest() == SHA256, "Expected the stock F08 SHA-256"

    # Primary RX: masked FF23 address 6E; FF24 seeds buffer offset zero and
    # FF25 supplies following bytes. Shared index writer is an XDATA MOVX.
    expect(image, 13, 0xE3B1, "90 ff 23 e0 54 fe 64 6e 70 32")
    expect(image, 13, 0xE3BB,
           "12 26 56 ef 7b 01 70 08 7a cf 79 d8 7d 80 80 06 "
           "7a ce 79 e1 7d 50 12 dd 24")
    expect(image, 13, 0xDD3C, "78 58 f6 90 ff 24 e0 ff 12 ef 37 12 ef 43")
    expect(image, 13, 0xDD7A, "90 ff 25 e0 90 c9 c2 12 ef 0d")
    expect(image, 13, 0xEF43, "e6 06 f5 82 75 83 00 ef 02 36 c0")
    expect(image, 13, 0xEF0D,
           "ff e0 fb a3 e0 fa a3 e0 f9 78 58 e6 06 f5 82 "
           "75 83 00 ef 12 36 c0 90 00 01 12 36 81 54 7f 24 03")
    expect(image, 0, 0x36C0,
           "f8 bb 01 0d e5 82 29 f5 82 e5 83 3a f5 83 e8 f0 22")
    expect(image, 13, 0xDDA4,
           "12 ef 37 90 00 03 12 36 81 b4 fc 0e 90 00 02 "
           "12 36 81 b4 03 05")

    # The primary RX completion flag (CFD2.bit0) is conditionally retained:
    # 13:C8A4 examines CFDB via bank-14 FE80; that helper detects EC,
    # whereas the Sidekick reference family byte is E0.
    expect(image, 13, 0xE3D1,
           "12 dd 24 12 f7 c6 4f f0 90 cf d2 e0 13 50 15")
    expect(image, 13, 0xE3E0, "e4 ff 12 c8 a4 bf 01 0d 12 f7 c6 f0 22")
    expect(image, 13, 0xC8A4,
           "90 c9 c2 ef f0 e4 a3 f0 fe 7f 03 fd 7b 01 7a c9 "
           "79 c4 12 3e 86 12 26 56 ef 70 15")
    expect(image, 13, 0xC8BF,
           "90 cf da e0 90 c9 c4 f0 90 cf db e0 90 c9 c5 f0")
    expect(image, 13, 0xC914,
           "90 c9 c5 e0 ff 12 26 62 ef 64 01 60 03 02 ca 08")
    expect(image, 0, 0x2662, "90 fe 80 02 0c 7a")
    expect(image, 14, 0xFE80,
           "c0 d0 75 d0 10 ef b4 ec 04 7f 01 80 02 7f 00 d0 d0 22")
    expect(image, 13, 0xCA08, "7f 00 22")

    # Bank 18 selects pending slot and optionally copies CEE1/CF31 into
    # CFD8. It calls bank 7 first; for CFDA=03 the bank-7 handler returns
    # with C=0, permitting the later bank-12 call to be reached.
    expect(image, 18, 0xD6B2,
           "90 d1 83 e0 ff 13 13 54 3f 30 e0 6f")
    expect(image, 18, 0xD6BE,
           "90 cf d2 e0 24 ff 50 67 12 e2 2d 12 2d ac 40 41 "
           "12 2d b2 40 3c")
    expect(image, 18, 0xE254,
           "90 c5 01 e0 75 f0 50 a4 24 e1 f9 74 ce 35 f0 "
           "fa 7b 01 78 d8 7c cf 7d 01 7e 00 7f 50 12 35 fc")
    expect(image, 0, 0x2DAC, "90 69 22 02 0b f5")
    expect(image, 0, 0x0BF5,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 "
           "c0 82 c0 83 02 50 1c")
    expect(image, 0, 0x501C, "78 07 80 5e")
    expect(image, 7, 0x6945,
           "90 cf da e0 ff 64 c0 60 07 ef 64 d0 60 02 c3 22")
    expect(image, 0, 0x2DB2, "90 53 9d 02 0c 54")
    expect(image, 0, 0x0C54,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 "
           "c0 82 c0 83 02 50 30")
    expect(image, 0, 0x5030, "78 0c 80 4a")

    # Bank 12 checks E0 and 03, looks up the code in its 3-byte records,
    # and conditionally sets the corresponding D12D request bit for CFDE=2.
    expect(image, 12, 0x53FC, "90 cf db e0 ff 64 e0 60 02 c3 22")
    expect(image, 12, 0x5407, "90 cf da e0 64 01 60 03 02 5d 73")
    expect(image, 12, 0x5D73,
           "90 cf da e0 64 03 60 03 02 68 d1 90 cf dc e0 12 3c 49")
    expect(image, 0, 0x3C49, "d0 83 d0 82 f8 e4 93")
    expect(image, 12, 0x68A9,
           "90 cf de e0 64 02 70 23 90 d1 2d e0 44 01 80 0d")
    expect(image, 12, 0x68B9,
           "90 cf de e0 b4 02 14 90 d1 2d e0 44 02 f0")
    expect(image, 12, 0x68C6, "f0 12 2c 50 12 2b 9c 80 05")
    expect(image, 12, 0x68D4, "d3 22")

    table = image[12 * BANK_SIZE + 0x5D85:12 * BANK_SIZE + 0x5EB1]
    assert len(table) == 300
    handlers = {record[2]: (record[0] << 8) | record[1]
                for pos in range(0, len(table), 3)
                if (record := table[pos:pos + 3])}
    assert len(handlers) == 100

    for name, frame in SIDEKICK_FRAMES.items():
        assert len(frame) == (frame[1] & 0x7F) + 3 == 8
        checksum = 0
        for byte in frame:
            checksum ^= byte
        assert checksum == 0, "Host reference frame XOR checksum differs"

        # If an intact frame occupies CFD8[0:8], the 8051's index mapping
        # makes these exact fields, including CFDE=02, visible to bank 12.
        assert frame[2:7] == bytes((3, 0xE0, frame[4], 0, 2))
        assert frame[3] != 0xFC  # 13:DDA4 special branch is bypassed.
        assert frame[3] != 0xEC  # 14:FE80 does not consume the E0 family.
        assert frame[2] not in (0xC0, 0xD0)  # bank 7 sets C=0.
        assert frame[6] == 2  # bank 12 checks CFDE, offset 6.
        handler = handlers[frame[4]]
        assert handler == (0x68A9 if name == "APCS" else 0x68B9)
        print(f"PASS {name}: {frame.hex(' ')}; length=8, XOR=00; "
              f"CFDA..CFDE=03 e0 {frame[4]:02x} 00 02; "
              f"conditional target 12:{handler:04X}")

    print("PASS: stock-byte RX layout, non-EC retention branch, bank-7 "
          "carry-clear path, and bank-12 conditional request handlers")
    print("LIMIT: No proof HID payload reaches FF24/FF25 or CFDA..CFDF; "
          "RX checksum/acceptance, D8FE/CFD2/D183 states, intervening "
          "helper effects and physical execution remain unverified")


if __name__ == "__main__":
    audit()
