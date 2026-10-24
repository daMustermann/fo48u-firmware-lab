"""Offline F08 E0/FE prototype: allowlisted XDATA telemetry and D8FE routing.

No host sender is exposed. Physical ingress, cave ownership and flash safety
remain unvalidated. Never send these commands to stock F06 or flash this code.
"""
SET_ENTRY, GET_ENTRY = 0xFF00, 0xFF60
READ_ADDRESSES = (0xD12D, 0xD13D, 0xD13E, 0xD8FE)
EVENT_VALUES = (0, 0x10, 0x20)


def control_request(address, value=None):
    """Logical prototype frame only; no transport, no hardware access."""
    if type(address) is not int or address not in READ_ADDRESSES:
        raise ValueError('address is not allowlisted')
    if value is not None and (address != 0xD8FE or type(value) is not int or value not in EVENT_VALUES):
        raise ValueError('only D8FE=00/10/20 is writable')
    frame = [0x51, 0x85 if value is None else 0x86, 1 if value is None else 3,
             0xE0, 0xFE, address >> 8, address & 255]
    if value is not None:
        frame.append(value)
    checksum = 0
    for byte in frame:
        checksum ^= byte
    return bytes((*frame, checksum))


class Assembler:
    def __init__(self, base):
        self.base, self.code, self.labels, self.fixups = base, bytearray(), {}, []

    def emit(self, value):
        self.code.extend(bytes.fromhex(value))

    def label(self, name):
        self.labels[name] = self.base + len(self.code)

    def branch(self, prefix, label):
        self.emit(prefix)
        self.fixups.append((len(self.code), label))
        self.code.append(0)

    def finish(self):
        for position, label in self.fixups:
            rel = self.labels[label] - (self.base + position + 1)
            if not -128 <= rel <= 127:
                raise ValueError("hook branch out of range")
            self.code[position] = rel & 255
        return bytes(self.code)


def make_set():
    a = Assembler(SET_ENTRY)
    a.emit('90 CF DC E0'); a.branch('B4 FE', 'fallback')
    a.emit('90 CF D8 E0'); a.branch('B4 51', 'deny')
    a.emit('A3 E0'); a.branch('B4 86', 'deny')
    a.emit('90 CF D8 7F 09 7E 00')
    a.label('xor'); a.emit('E0 6E FE A3'); a.branch('DF', 'xor')
    a.emit('EE'); a.branch('70', 'deny')
    a.emit('90 CF DD E0'); a.branch('B4 D8', 'deny')
    a.emit('A3 E0'); a.branch('B4 FE', 'deny')
    a.emit('A3 E0'); a.branch('60', 'allowed')
    a.branch('B4 10', 'twenty'); a.branch('80', 'allowed')
    a.label('twenty'); a.branch('B4 20', 'deny')
    a.label('allowed'); a.emit('90 D8 FE F0 D3 22')
    a.label('deny'); a.emit('C3 22')
    a.label('fallback'); a.emit('02 68 CF')
    return a.finish()


def make_get():
    a = Assembler(GET_ENTRY)
    a.emit('90 CF DC E0'); a.branch('B4 FE', 'fallback')
    a.emit('90 CF D8 E0'); a.branch('B4 51', 'deny')
    a.emit('A3 E0'); a.branch('B4 85', 'deny')
    a.emit('90 CF D8 7F 08 7E 00')
    a.label('xor'); a.emit('E0 6E FE A3'); a.branch('DF', 'xor')
    a.emit('EE'); a.branch('70', 'deny')
    a.emit('90 CF DD E0 FE A3 E0 FD EE'); a.branch('B4 D8', 'd1')
    a.emit('ED'); a.branch('B4 FE', 'deny'); a.branch('80', 'read')
    a.label('d1'); a.branch('B4 D1', 'deny')
    a.emit('ED'); a.branch('B4 2D', 'h3d'); a.branch('80', 'read')
    a.label('h3d'); a.branch('B4 3D', 'h3e'); a.branch('80', 'read')
    a.label('h3e'); a.branch('B4 3E', 'deny')
    a.label('read')
    a.emit('8D 82 8E 83 E0 FC')
    a.label('response')
    a.emit('90 CF 86 74 FE F0 A3 E4 F0 A3 74 FF F0 A3 E4 F0 A3 EC F0 02 5D 5A')
    a.label('deny'); a.emit('90 CF 84 74 01 F0 E4 FC'); a.branch('80', 'response')
    a.label('fallback'); a.emit('02 5D 3D')
    return a.finish()


SET_CODE, GET_CODE = make_set(), make_get()
assert SET_ENTRY + len(SET_CODE) <= GET_ENTRY
assert GET_ENTRY + len(GET_CODE) <= 0x10000
HOOK_PATCHES = [
    (12, 0x5520, bytes.fromhex('5D 3D'), GET_ENTRY.to_bytes(2, 'big'), 'Keil GET default target (data, not instructions)'),
    (12, 0x5EB3, bytes.fromhex('68 CF'), SET_ENTRY.to_bytes(2, 'big'), 'Keil SET default target (data, not instructions)'),
    (12, SET_ENTRY, b'\xff' * len(SET_CODE), SET_CODE, 'E0/FE SET: D8FE only, values 00/10/20'),
    (12, GET_ENTRY, b'\xff' * len(GET_CODE), GET_CODE, 'E0/FE GET: allowlisted RAM only'),
]


def apply_control_hook(data, notes):
    bank_data = data[12*65536:13*65536]
    for start, end, expected in ((0x542E, 0x5522, 0x5D3D), (0x5D85, 0x5EB5, 0x68CF)):
        position, cases = start, {}
        while position + 4 <= end:
            target = int.from_bytes(bank_data[position:position+2], 'big')
            if target == 0:
                assert position + 4 == end
                assert int.from_bytes(bank_data[position+2:position+4], 'big') == expected
                break
            selector = bank_data[position+2]
            if selector in cases:
                raise ValueError('duplicate switch case')
            cases[selector] = target
            position += 3
        else:
            raise ValueError('unterminated Keil table')
        if 0xFE in cases:
            raise ValueError('FE is already assigned in stock table')
    for bank, address, old, new, note in HOOK_PATCHES:
        offset = bank * 65536 + address
        if data[offset:offset+len(old)] != old:
            raise ValueError(f"control hook stock mismatch at {bank}:{address:04X}")
        data[offset:offset+len(new)] = new
        notes.append(f'{bank}:{address:04X}: {note}; OFFLINE PROTOTYPE / DO NOT FLASH')


def run_hook(code, base, command, address, value=0, initial=0xA5, length=None, header=0x51, corrupt_checksum=False):
    """Bounded interpreter for the entire injected ISA, including access traces."""
    frame = [header, length if length is not None else (0x86 if base == SET_ENTRY else 0x85),
             3 if base == SET_ENTRY else 1, 0xE0, command, address >> 8, address & 255]
    if base == SET_ENTRY:
        frame.append(value)
    checksum = 0
    for byte in frame:
        checksum ^= byte
    frame.append(checksum ^ int(corrupt_checksum))
    memory = {0xCFD8 + offset: byte for offset, byte in enumerate(frame)}
    memory.update({addr: initial for addr in READ_ADDRESSES})
    registers, reads, writes = [0] * 8, [], []
    pc, a, carry, dptr, stack = base, 0, 0, 0, 2
    for _ in range(200):
        p = pc - base
        op = code[p]
        if op == 0x90:
            dptr = int.from_bytes(code[p+1:p+3], 'big'); pc += 3
        elif op == 0xE0:
            reads.append(dptr); a = memory.get(dptr, 0); pc += 1
        elif op == 0xF0:
            memory[dptr] = a; writes.append((dptr, a)); pc += 1
        elif op == 0xA3:
            dptr = (dptr + 1) & 65535; pc += 1
        elif op == 0x74:
            a = code[p+1]; pc += 2
        elif op == 0xE4:
            a = 0; pc += 1
        elif 0x78 <= op <= 0x7F:
            registers[op-0x78] = code[p+1]; pc += 2
        elif 0x68 <= op <= 0x6F:
            a ^= registers[op-0x68]; pc += 1
        elif 0xF8 <= op <= 0xFF:
            registers[op-0xF8] = a; pc += 1
        elif 0xE8 <= op <= 0xEF:
            a = registers[op-0xE8]; pc += 1
        elif op in (0x8D, 0x8E):
            direct = code[p+1]
            assert direct in (0x82, 0x83)
            v = registers[op-0x88]
            dptr = (dptr & 0xFF00) | v if direct == 0x82 else (v << 8) | (dptr & 255)
            pc += 2
        elif op in (0xC3, 0xD3):
            carry = int(op == 0xD3); pc += 1
        elif op in (0xB4, 0x60, 0x70, 0x80) or 0xD8 <= op <= 0xDF:
            size = 3 if op == 0xB4 else 2
            rel = code[p+size-1]; rel = rel if rel < 128 else rel-256
            if 0xD8 <= op <= 0xDF:
                registers[op-0xD8] = (registers[op-0xD8] - 1) & 255
                take = registers[op-0xD8] != 0
            else:
                take = True if op == 0x80 else a == 0 if op == 0x60 else a != 0 if op == 0x70 else a != code[p+1]
            if op == 0xB4:
                carry = int(a < code[p+1])
            pc += size + (rel if take else 0)
        elif op == 0x02:
            return int.from_bytes(code[p+1:p+3], 'big'), carry, memory, reads, writes, stack
        elif op == 0x22:
            stack -= 2
            return 'ret', carry, memory, reads, writes, stack
        else:
            raise AssertionError(f'unmodeled hook instruction {op:02X}')
        assert base <= pc < base + len(code)
    raise AssertionError('hook did not terminate')


def verify_control_hook():
    # Exhaust every possible address, plus all values and all command IDs.
    cases = 0
    for address in range(65536):
        exit, _, _, reads, writes, stack = run_hook(GET_CODE, GET_ENTRY, 0xFE, address)
        assert exit == 0x5D5A and stack == 2
        assert set(reads) <= {*range(0xCFD8, 0xCFE0), *READ_ADDRESSES}
        assert [addr for addr in reads if addr in READ_ADDRESSES] == ([address] if address in READ_ADDRESSES else [])
        assert all(0xCF84 <= addr <= 0xCF8A for addr, _ in writes)
        exit, carry, _, _, writes, stack = run_hook(SET_CODE, SET_ENTRY, 0xFE, address, 0x10)
        assert exit == 'ret' and stack == 0
        assert writes == ([(0xD8FE, 0x10)] if address == 0xD8FE else [])
        assert carry == int(address == 0xD8FE)
        cases += 2
    for value in range(256):
        _, carry, _, _, writes, stack = run_hook(SET_CODE, SET_ENTRY, 0xFE, 0xD8FE, value)
        assert writes == ([(0xD8FE, value)] if value in EVENT_VALUES else [])
        assert carry == int(value in EVENT_VALUES) and stack == 0
        for code, base, fallback in ((GET_CODE, GET_ENTRY, 0x5D3D), (SET_CODE, SET_ENTRY, 0x68CF)):
            if value != 0xFE:
                exit, _, _, _, writes, stack = run_hook(code, base, value, 0xD8FE)
                assert exit == fallback and not writes and stack == 2
        cases += 1 + (2 if value != 0xFE else 0)
        for address in READ_ADDRESSES:
            _, _, memory, _, _, _ = run_hook(GET_CODE, GET_ENTRY, 0xFE, address, initial=value)
            assert memory[0xCF8A] == value and memory[0xCF86] == 0xFE
            cases += 1
        for code, base, wanted in ((GET_CODE, GET_ENTRY, 0x85), (SET_CODE, SET_ENTRY, 0x86)):
            if value != wanted:
                _, _, memory, _, writes, _ = run_hook(code, base, 0xFE, 0xD8FE, length=value)
                assert not any(address == 0xD8FE for address, _ in writes)
                if base == GET_ENTRY:
                    assert memory[0xCF84] == 1
                cases += 1
    for code, base in ((GET_CODE, GET_ENTRY), (SET_CODE, SET_ENTRY)):
        for bad in ({'header': 0}, {'corrupt_checksum': True}):
            _, _, memory, _, writes, _ = run_hook(code, base, 0xFE, 0xD8FE, **bad)
            assert not any(address == 0xD8FE for address, _ in writes)
            if base == GET_ENTRY:
                assert memory[0xCF84] == 1
            cases += 1
    return cases
