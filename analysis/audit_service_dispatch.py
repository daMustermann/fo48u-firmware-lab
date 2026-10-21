#!/usr/bin/env python3
"""Static original-F08 audit of the bank-9 service-item enumeration path.

Important: R5=1/R3=0 at the shared dispatcher is NOT evidence that the user
selected a service item. This audit demonstrates a path that generates those
arguments while walking the entire descriptor table. No image is modified.
"""

from hashlib import md5

from build_custom import file_offset, load_source

ORIGINAL_MD5 = "d4324c6c88abea48b1ee896f7e14ee9f"
BANK = 9


def at(image: bytes, bank: int, addr: int, length: int) -> bytes:
    return image[file_offset(bank, addr):file_offset(bank, addr) + length]


def expect(image: bytes, bank: int, addr: int, hex_bytes: str) -> None:
    expected = bytes.fromhex(hex_bytes)
    actual = at(image, bank, addr, len(expected))
    assert actual == expected, (
        f"bank {bank}, address {addr:04X}: expected {expected.hex(' ')}, "
        f"got {actual.hex(' ')}"
    )


def audit(image: bytes | None = None) -> dict[str, object]:
    source = image if image is not None else bytes(load_source())
    assert md5(source).hexdigest() == ORIGINAL_MD5, "Only verified stock F08 can be audited"

    # The little-endian item number plus a one-byte/static state flag.
    entries = [tuple(at(source, BANK, 0x9747 + i * 2, 2)) for i in range(30)]
    assert [entry[0] for entry in entries] == list(range(30))
    assert entries[23] == (23, 1) and entries[24] == (24, 1)

    # Five page descriptors: memory space selector, pointer, entry count.
    pages = []
    for start in (0x9783, 0x9797):
        page_count = 5 if start == 0x9783 else 5
        descriptors = [at(source, BANK, start + 4 * n, 4)
                       for n in range(page_count)]
        pages.append([(p[0], (p[1] << 8) | p[2], p[3]) for p in descriptors])
    assert pages[0] == [
        (0xFF, 0x9747, 2), (0xFF, 0x974B, 8), (0xFF, 0x975B, 13),
        (0xFF, 0x9775, 6), (0xFF, 0x9781, 1),
    ]
    assert pages[1] == [pages[0][4], pages[0][3], *pages[0][:3]]
    for arrangement in pages:
        indexes = []
        for space, pointer, count in arrangement:
            assert space == 0xFF
            assert (pointer - 0x9747) % 2 == 0
            indexes.extend(range((pointer - 0x9747) // 2,
                                 (pointer - 0x9747) // 2 + count))
        assert sorted(indexes) == list(range(30))

    # E48C selects the page's CODE-memory pointer, E4C7 reads the second
    # byte of the item from MOVC through common-bank helper 0:3681.
    expect(source, BANK, 0xE4C7, "ED 75 F0 02 A4 FF E9 2F F9 EA 35 F0 FA 90 00 01 02 36 81")
    expect(source, 0, 0x36AB, "E4 93 22")

    # FEF6 is a CLRC/RET stub in this F08 image: the optional-branch checks
    # at D560, D4C4, F215 never get carry=1 from the callee.
    expect(source, BANK, 0xFEF6, "C3 22")
    expect(source, BANK, 0xD560, "12 FE F6 50 12")
    expect(source, BANK, 0xD4C4, "12 FE F6 50 10")
    expect(source, BANK, 0xF215, "12 FE F6 40 46")

    # The handler is always dispatched as each entry is enumerated.
    expect(source, BANK, 0xD565, "12 E4 F6 12 E4 8C 12 E4 B5")
    expect(source, BANK, 0xD56E, "90 C5 04 E0 FB 7D 01 80 0D")
    expect(source, BANK, 0xD577, "12 E4 F6 12 E4 8C 12 E4 B5 7B 01 E4 FD")
    for caller in (0xD4D6, 0xD584, 0xE0E2, 0xF24C):
        expect(source, BANK, caller, "12 97 DB")
    expect(source, BANK, 0x9835, "02 A1 4C 02 A1 C0")

    # The command-2 branch sets C504=1; commands 0/1/5 use C504=0.
    expect(source, BANK, 0xD516, "90 C5 01 E0 B4 02 08")
    expect(source, BANK, 0xD51D, "90 C5 04 74 01 F0 80 05")
    expect(source, BANK, 0xD525, "E4 90 C5 04 F0")

    # The service items have a 1 flag, so D516 calls D584 with R5=1
    # irrespective of an individual selection event. For commands 0/1/5,
    # R3 also equals 0, matching the abandoned hook's alleged 'key' state.
    dangerous_commands = (0, 1, 5)
    for item in (23, 24):
        assert entries[item][1] == 1
        for command in dangerous_commands:
            r5, r3 = entries[item][1], int(command == 2)
            assert (r5, r3) == (1, 0)

    # Bank-12 refresh commands have no *direct* LCALL/LJMP reference to their
    # entrypoints within their bank; their distinct indirect table is separate.
    bank12 = at(source, 12, 0, 65536)
    for target in (0x68A9, 0x68B9):
        for opcode in (0x02, 0x12):
            assert bytes((opcode, target >> 8, target & 0xFF)) not in bank12

    return {
        "service_item_state": {23: entries[23], 24: entries[24]},
        "D516_enumeration_command_ids_with_R5_1_R3_0": dangerous_commands,
        "D516_enumeration_command_id_with_R5_1_R3_1": 2,
        "D4A0_enumeration_command_ids_with_R5_0_R3_1": (3, 7, 8),
        "shared_dispatcher_callers": (0xD4D6, 0xD584, 0xE0E2, 0xF24C),
    }


if __name__ == "__main__":
    result = audit()
    print("PASS: original F08's five-page service table contains all 30 items")
    print("APCS/AOCS service records:", result["service_item_state"])
    print("D516 enumeration can reach items 23/24 with R5=1, R3=0 on commands 0/1/5.")
    print("Hooking D584 based on item + R5/R3 risks unrequested OLED refresh.")
    print("No flashable menu patch can be justified from these parameters alone.")
