"""Offline regressions for byte-preserving firmware tools. No image outputs."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch as mock_patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'analysis'))
import patch as firmware_patch
from verify_patch_safety import bank_crc8, verify_aocs_carry
from build_custom import load_source
from verify_menu_patch import selector_evidence
from control_hook import verify_control_hook, apply_control_hook, control_request
from build_custom import patch_unlock
import build_variant


class AnalysisSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = bytes(load_source())
        cls.bank = cls.stock[12*65536:13*65536]

    def test_patch_rejects_resize_bounds_overlap_and_bank_confusion(self):
        record = {'bank': 12, 'offset': 0x68BD, 'old': 'B4 02 14', 'new': 'C3 74 02'}
        changed = firmware_patch.apply_patches(self.bank, [record], 12, self.bank)
        self.assertEqual(len(changed), 65536)
        self.assertEqual(changed[0x68BD:0x68C0], bytes.fromhex('C3 74 02'))
        bad = [{'new': '00'}, {'offset': -1}, {'offset': 65535}, {'offset': True},
               {'bank': 11}, {'old': '00 00 00'}, {'bank': True}]
        for changes in bad:
            with self.assertRaises(ValueError):
                firmware_patch.apply_patches(self.bank, [{**record, **changes}], 12, self.bank)
        with self.assertRaises(ValueError):
            firmware_patch.apply_patches(self.bank, [record, record], 12, self.bank)
        with self.assertRaises(ValueError):
            firmware_patch.apply_patches(changed, [record], 12, self.bank)

    def test_reassembly_preserves_all_stock_banks_without_data_bank_files(self):
        self.assertEqual(firmware_patch.reassemble(self.stock), self.stock)
        original = Path.read_bytes
        def overlay(path):
            value = original(path)
            if path.name == 'bank_0.bin':
                return bytes((value[0] ^ 1,)) + value[1:]
            return value
        with mock_patch.object(Path, 'read_bytes', overlay):
            changed = firmware_patch.reassemble(self.stock)
        self.assertNotEqual(changed[0], self.stock[0])
        self.assertEqual(changed[20*65536:], self.stock[20*65536:])

    def test_protected_outputs_refused_before_open(self):
        for path in [firmware_patch.IMG, *(firmware_patch.BANKS_DIR / f'bank_{b}.bin' for b in range(31))]:
            with self.assertRaises(ValueError):
                firmware_patch.write_output(path, b'never written')

    def test_carry_state_and_menu_selectors(self):
        self.assertEqual(verify_aocs_carry(self.stock), 131072)
        self.assertEqual(selector_evidence(self.stock)['item_id_selector'], '9:E4B8')

    def test_full_control_hook_and_default_table_scope(self):
        self.assertEqual(verify_control_hook(), 133376)
        unlocked = bytearray(self.stock)
        patch_unlock(unlocked, [])
        hooked = bytearray(unlocked)
        apply_control_hook(hooked, [])
        self.assertNotEqual(hooked, unlocked)
        self.assertEqual(hooked[0xC5520:0xC5522], bytes.fromhex('FF 60'))
        self.assertEqual(hooked[0xC5EB3:0xC5EB5], bytes.fromhex('FF 00'))
        variant = bytearray(self.stock)
        for name in build_variant.VARIANTS['F08-full-control'][0]:
            build_variant.apply_patch(variant, name)
        self.assertEqual(hooked, variant)

    def test_crc_matches_native_emulation_vectors(self):
        self.assertEqual(bank_crc8(bytes(65536)), 0)
        self.assertEqual(bank_crc8(bytes(range(256)) * 256), 0x17)
        self.assertEqual(bank_crc8(self.bank), 0x4F)
        with self.assertRaises(ValueError):
            bank_crc8(b'wrong size')

    def test_control_frames_are_offline_and_allowlisted(self):
        for frame in (control_request(0xD13D), control_request(0xD8FE, 0x10)):
            checksum = 0
            for byte in frame:
                checksum ^= byte
            self.assertEqual(checksum, 0)
            self.assertEqual(len(frame), (frame[1] & 0x7F) + 3)
            self.assertEqual(frame[3:5], bytes.fromhex('E0 FE'))
        for args in ((0xFFFF,), (0xD12D, 1), (0xD8FE, 0xFF)):
            with self.assertRaises(ValueError):
                control_request(*args)


if __name__ == '__main__':
    unittest.main()
