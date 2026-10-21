#!/usr/bin/env python3
"""Read-only bytecode evidence for the FO48U incoming DDC/CI field layout.

Checks the exact stock F08 image. This is static analysis and neither sends
DDC/CI requests nor modifies firmware or a monitor.
"""

from collections import Counter
from hashlib import md5

from build_custom import file_offset, load_source


STOCK_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"


def expect(blob: bytes, bank: int, address: int, hex_bytes: str) -> None:
    want = bytes.fromhex(hex_bytes)
    start = file_offset(bank, address)
    got = blob[start : start + len(want)]
    assert got == want, (
        f"bank {bank}:{address:04X}: expected {want.hex(' ')}, "
        f"got {got.hex(' ')}"
    )


def audit() -> dict[str, object]:
    image = bytes(load_source())
    assert len(image) == 31 * 0x10000
    assert md5(image).hexdigest() == STOCK_MD5

    # A second dispatcher routes CFDA through 03, 07, 0C, F3, 01.
    # Standard DDC/CI requests: 01=Get VCP, 03=Set VCP,
    # 07=Get Timing Report, 0C=Save Current Settings,
    # F3=Capabilities Request (VESA DDC/CI 1.1, sections 4.3-4.7).
    # This opcode agreement does not prove the bank-12 transport.
    expect(image, 18, 0xD6D3,
           "90 cf da e0 24 fd 60 15 24 fc 60 16 24 fb 60 2c "
           "24 19 60 1b 24 f2 70 21")
    expect(image, 18, 0xD6EB, "12 85 66 80 1f")   # CFDA 01
    expect(image, 18, 0xD6F0, "12 7b ef 80 1a")   # CFDA 03
    expect(image, 18, 0xD6F5, "90 d1 46 e0 ff")   # CFDA 07
    expect(image, 18, 0xD702, "90 cf d1 e0 ff")   # CFDA F3

    # The 12:53FC path selects command E0, mode/opcode 03, command ID CFDC.
    expect(image, 12, 0x53FC, "90 cf db e0 ff 64 e0 60 02 c3 22")
    expect(image, 12, 0x5D73, "90 cf da e0 64 03 60 03 02 68 d1")
    expect(image, 12, 0x5D7E, "90 cf dc e0 12 3c 49")

    # CFDE is reused by many handlers as an incoming operand, not just in
    # APCS/AOCS. Here it selects a response-array index (bank 7) and forms a
    # two-byte number CFDE*100+CFDF (bank 12).
    expect(image, 7, 0x7CF7,
           "90 cf de e0 24 88 f5 82 e4 34 cf f5 83 ef f0")
    expect(image, 12, 0xD2E9,
           "90 cf de e0 75 f0 64 a4 ff a3 e0")
    expect(image, 7, 0x6A88,
           "90 cf de e0 90 d6 55 f0")

    # The refresh commands do require CFDE==2. Removing that condition
    # changes their packet operand validation; it is not a proven UI unlock.
    expect(image, 12, 0x68A9, "90 cf de e0 64 02 70 23")
    expect(image, 12, 0x68B9, "90 cf de e0 b4 02 14")

    refs = Counter()
    for bank in range(20):
        code = image[bank * 0x10000 : (bank + 1) * 0x10000]
        refs["CFDA"] += code.count(bytes.fromhex("90 cf da"))
        refs["CFDE"] += code.count(bytes.fromhex("90 cf de"))
    # These are byte-pattern counts, not a complete control-flow/xref proof.
    assert refs["CFDA"] == 8
    assert refs["CFDE"] == 78
    return {
        "CFDA_byte_pattern_refs": refs["CFDA"],
        "CFDE_byte_pattern_refs": refs["CFDE"],
        "CFDA_dispatch_codes": ["01", "03", "07", "0C", "F3"],
        "CFDE_uses": ["refresh operand == 02", "array index", "CFDE*100+CFDF"],
    }


if __name__ == "__main__":
    for key, value in audit().items():
        print(f"{key}: {value}")
    print("PASS: read-only opcode/operand evidence (no host transport proof)")
