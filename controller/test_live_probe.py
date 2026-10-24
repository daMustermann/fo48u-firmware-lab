"""Offline safety regressions. All simulated I/O lives only in this test module."""
import ast
import ctypes
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import live_probe as probe
from fo48u_controller.cli import _NullTransport, main as cli_main
from fo48u_controller.helper_transport import HelperTransport
from fo48u_controller.oled import OledCare, decode_status_reply, decode_standard_reply
from fo48u_controller.transport import RtHidTransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from verify_patch_safety import boundaries, relative_target
import build_custom


class ProbeTests(unittest.TestCase):
    def test_firmware_identity_never_inherits_static_reference_version(self):
        self.assertEqual(probe.firmware_identity(),
                         {"version": None, "source": "unknown", "verified_by_probe": False})
        self.assertEqual(probe.firmware_identity("F06"),
                         {"version": "F06", "source": "operator_supplied", "verified_by_probe": False})

    def test_capabilities_excludes_nested_value_tokens(self):
        raw = "(vcp(10 14(01 02 0B) 60(0F 11) E0 DF))"
        self.assertEqual(probe.advertised_codes(raw), [0x10, 0x14, 0x60, 0xDF, 0xE0])
        self.assertIsNone(probe.advertised_codes("vcp(10 12"))
        self.assertIsNone(probe.advertised_codes(None))

    def test_references_do_not_promote_vendor_subcommands_to_vcp(self):
        refs = probe.reference_index()
        self.assertIn("not a VCP mapping", refs["interpretation"])
        self.assertEqual(refs["codes"]["0x80"]["kb_vendor_command"]["handler"], "12:68A9")
        self.assertTrue(refs["codes"]["0x80"]["atlas_numeric_case_matches"])

    def test_failure_and_zero_success_remain_distinct(self):
        report = {"vcp": {"0x10": {"status": "responded", "current": 0,
                    "maximum_raw": 100, "vcp_type_raw": 0},
                    "0x11": {"status": "get_failed", "win32_error": 31},
                    "0x12": {"status": "not_attempted"}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            probe.save_report(path, report)
            loaded = json.loads(path.read_text())
        self.assertEqual(loaded["summary"]["responded"], 1)
        self.assertEqual(loaded["summary"]["get_failed"], 1)
        self.assertEqual(loaded["summary"]["not_attempted"], 1)
        self.assertNotIn("current", loaded["vcp"]["0x11"])

    def test_probe_has_no_control_transport_dependencies(self):
        tree = ast.parse(Path(probe.__file__).read_text())
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse(names & {"SetVCPFeature", "RtHidTransport", "HelperTransport", "OledCare"})
        self.assertFalse(hasattr(probe.ReadOnlyDdc, "set_vcp"))
        self.assertFalse(hasattr(probe.ReadOnlyDdc, "i2c_write"))

    def test_partial_instruction_and_signed_relative_detection(self):
        with self.assertRaises(AssertionError):
            boundaries(bytes.fromhex("90 D1 2D"), 0, 2)
        self.assertEqual(relative_target(bytes.fromhex("80 FE"), 0), 0)
        self.assertEqual(relative_target(bytes.fromhex("B4 02 FD"), 0), 0)
        self.assertEqual(relative_target(bytes.fromhex("D8 FE"), 0), 0)
        self.assertEqual(relative_target(bytes.fromhex("D5 20 FD"), 0), 0)
        self.assertEqual(relative_target(bytes.fromhex("20 E0 FD"), 0), 0)
        for opcode in (0x40, 0x50, 0x60, 0x70, 0x80, *range(0xD8, 0xE0)):
            self.assertEqual(relative_target(bytes((opcode, 0xFE)), 0), 0)
        for opcode in (0x10, 0x20, 0x30, 0xD5, *range(0xB4, 0xC0)):
            self.assertEqual(relative_target(bytes((opcode, 0x20, 0xFD)), 0), 0)

    def test_deadline_terminates_worker_and_reports_partial_failure(self):
        context, parent, child, process = Mock(), Mock(), Mock(), Mock()
        context.Pipe.return_value = parent, child
        context.Process.return_value = process
        process.is_alive.return_value = True
        events = []
        with patch.object(probe.mp, "get_context", return_value=context), patch.object(probe.time, "monotonic", side_effect=[0, 2]):
            probe.collect(0, "FO48U", 0.1, 1, lambda kind, value: events.append((kind, value)))
        process.terminate.assert_called_once()
        self.assertIn("partial", events[0][1])

    def test_full_control_preset_resolves_without_writing_firmware(self):
        with patch.object(build_custom, "verify_all"), patch.object(build_custom, "build", return_value={}) as build:
            self.assertEqual(build_custom.main(["build_custom.py", "--emit-offline-research",
                                               "--preset", "full-control", "--no-manifest"]), 0)
        self.assertEqual(build.call_args.args[0].name, "F08-full-control")
        self.assertTrue(build.call_args.args[0].unlock)


class TransportTests(unittest.TestCase):
    def transport(self):
        transport = object.__new__(RtHidTransport)
        transport.dll = Mock()
        transport.vid, transport.pid, transport._opened = 0x0BDA, 0x1100, True
        return transport

    def test_failed_native_reads_never_return_zero_buffer(self):
        transport = self.transport()
        for status in (-2, -1, 1, 2):
            transport.dll.HID_i2cread.return_value = status
            with self.assertRaises(OSError):
                transport.i2c_read()

    def test_native_zero_status_is_success(self):
        transport = self.transport()

        def fill(reg, reglen, pointer, length, slave, speed, timeout):
            ctypes.memmove(pointer, bytes(range(length)), length)
            return 0

        transport.dll.HID_i2cread.side_effect = fill
        self.assertEqual(transport.i2c_read(buf_len=36), list(range(36)))
        transport.dll.HID_i2cwrite.return_value = 1
        with self.assertRaises(OSError):
            transport.i2c_write([0x51] * 32)

    def test_open_fallback_checks_its_return_value(self):
        transport = self.transport()
        transport.dll.Open_HID.return_value = 0
        transport.dll.Get_mutiHID.return_value = 1
        transport.dll.Open_mutiHID.return_value = 1
        with self.assertRaises(OSError):
            transport.open()
        transport.dll.Open_mutiHID.return_value = 0
        transport.open()
        self.assertTrue(transport._opened)

    def test_helper_refuses_failed_missing_and_short_data(self):
        transport = object.__new__(HelperTransport)
        for response in ({"ok": True, "result": 1, "bytes": [0] * 36},
                         {"ok": True, "result": False, "bytes": [0] * 36},
                         {"ok": True, "bytes": [0] * 36},
                         {"ok": True, "result": 0, "bytes": [1, 2]}):
            transport._send = Mock(return_value=response)
            with self.assertRaises(OSError):
                transport.i2c_read()

    def test_dry_run_never_fabricates_hardware_data(self):
        care = OledCare(_NullTransport(), dry_run=True)
        self.assertIsNone(care.read_panel_hours())
        self.assertEqual(care.execute_aocs()[:8], [0x51, 0x85, 3, 0xE0, 0x82, 0, 2, 0xB7])
        with self.assertRaises(RuntimeError):
            _NullTransport().i2c_read()
        with patch("fo48u_controller.ddcci.DdcCi") as ddc, patch("fo48u_controller.cli.RtHidTransport") as hid:
            self.assertEqual(cli_main(["scan-vcp"]), 0)
            self.assertEqual(cli_main(["dump-state"]), 0)
            ddc.assert_not_called()
            hid.assert_not_called()

    def test_stale_helper_is_rejected_before_hardware_open(self):
        process = Mock()
        process.stdout = io.StringIO('{"ready":true}\n')
        with patch("fo48u_controller.helper_transport.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "protocol 2 required"):
                HelperTransport("unused.exe")
        process.terminate.assert_called_once()

    def test_status_frame_validates_checksum_echo_and_framing(self):
        # Fixed captured F06 version frame; trailing bridge buffer data is opaque.
        frame = list(bytes.fromhex('6E 88 02 00 E0 38 FF FF 46 06 2C')) + [0] * 25
        self.assertEqual(decode_status_reply(frame, 0x38)['value'], 0x4606)
        for index in range(11):
            changed = list(frame)
            changed[index] ^= 1
            with self.assertRaises(OSError):
                decode_status_reply(changed, 0x38)
        with self.assertRaises(OSError):
            decode_status_reply(frame, 0x7F)

    def test_standard_get_rejects_vendor_shaped_e0_reply(self):
        df = list(bytes.fromhex('6E 88 02 00 DF 00 FF FF 02 02 6B')) + [0]*25
        self.assertEqual(decode_standard_reply(df, 0xDF)['value'], 0x0202)
        vendor = list(bytes.fromhex('6E 88 02 00 E0 32 00 07 00 01 60')) + [0]*25
        with self.assertRaisesRegex(OSError, 'type'):
            decode_standard_reply(vendor, 0xE0)
        with self.assertRaisesRegex(OSError, 'echo'):
            decode_standard_reply(df, 0xE0)

    def test_read_only_helper_rejects_arbitrary_selectors_locally(self):
        helper = object.__new__(HelperTransport)
        helper.read_only = True
        helper._send = Mock()
        for selector in (0x55, 0xEC, -1, 256):
            with self.assertRaises(ValueError):
                helper.status_query(selector)
        helper._send.assert_not_called()

    def test_oled_rejects_empty_or_malformed_replies(self):
        transport = Mock()
        care = OledCare(transport, dry_run=False, sleeper=lambda _: None)
        for response in ([0] * 36, [255] * 36, [1] * 9, [256] * 36):
            transport.i2c_read.return_value = response
            with self.assertRaises(OSError):
                care.read_panel_hours()
        with self.assertRaises(PermissionError):
            care.execute_apcs(confirmed=True)


if __name__ == "__main__":
    unittest.main()
