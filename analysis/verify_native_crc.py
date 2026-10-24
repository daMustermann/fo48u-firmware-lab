#!/usr/bin/env python3
"""Emulate the hash-pinned RFlash CRC routine; requires dnfile and unicorn.

No DLL is loaded/executed by the host OS, no device API runs, and no firmware
file is written. Only emulated RAM and an MSVC-cookie stub are modified.
"""
import argparse
import hashlib
from pathlib import Path
from build_custom import load_source
from verify_patch_safety import bank_crc8

DLL_SHA256 = '09586d4b2cfd5d80b20ad3bf2ee2b01fd080260f0753e83c8ec32eaf3b0ec652'
FUNCTION_SHA256 = 'd97be5736c67e3a0e87cb749fe0d115941fb7dea5d8be2a10c68d3313920d686'


def verify(path):
    import dnfile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_CR4
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != DLL_SHA256:
        raise ValueError('unknown RFlash.dll; refusing a different build')
    pe = dnfile.dnPE(data=raw)
    assert hashlib.sha256(pe.get_data(0x2540, 0x1F0)).hexdigest() == FUNCTION_SHA256
    stock = bytes(load_source())
    cases = [('zero', bytes(65536)), ('incrementing', bytes(range(256))*256),
             ('stock bank12', stock[12*65536:13*65536])]
    results = []
    for name, data in cases:
        emulator = Uc(UC_ARCH_X86, UC_MODE_32)
        emulator.mem_map(0x10000000, 0x60000)
        emulator.mem_write(0x10000000, pe.get_memory_mapped_image())
        emulator.mem_map(0x200000, 0x20000)
        emulator.mem_map(0x300000, 0x1000)
        emulator.mem_write(0x1001706E, b'\xC3')  # cookie check only, in emulator RAM
        emulator.mem_write(0x1003E2F8, data)
        emulator.mem_write(0x210000, (0x300000).to_bytes(4, 'little'))
        emulator.reg_write(UC_X86_REG_ESP, 0x210000)
        emulator.reg_write(UC_X86_REG_CR4, 0x600)
        emulator.emu_start(0x10002540, 0x300000, timeout=20_000_000, count=20_000_000)
        assert emulator.reg_read(UC_X86_REG_EIP) == 0x300000, 'emulation did not return'
        actual = emulator.reg_read(UC_X86_REG_EAX) & 255
        assert actual == bank_crc8(data), (name, actual)
        results.append((name, actual))
        print(f'PASS: vendor emulation / Python CRC {name}: {actual:02X}')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rflash', type=Path)
    verify(parser.parse_args().rflash)
