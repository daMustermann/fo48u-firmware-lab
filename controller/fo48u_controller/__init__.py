"""Minimal, safety-gated host-side controller for the Gigabyte AORUS FO48U.

This package wraps the byte-verified Realtek-HID frames documented in
analysis/sidekick-protocol.md.  It does not claim that any OLED-care
execution command has been hardware-validated.
"""

__version__ = "0.1.0"
__all__ = ["transport", "oled", "cli"]