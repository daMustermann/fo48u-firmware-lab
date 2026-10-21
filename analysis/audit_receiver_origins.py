#!/usr/bin/env python3
"""Offline stock-byte audit of the F08 receiver interrupt and two RX families.

Verifies executable call/stub bytes, bank selectors, receive registers, and
framing. It cannot identify physical pins, USB endpoints, HID reports, or
incoming checksum acceptance. No device I/O or firmware modifications.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parents[1] / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
REFERENCE_HASH = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000


def expect(image: bytes, bank: int, address: int, original: str) -> None:
    wanted = bytes.fromhex(original)
    offset = bank * BANK_SIZE + address
    actual = image[offset:offset + len(wanted)]
    assert actual == wanted, (
        f"{bank}:{address:04X} file 0x{offset:06X}: "
        f"expected {wanted.hex(' ')}, observed {actual.hex(' ')}"
    )


def audit() -> None:
    image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Unexpected stock image length"
    assert sha256(image).hexdigest() == REFERENCE_HASH, "Unexpected stock SHA256"

    # The 8051 vector at 0x0013 conventionally denotes INT1. The actual
    # board-level source or scaler interrupt routing cannot be inferred.
    expect(image, 0, 0x0013, "02 52 0b")                  # vector -> ISR
    expect(image, 0, 0x520B,
           "c0 e0 c0 f0 c0 83 c0 82 c0 d0 75 d0 10 "
           "90 ff f4 e0 90 c9 c1 f0")                     # save IRQ latch
    expect(image, 0, 0x5220,
           "12 0e d4 12 0e da 50 08 12 0e e0 12 0e e6 "
           "80 03 12 0e ec")                             # conditional calls
    expect(image, 0, 0x5233, "90 c9 c1 e0 90 ff f4 f0")  # restore latch
    expect(image, 0, 0x5245, "32")                        # RETI

    # Explicit cross-bank trampolines and selector writes to XDATA 0xFFFF.
    expect(image, 0, 0x0ED4, "90 d4 ec 02 0c 67")       # 13:D4EC
    expect(image, 0, 0x0EDA, "90 fd 57 02 0c 67")       # 13:FD57
    expect(image, 0, 0x0EE0, "90 e3 73 02 0c 67")       # 13:E373
    expect(image, 0, 0x0EE6, "90 ea ce 02 0c 67")       # 13:EACE
    expect(image, 0, 0x0EEC, "90 ba 52 02 0b f5")       # 7:BA52
    expect(image, 0, 0x0C67,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 "
           "c0 82 c0 83 02 50 34")
    expect(image, 0, 0x0BF5,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 "
           "c0 82 c0 83 02 50 1c")
    expect(image, 0, 0x5034, "78 0d 80 46")           # select bank 13
    expect(image, 0, 0x501C, "78 07 80 5e")           # select bank 7
    expect(image, 0, 0x507E,
           "c8 90 ff ff f5 52 12 0d d0 f0 e8 22")

    # 13:FD57: carry=1 iff 14:FE67 returned R7=1 and 0:001E R7!=1.
    # In these routines this means XDATA D183 bit 2 set and IRAM 0x27.5 clear.
    # The choice may depend on earlier work in 13:D4EC; no live values known.
    expect(image, 13, 0xFD57,
           "12 26 68 bf 01 0a 12 00 1e bf 01 02 "
           "c3 22 d3 22 c3 22")
    expect(image, 0, 0x2668, "90 fe 67 02 0c 7a")      # bank-14 stub
    expect(image, 0, 0x0C7A,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 "
           "c0 82 c0 83 02 50 38")
    expect(image, 0, 0x5038, "78 0e 80 42")
    expect(image, 14, 0xFE67,
           "c0 d0 75 d0 10 90 d1 83 e0 13 13 54 3f "
           "30 e0 04 7f 01 80 02 7f 00 d0 d0 22")
    expect(image, 0, 0x001E,
           "c0 d0 75 d0 10 a2 3d e4 33 ff d0 d0 22")

    # The ISR's two bank-13 receivers interrogate paired register windows.
    expect(image, 13, 0xE373, "90 ff 29 12 f7 bb")
    expect(image, 13, 0xE3B1, "90 ff 23 e0 54 fe 64 6e")
    expect(image, 13, 0xEACE, "90 fe 8d 12 f7 bb")
    expect(image, 13, 0xEAFA, "90 fe 87 e0 54 fe 64 6e")
    expect(image, 13, 0xDD3F, "90 ff 24 e0 ff 12 ef 37 12 ef 43")
    expect(image, 13, 0xDE7B, "90 fe 88 e0 ff 90 c9 c2 12 ef 3a 12 ef 43")
    expect(image, 13, 0xDD7A, "90 ff 25 e0 90 c9 c2 12 ef 0d")
    expect(image, 13, 0xDEB3, "90 fe 89 e0 90 c9 c2 12 ef 0d")
    expect(image, 13, 0xEF0D,
           "ff e0 fb a3 e0 fa a3 e0 f9 78 58 e6 06 f5 82 "
           "75 83 00 ef 12 36 c0 90 00 01 12 36 81 54 7f 24 03")
    expect(image, 0, 0x36C0,
           "f8 bb 01 0d e5 82 29 f5 82 e5 83 3a f5 83 e8 f0 22")
    expect(image, 13, 0xDD84, "b5 17 d4 ec b5 16 d0 90 ff 2a 12 ef 4e")
    expect(image, 13, 0xDEBD, "b5 17 da ec b5 16 d6 90 fe 8e 12 ef 4e")
    expect(image, 13, 0xDDA4,
           "12 ef 37 90 00 03 12 36 81 b4 fc 0e "
           "90 00 02 12 36 81 b4 03 05")
    expect(image, 13, 0xDEDD,
           "90 c9 c2 12 ef 3a 90 00 03 12 36 81 b4 fc 0e "
           "90 00 02 12 36 81 b4 03 05")
    expect(image, 13, 0xEF4E, "e0 44 60 f0 e4 f6 75 47 20 22")

    # Third ISR branch: FF24 seed and FF25 data into XDATA D617+index.
    expect(image, 7, 0xBA52, "90 ff 29 e0 54 cf f0")
    expect(image, 7, 0xBA6F, "90 ff 24 e0 90 d6 17 f0")
    expect(image, 7, 0xBAB2,
           "90 ff 25 e0 fe 90 d6 12 e0 24 17 f5 82 "
           "e4 34 d6 f5 83 ee f0")

    # The verified XOR expression is outbound: CF8B = B4^CF85^CF89^CF8A.
    # No claim is made about an incoming checksum acceptance path.
    expect(image, 13, 0xC93E,
           "90 cf 81 74 6e f0 a3 74 88 f0 a3 74 02 f0 e4 a3 f0")
    expect(image, 13, 0xC976,
           "90 cf 85 e0 64 b4 ff 90 cf 89 e0 6f ff a3 e0 6f a3 f0")
    expect(image, 13, 0xC9A5, "90 ff 26 f0")
    expect(image, 13, 0xC9C3, "90 fe 8a f0")
    assert 0x50 ^ 0x6E ^ 0x88 ^ 0x02 ^ 0x00 == 0xB4

    print("PASS: F08 stock hash and byte-verified INT1 vector 0:0013 -> 0:520B")
    print("ISR: 0:5226 JNC selects 7:BA52, else 13:E373 then 13:EACE")
    print("Gate: XDATA D183 bit2 and IRAM 0x27.5; physical transport unknown")
    print("RX: FF24/FF25, FE88/FE89; length=(buffer[1]&0x7f)+3")
    print("RX: special buffer[2:4] == 03 FC branch; no RX checksum demonstrated")
    print("TX only: CF8B=B4^CF85^CF89^CF8A, sent via FF26 or FE8A")
    print("DDC/CI-like TX seed: 50^6E^88^02^00=B4; physical route unverified")
    print("LIMIT: no USB HID endpoint, physical DDC channel or RX checksum proven")


if __name__ == "__main__":
    audit()
