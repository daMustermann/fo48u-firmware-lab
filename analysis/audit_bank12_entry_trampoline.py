#!/usr/bin/env python3
"""Read-only F08 audit: bank-18 caller -> shared stub -> bank-12 entry.

Checks literal stock-image bytes and a direct-LCALL inventory. A reachable
firmware call site does not establish external packet delivery or acceptance.
"""

from hashlib import sha256
from pathlib import Path


IMAGE = (Path(__file__).resolve().parent.parent / "firmware" / "F08-20221115"
         / "FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin")
SHA256 = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
BANK_SIZE = 0x10000


def at(image: bytes, bank: int, address: int, count: int) -> bytes:
    start = bank * BANK_SIZE + address
    return image[start:start + count]


def expect(image: bytes, bank: int, address: int, sequence: str) -> None:
    wanted = bytes.fromhex(sequence)
    actual = at(image, bank, address, len(wanted))
    assert actual == wanted, (
        f"{bank}:{address:04X} (file offset 0x{bank * BANK_SIZE + address:X}): "
        f"expected {wanted.hex(' ')}, got {actual.hex(' ')}"
    )


def audit() -> None:
    image = IMAGE.read_bytes()
    assert len(image) == 2_031_616, "Unexpected F08 image length"
    assert sha256(image).hexdigest() == SHA256, "Unexpected F08 image SHA-256"

    # Shared prefix contains the bank-switch stub, identical in banks 0..19.
    shared = at(image, 0, 0, 0x536C)
    for bank in range(1, 20):
        assert at(image, bank, 0, len(shared)) == shared, bank

    # The bank-18 caller is within a gated handler. D183's bit 2 is tested
    # after two RRC instructions; a zero CFD2 value exits before the calls.
    # The carry from each preceding call controls whether execution proceeds.
    expect(image, 18, 0xD6B2,
           "90 d1 83 e0 ff 13 13 54 3f 30 e0 6f")
    expect(image, 18, 0xD6BE,
           "90 cf d2 e0 24 ff 50 67 12 e2 2d 12 2d ac 40 41 "
           "12 2d b2 40 3c")
    expect(image, 18, 0xD6D3, "90 cf da e0 24 fd 60 15")

    # 18:D6CE LCALL 2DB2 enters the shared 6-byte cross-bank stub.
    # 0:0C54 pushes a synthetic return address from DPTR, then 0:5030
    # selects logical bank 12. 0:507E writes the adjusted selector to
    # XDATA FFFF; RET transfers execution to the saved 12:539D address.
    expect(image, 0, 0x2DB2, "90 53 9d 02 0c 54")
    expect(image, 0, 0x0C54,
           "e5 52 54 1f 23 23 c0 e0 74 50 c0 e0 c0 82 c0 83 02 50 30")
    expect(image, 0, 0x5030, "78 0c 80 4a")
    expect(image, 0, 0x507E, "c8 90 ff ff f5 52 12 0d d0 f0 e8 22")
    expect(image, 0, 0x0DD0, "c0 d0 25 30 d0 d0 22")

    # 12:539D is a real bank-local routine with setup and fallthrough into
    # 12:53FC, which checks the CFDB==E0 family before later CFDA dispatch.
    expect(image, 12, 0x539D,
           "e4 90 c5 00 f0 a3 12 3b 5f 00 00 00 00 e4 90 c5 05 f0 a3 f0")
    expect(image, 12, 0x53C0, "12 35 fc")
    expect(image, 12, 0x53D3, "12 35 fc")
    expect(image, 12, 0x53F1,
           "74 ff f0 a3 74 53 f0 a3 74 78 f0")
    expect(image, 12, 0x53FC, "90 cf db e0 ff 64 e0 60 02 c3 22")
    expect(image, 12, 0x5407, "90 cf da e0 64 01 60 03 02 5d 73")

    # Only one literal 8051 LCALL encoding targets the stub across the 20
    # code banks. Byte scanning is not an exhaustive control-flow proof.
    call = bytes.fromhex("12 2d b2")
    matches = [(bank, address)
               for bank in range(20)
               for address in range(BANK_SIZE - len(call) + 1)
               if at(image, bank, address, len(call)) == call]
    assert matches == [(18, 0xD6CE)], matches

    print(f"PASS: verified stock F08 SHA-256 {SHA256}")
    print("18:D6CE LCALL 0:2DB2 -> 0:0C54 -> 0:5030 -> 0:507E -> 12:539D")
    print("12:539D setup falls through to 12:53FC (CFDB == E0 guard)")
    print("Bank-18 call is conditional on D183/CFD2 and intervening carry flags")
    print("LIMIT: No established external packet origin, accepted command or panel operation")


if __name__ == "__main__":
    audit()
