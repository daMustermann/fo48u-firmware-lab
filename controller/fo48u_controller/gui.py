"""Modern customtkinter GUI for the FO48U controller (experimental, safety-gated)."""

from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from .ddcci import DdcCi
from .helper_transport import HelperTransport
from .oled import OledCare
from .transport import RtHidTransport

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VCP_NAMES = {
    0x02: "New control value",
    0x04: "Restore factory defaults",
    0x05: "Restore brightness/contrast defaults",
    0x06: "Restore color defaults",
    0x08: "Restore geometry defaults",
    0x0B: "Color temperature request",
    0x0C: "Image mode",
    0x10: "Brightness",
    0x12: "Contrast",
    0x14: "Select color preset",
    0x16: "Red gain",
    0x18: "Green gain",
    0x1A: "Blue gain",
    0x1E: "Auto setup",
    0x20: "Horizontal position",
    0x30: "Vertical position",
    0x52: "Active control",
    0x60: "Input select",
    0x62: "Volume",
    0x6C: "Black level",
    0x6E: "Black stabilizer",
    0x70: "Gamma",
    0x86: "Display scaling",
    0x87: "Sharpness",
    0xAC: "Horizontal frequency",
    0xAE: "Vertical frequency",
    0xB2: "Source timing mode",
    0xB6: "Display technology type",
    0xC6: "Application enable key",
    0xC8: "Display controller type",
    0xC9: "Display firmware level",
    0xCA: "OSD / button control",
    0xCC: "OSD language",
    0xD6: "Power mode",
    0xDF: "Manufacturer specific",
    0xE0: "Manufacturer specific",
    0xEC: "Manufacturer specific",
}

PAGES = [
    ("Dashboard", "📊"),
    ("OLED care", "🔋"),
    ("Display", "🖥️"),
    ("Audio", "🔊"),
    ("Gaming", "🎮"),
    ("Crosshair", "🎯"),
    ("Firmware", "💾"),
    ("Hardware", "📈"),
    ("Profiles", "📁"),
    ("Diagnostics", "🧪"),
    ("Tests", "🎨"),
    ("Settings", "⚙️"),
    ("Log", "📜"),
]


class Fo48uGui:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("FO48U Controller")
        self.root.geometry("1320x860")
        self.root.minsize(1120, 720)

        self.connected = ctk.BooleanVar(value=False)
        self.write_enabled = ctk.BooleanVar(value=False)
        self.transport = None
        self.care = None
        self.ddc = None
        self._worker = None

        self.oled_vars = {k: ctk.StringVar(value="—") for k in
                          ("panel_hours", "apcs_time", "aocs_time", "apcs_enable", "aocs_enable")}
        self.vcp_vars = {}
        self.all_vcp = [
            (0x04, 1), (0x05, 1), (0x06, 1), (0x10, 100), (0x12, 100), (0x14, 11),
            (0x16, 100), (0x18, 100), (0x1A, 100), (0x1E, 1), (0x20, 1), (0x30, 1),
            (0x52, 1), (0x60, 3), (0x62, 100), (0x6C, 100), (0x6E, 100), (0x70, 100),
            (0x87, 10), (0xB6, 5), (0xC6, 255), (0xCC, 13), (0xD6, 5),
        ]
        self.all_vars = {}
        self.crosshair_index = ctk.IntVar(value=1)
        self.hw_text = ctk.StringVar(value="Not refreshed")
        self.info_text = ctk.StringVar(value="Not refreshed")
        self.custom_code = ctk.StringVar(value="0xE5")
        self.custom_value = ctk.IntVar(value=50)
        self.custom_result = ctk.StringVar(value="—")
        self.auto_refresh = ctk.BooleanVar(value=False)

        self.pages = {}
        self.current_page = None

        self._build_layout()
        self.log("Ready. Read-only mode is active by default.")

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self.root, width=210, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="FO48U", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(18, 4))
        ctk.CTkLabel(sidebar, text="Controller", text_color="#9aa3b2").pack(pady=(0, 14))

        self.page_buttons = {}
        for name, icon in PAGES:
            btn = ctk.CTkButton(sidebar, text=f"  {icon}  {name}", anchor="w", fg_color="transparent",
                                hover_color="#2a2f45", command=lambda n=name: self.show_page(n))
            btn.pack(fill="x", padx=10, pady=3)
            self.page_buttons[name] = btn

        bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=10, pady=12)
        self.connect_switch = ctk.CTkSwitch(bottom, text="Connect", variable=self.connected, command=self._toggle_connect)
        self.connect_switch.pack(fill="x", pady=4)
        self.write_switch = ctk.CTkSwitch(bottom, text="Write access", variable=self.write_enabled, command=self._toggle_write)
        self.write_switch.pack(fill="x", pady=4)
        self.status_label = ctk.CTkLabel(bottom, text="read-only", text_color="#9aa3b2")
        self.status_label.pack(pady=(8, 0))

        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.page_container = ctk.CTkFrame(main, corner_radius=16)
        self.page_container.grid(row=0, column=0, sticky="nsew")
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

        self._build_pages()
        self.show_page("Dashboard")

    def _build_pages(self) -> None:
        self.pages["Dashboard"] = self._page_dashboard()
        self.pages["OLED care"] = self._page_oled()
        self.pages["Display"] = self._page_display()
        self.pages["Audio"] = self._page_audio()
        self.pages["Gaming"] = self._page_gaming()
        self.pages["Crosshair"] = self._page_crosshair()
        self.pages["Firmware"] = self._page_firmware()
        self.pages["Hardware"] = self._page_hardware()
        self.pages["Profiles"] = self._page_profiles()
        self.pages["Diagnostics"] = self._page_diagnostics()
        self.pages["Tests"] = self._page_tests()
        self.pages["Settings"] = self._page_settings()
        self.pages["Log"] = self._page_log()

    def show_page(self, name: str) -> None:
        if self.current_page is not None:
            self.pages[self.current_page].grid_forget()
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        self.current_page = name
        for n, btn in self.page_buttons.items():
            btn.configure(fg_color="#2a2f45" if n == name else "transparent")

    # --------------------------------------------------------------- pages
    def _page_dashboard(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Dashboard", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))

        cards = ctk.CTkFrame(page, fg_color="transparent")
        cards.pack(fill="x", padx=14)
        items = [
            ("Panel hours", self.oled_vars["panel_hours"]),
            ("Brightness", None),
            ("Volume", None),
            ("Input", None),
        ]
        for i, (label, var) in enumerate(items):
            card = ctk.CTkFrame(cards, corner_radius=14)
            card.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=label, text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(12, 2))
            value = var if var is not None else ctk.StringVar(value="—")
            ctk.CTkLabel(card, textvariable=value, font=ctk.CTkFont(size=24, weight="bold"), text_color="#00d4ff").pack(anchor="w", padx=14, pady=(0, 12))
            cards.columnconfigure(i, weight=1)

        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkButton(row, text="Refresh all", command=self._refresh_all).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Trigger APCS", fg_color="#ff5c7a", hover_color="#ff7a93", command=lambda: self._trigger("apcs")).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Trigger AOCS", fg_color="#ff5c7a", hover_color="#ff7a93", command=lambda: self._trigger("aocs")).pack(side="left", padx=6)
        return page

    def _page_oled(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="OLED care", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))

        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="x", padx=14)
        items = [
            ("Panel hours", "panel_hours"),
            ("APCS elapsed (h)", "apcs_time"),
            ("AOCS elapsed (h)", "aocs_time"),
            ("APCS enable/status", "apcs_enable"),
            ("AOCS enable/status", "aocs_enable"),
        ]
        for i, (label, key) in enumerate(items):
            card = ctk.CTkFrame(grid, corner_radius=14)
            card.grid(row=i // 3, column=i % 3, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=label, text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(card, textvariable=self.oled_vars[key], font=ctk.CTkFont(size=24, weight="bold"), text_color="#00d4ff").pack(anchor="w", padx=14, pady=(0, 12))
            grid.columnconfigure(i % 3, weight=1)

        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkButton(row, text="Refresh", command=self._refresh_oled).pack(side="left", padx=6)
        self.apcs_button = ctk.CTkButton(row, text="Trigger APCS", fg_color="#ff5c7a", hover_color="#ff7a93", command=lambda: self._trigger("apcs"))
        self.apcs_button.pack(side="left", padx=6)
        self.aocs_button = ctk.CTkButton(row, text="Trigger AOCS", fg_color="#ff5c7a", hover_color="#ff7a93", command=lambda: self._trigger("aocs"))
        self.aocs_button.pack(side="left", padx=6)
        self._update_action_state()
        return page

    def _page_display(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Display", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        scroll = ctk.CTkScrollableFrame(page, corner_radius=14)
        scroll.pack(fill="both", expand=True, padx=14, pady=8)

        for name, code in [("Brightness", 0x10), ("Contrast", 0x12), ("Red gain", 0x16), ("Green gain", 0x18),
                           ("Blue gain", 0x1A), ("Sharpness", 0x87), ("Black level", 0x6C), ("Black stabilizer", 0x6E),
                           ("Volume", 0x62), ("Gamma", 0x70)]:
            self._vcp_row(scroll, name, code)

        # Extended controls
        ext = ctk.CTkFrame(scroll, corner_radius=14)
        ext.pack(fill="x", pady=8)
        ctk.CTkLabel(ext, text="Extended", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))

        r1 = ctk.CTkFrame(ext, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r1, text="Input source").pack(side="left")
        self.input_var = ctk.StringVar(value="HDMI 1")
        ctk.CTkOptionMenu(r1, values=["HDMI 1", "HDMI 2", "DisplayPort", "USB-C"], variable=self.input_var).pack(side="left", padx=10)
        ctk.CTkButton(r1, text="Apply", width=90, command=self._apply_input).pack(side="left", padx=6)

        r2 = ctk.CTkFrame(ext, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r2, text="Color preset").pack(side="left")
        self.color_var = ctk.StringVar(value="6500K")
        ctk.CTkOptionMenu(r2, values=["5000K", "6500K", "7500K", "9300K", "sRGB", "Native"], variable=self.color_var).pack(side="left", padx=10)
        ctk.CTkButton(r2, text="Apply", width=90, command=self._apply_color).pack(side="left", padx=6)

        r3 = ctk.CTkFrame(ext, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=4)
        self.mute_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(r3, text="Mute", variable=self.mute_var, command=self._apply_mute).pack(side="left")
        ctk.CTkButton(r3, text="Factory reset", fg_color="#ff5c7a", hover_color="#ff7a93", command=self._factory_reset).pack(side="right", padx=6)

        # Custom VCP
        custom = ctk.CTkFrame(scroll, corner_radius=14)
        custom.pack(fill="x", pady=8)
        ctk.CTkLabel(custom, text="Custom VCP", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        crow = ctk.CTkFrame(custom, fg_color="transparent")
        crow.pack(fill="x", padx=14, pady=4)
        self.custom_code = ctk.StringVar(value="0xE5")
        ctk.CTkEntry(crow, textvariable=self.custom_code, width=80).pack(side="left")
        self.custom_value = ctk.IntVar(value=50)
        ctk.CTkSlider(crow, from_=0, to=255, variable=self.custom_value).pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(crow, text="Read", width=70, command=self._read_custom_vcp).pack(side="left", padx=4)
        ctk.CTkButton(crow, text="Apply", width=70, command=self._apply_custom_vcp).pack(side="left", padx=4)
        self.custom_result = ctk.StringVar(value="—")
        ctk.CTkLabel(custom, textvariable=self.custom_result, text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(2, 10))

        # All controls
        allf = ctk.CTkFrame(scroll, corner_radius=14)
        allf.pack(fill="x", pady=8)
        ctk.CTkLabel(allf, text="All VCP controls", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        self.all_vars = {}
        for code, maximum in self.all_vcp:
            row = ctk.CTkFrame(allf, corner_radius=10)
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(row, text=f"0x{code:02X} {VCP_NAMES.get(code, '')}", width=220).pack(side="left", padx=8)
            var = ctk.IntVar(value=0)
            self.all_vars[code] = var
            ctk.CTkSlider(row, from_=0, to=maximum if maximum > 0 else 255, variable=var).pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkButton(row, text="Apply", width=70, command=lambda c=code, v=var: self._apply_all_vcp(c, v.get())).pack(side="right", padx=8)

        ctk.CTkButton(page, text="Read all VCP", command=self._read_vcp).pack(anchor="w", padx=14, pady=8)
        return page

    def _vcp_row(self, parent, name, code):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.pack(fill="x", pady=4)
        ctk.CTkLabel(card, text=name, width=150).pack(side="left", padx=10)
        var = ctk.IntVar(value=50)
        self.vcp_vars[code] = var
        ctk.CTkSlider(card, from_=0, to=100, variable=var).pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(card, text="Apply", width=80, command=lambda c=code, v=var: self._apply_vcp(c, v.get())).pack(side="right", padx=10)

    def _page_audio(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Audio", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Volume", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        var = ctk.IntVar(value=30)
        self.vcp_vars[0x62] = var
        ctk.CTkSlider(card, from_=0, to=100, variable=var).pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(card, text="Apply volume", command=lambda: self._apply_vcp(0x62, var.get())).pack(anchor="e", padx=14, pady=8)
        mute = ctk.CTkFrame(card, fg_color="transparent")
        mute.pack(fill="x", padx=14, pady=6)
        self.mute_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(mute, text="Mute", variable=self.mute_var, command=self._apply_mute).pack(side="left")
        return page

    def _page_gaming(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Gaming", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Game-oriented controls", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        for name, code in [("Black stabilizer", 0x6E), ("Sharpness", 0x87), ("Color preset", 0x14)]:
            self._vcp_row(card, name, code)
        ctk.CTkLabel(card, text="Use Custom VCP for overdrive / aim stabilizer vendor codes.", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=8)
        return page

    def _page_crosshair(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Crosshair", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Hardware crosshair (monitor OSD)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row, text="Preset index").pack(side="left")
        ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, 8)], variable=self.crosshair_index).pack(side="left", padx=10)
        ctk.CTkButton(row, text="Apply to monitor", fg_color="#ff5c7a", hover_color="#ff7a93", command=self._apply_crosshair).pack(side="left", padx=10)
        ctk.CTkLabel(card, text="Sends the byte-verified E0 55 <index> frame via the same transport.", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(6, 12))
        return page

    def _page_firmware(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Firmware", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Safety: firmware flashing is intentionally not provided.", text_color="#ff5c7a", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(card, text="Reference image: F08 / 2022-11-15, 2,031,616 bytes, SHA-256 3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f", text_color="#9aa3b2", wraplength=900).pack(anchor="w", padx=14, pady=6)
        ctk.CTkLabel(card, text="Use analysis/build_variant.py --verify and build_custom.py --verify for offline checks. No commands are sent to the monitor.", text_color="#9aa3b2", wraplength=900).pack(anchor="w", padx=14, pady=6)
        ctk.CTkButton(card, text="Verify stock image hash", command=self._verify_firmware).pack(anchor="w", padx=14, pady=10)
        self.fw_text = ctk.StringVar(value="Not checked")
        ctk.CTkLabel(card, textvariable=self.fw_text, text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        return page

    def _verify_firmware(self) -> None:
        import hashlib
        from pathlib import Path
        path = "firmware/F08-20221115/FO48U_MP_F08_20221115_r9120_SIDEKICK_USE.bin"
        p = Path(path)
        if not p.exists():
            self.fw_text.set("Stock image not found")
            return
        data = p.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        expected = "3dd2e95afce675d3b299dc29bffa1bf43aaee5efdad12d88a562442804bfdf5f"
        self.fw_text.set("MATCH" if digest == expected else f"MISMATCH: {digest}")
        self.log(f"Firmware hash: {digest}")

    def _page_hardware(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Hardware", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="both", expand=True, padx=14, pady=8)
        ctk.CTkLabel(card, text="System metrics", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(card, textvariable=self.hw_text, justify="left", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        ctk.CTkButton(card, text="Refresh metrics", command=self._refresh_hw).pack(anchor="w", padx=14, pady=10)

        info = ctk.CTkFrame(page, corner_radius=14)
        info.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(info, text="Monitor identification", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        ctk.CTkLabel(info, textvariable=self.info_text, justify="left", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        ctk.CTkButton(info, text="Refresh info", command=self._refresh_info).pack(anchor="w", padx=14, pady=10)
        return page

    def _page_profiles(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Profiles", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Save/load monitor control profiles (JSON)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)
        ctk.CTkButton(row, text="Save profile", command=self._save_profile).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Load profile", command=self._load_profile).pack(side="left", padx=6)
        return page

    def _page_diagnostics(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Diagnostics", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="both", expand=True, padx=14, pady=8)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkButton(row, text="Dump DDC/CI VCP", command=self._dump_vcp).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Dump OLED selectors", command=self._dump_oled).pack(side="left", padx=6)
        self.diag_text = ctk.CTkTextbox(card, corner_radius=14)
        self.diag_text.pack(fill="both", expand=True, padx=14, pady=8)
        return page

    def _page_tests(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Display tests", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Fullscreen color patterns for visual inspection (read-only).", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(10, 6))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)
        for color in ["#ff0000", "#00ff00", "#0000ff", "#ffffff", "#000000", "#808080"]:
            ctk.CTkButton(row, text=color, fg_color=color, text_color="#000000" if color in ("#ffffff", "#00ff00") else "#ffffff",
                          width=90, command=lambda c=color: self._show_color(c)).pack(side="left", padx=4)
        ctk.CTkLabel(card, text="Press ESC to close the test window.", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        return page

    def _show_color(self, color: str) -> None:
        win = ctk.CTkToplevel(self.root)
        win.attributes("-fullscreen", True)
        win.configure(fg_color=color)
        win.bind("<Escape>", lambda e: win.destroy())

    def _page_settings(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Settings", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        card = ctk.CTkFrame(page, corner_radius=14)
        card.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(card, text="Appearance", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkOptionMenu(card, values=["dark", "light", "system"], command=ctk.set_appearance_mode).pack(anchor="w", padx=14, pady=6)
        ctk.CTkLabel(card, text="Auto-refresh", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkSwitch(card, text="Refresh every 30s", variable=self.auto_refresh, command=self._toggle_auto_refresh).pack(anchor="w", padx=14, pady=6)
        ctk.CTkLabel(card, text="Safety", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(card, text="Read-only by default. Write access requires explicit toggle and confirmation.", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        return page

    def _page_log(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        ctk.CTkLabel(page, text="Log", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=14, pady=(14, 8))
        self.log_text = ctk.CTkTextbox(page, corner_radius=14)
        self.log_text.pack(fill="both", expand=True, padx=14, pady=8)
        return page

    # --------------------------------------------------------------- connect
    def _toggle_connect(self) -> None:
        if self.connected.get():
            self._connect()
        else:
            self._disconnect()

    def _connect(self) -> None:
        try:
            try:
                self.transport = RtHidTransport()
            except OSError:
                self.transport = HelperTransport()
            self.transport.open()
            self.care = OledCare(self.transport, dry_run=False, allow_execute=self.write_enabled.get())
            self.ddc = DdcCi()
            self.log("Connected.")
            self._refresh_oled()
            self._read_vcp()
            self._refresh_info()
        except Exception as exc:
            self.connected.set(False)
            self.transport = None
            self.care = None
            self.ddc = None
            from tkinter import messagebox
            messagebox.showerror("Connection failed", str(exc))
            self.log(f"Connection failed: {exc}")

    def _disconnect(self) -> None:
        if self.transport is not None:
            self.transport.close()
        if self.ddc is not None:
            self.ddc.close()
        self.transport = None
        self.care = None
        self.ddc = None
        self.log("Disconnected.")

    def _toggle_write(self) -> None:
        if self.write_enabled.get():
            from tkinter import messagebox
            if not messagebox.askyesno("Enable write access", "Write access sends commands to the monitor. Continue?"):
                self.write_enabled.set(False)
                self.write_switch.deselect()
                self.log("Write access disabled.")
                self._update_action_state()
                self._update_status()
                return
            self.log("Write access enabled.")
        else:
            self.log("Write access disabled.")
        if self.care is not None:
            self.care.allow_execute = self.write_enabled.get()
        self._update_action_state()
        self._update_status()

    def _update_action_state(self) -> None:
        state = "normal" if self.write_enabled.get() else "disabled"
        try:
            self.apcs_button.configure(state=state)
            self.aocs_button.configure(state=state)
        except Exception:
            pass

    def _update_status(self) -> None:
        if self.write_enabled.get():
            self.status_label.configure(text="WRITE ACCESS", text_color="#ff5c7a")
        else:
            self.status_label.configure(text="read-only", text_color="#9aa3b2")

    # --------------------------------------------------------------- OLED
    def _refresh_oled(self) -> None:
        if self.care is None:
            for key in self.oled_vars:
                self.oled_vars[key].set("n/a")
            self.log("Not connected.")
            return

        def work():
            values = {
                "panel_hours": self.care.read_panel_hours(),
                "apcs_time": self.care.read_apcs_time(),
                "aocs_time": self.care.read_aocs_time(),
                "apcs_enable": self.care.read_apcs_enable(),
                "aocs_enable": self.care.read_aocs_enable(),
            }
            self.root.after(0, lambda v=values: self._apply_oled(v))

        self._start_worker(work)

    def _apply_oled(self, values) -> None:
        for key, value in values.items():
            self.oled_vars[key].set("—" if value is None else str(value))
        self.log("OLED readback refreshed.")

    def _trigger(self, kind: str) -> None:
        if self.care is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Send unverified {kind.upper()} execution frame?"):
            return

        def work():
            try:
                if kind == "apcs":
                    frame = self.care.execute_apcs(confirmed=True)
                else:
                    frame = self.care.execute_aocs(confirmed=True)
                text = " ".join(f"{b:02x}" for b in frame)
                self.root.after(0, lambda t=text, k=kind: self.log(f"{k.upper()} frame: {t}"))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.log(f"Error: {e}"))

        self._start_worker(work)

    def _refresh_all(self) -> None:
        self._refresh_oled()
        self._read_vcp()
        self._refresh_hw()
        self._refresh_info()

    # ----------------------------------------------------------- monitor VCP
    def _read_vcp(self) -> None:
        if self.ddc is None:
            self.log("Not connected.")
            return

        def work():
            for code, var in self.vcp_vars.items():
                for phys in self.ddc.physical_monitors():
                    current, maximum = self.ddc.get_vcp(phys.hPhysicalMonitor, code)
                    if current is not None:
                        self.root.after(0, lambda c=code, v=current: self.vcp_vars[c].set(v))
            for code, var in getattr(self, "all_vars", {}).items():
                for phys in self.ddc.physical_monitors():
                    current, maximum = self.ddc.get_vcp(phys.hPhysicalMonitor, code)
                    if current is not None:
                        self.root.after(0, lambda c=code, v=current: self.all_vars[c].set(v))
            self.root.after(0, lambda: self.log("VCP readback refreshed."))

        self._start_worker(work)

    def _apply_vcp(self, code: int, value: int) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Set VCP 0x{code:02X} to {value}?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, code, value) or ok
            self.root.after(0, lambda: self.log(f"VCP 0x{code:02X} set: {ok}"))

        self._start_worker(work)

    def _apply_input(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        mapping = {"HDMI 1": 0x11, "HDMI 2": 0x12, "DisplayPort": 0x0F, "USB-C": 0x13}
        value = mapping.get(self.input_var.get(), 17)
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Set input to {self.input_var.get()}?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, 0x60, value) or ok
            self.root.after(0, lambda: self.log(f"Input set: {ok}"))

        self._start_worker(work)

    def _apply_color(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        mapping = {"5000K": 1, "6500K": 2, "7500K": 3, "9300K": 5, "sRGB": 8, "Native": 11}
        value = mapping.get(self.color_var.get(), 2)
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Set color preset to {self.color_var.get()}?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, 0x14, value) or ok
            self.root.after(0, lambda: self.log(f"Color preset set: {ok}"))

        self._start_worker(work)

    def _apply_mute(self) -> None:
        if self.ddc is None:
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            self.mute_var.set(not self.mute_var.get())
            return
        value = 1 if self.mute_var.get() else 2

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, 0x8D, value) or ok
            self.root.after(0, lambda: self.log(f"Mute set: {ok}"))

        self._start_worker(work)

    def _factory_reset(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", "Restore factory defaults?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, 0x04, 1) or ok
            self.root.after(0, lambda: self.log(f"Factory reset: {ok}"))

        self._start_worker(work)

    def _read_custom_vcp(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        try:
            code = int(self.custom_code.get(), 0)
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Invalid code", "Enter a hex code like 0xE5")
            return

        def work():
            for phys in self.ddc.physical_monitors():
                current, maximum = self.ddc.get_vcp(phys.hPhysicalMonitor, code)
                if current is not None:
                    self.root.after(0, lambda c=current, m=maximum: self.custom_result.set(f"current={c} max={m}"))
                    self.root.after(0, lambda v=current: self.custom_value.set(v))
                    return
            self.root.after(0, lambda: self.custom_result.set("no response"))

        self._start_worker(work)

    def _apply_custom_vcp(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        try:
            code = int(self.custom_code.get(), 0)
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Invalid code", "Enter a hex code like 0xE5")
            return
        value = self.custom_value.get()
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Set VCP 0x{code:02X} to {value}?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, code, value) or ok
            self.root.after(0, lambda: self.log(f"Custom VCP 0x{code:02X} set: {ok}"))

        self._start_worker(work)

    def _apply_all_vcp(self, code: int, value: int) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Set VCP 0x{code:02X} to {value}?"):
            return

        def work():
            ok = False
            for phys in self.ddc.physical_monitors():
                ok = self.ddc.set_vcp(phys.hPhysicalMonitor, code, value) or ok
            self.root.after(0, lambda: self.log(f"VCP 0x{code:02X} set: {ok}"))

        self._start_worker(work)

    def _apply_crosshair(self) -> None:
        if self.care is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return
        if not self.write_enabled.get():
            from tkinter import messagebox
            messagebox.showinfo("Read-only", "Enable write access first.")
            return
        index = int(self.crosshair_index.get())
        from tkinter import messagebox
        if not messagebox.askyesno("Confirm", f"Apply hardware crosshair preset {index}?"):
            return

        def work():
            try:
                frame = self.care.set_crosshair(index, confirmed=True)
                text = " ".join(f"{b:02x}" for b in frame)
                self.root.after(0, lambda t=text: self.log(f"Crosshair frame: {t}"))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.log(f"Error: {e}"))

        self._start_worker(work)

    def _refresh_hw(self) -> None:
        def work():
            lines = []
            try:
                import subprocess
                out = subprocess.check_output(["wmic", "cpu", "get", "loadpercentage"], text=True, stderr=subprocess.DEVNULL)
                lines.append("CPU load: " + " ".join(out.split()))
            except Exception:
                lines.append("CPU load: unavailable")
            try:
                import subprocess
                out = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader"], text=True, stderr=subprocess.DEVNULL)
                lines.append("GPU: " + out.strip())
            except Exception:
                lines.append("GPU: nvidia-smi not available")
            self.root.after(0, lambda: self.hw_text.set("\n".join(lines)))

        self._start_worker(work)

    def _refresh_info(self) -> None:
        def work():
            lines = []
            try:
                import subprocess
                ps = "Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorID | ForEach-Object { $_.UserFriendlyName -join '' }"
                out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True, stderr=subprocess.DEVNULL)
                lines.append("Model: " + out.strip())
            except Exception:
                lines.append("Model: unavailable")
            try:
                import subprocess
                ps = "Get-CimInstance -Namespace root\\wmi -ClassName WmiMonitorID | ForEach-Object { $_.SerialNumberID -join '' }"
                out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True, stderr=subprocess.DEVNULL)
                lines.append("Serial: " + out.strip())
            except Exception:
                lines.append("Serial: unavailable")
            try:
                import subprocess
                ps = "Get-CimInstance Win32_VideoController | Select-Object -First 1 CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate | ForEach-Object { $_.CurrentHorizontalResolution.ToString() + 'x' + $_.CurrentVerticalResolution.ToString() + ' @' + $_.CurrentRefreshRate.ToString() + 'Hz' }"
                out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps], text=True, stderr=subprocess.DEVNULL)
                lines.append("Display mode: " + out.strip())
            except Exception:
                lines.append("Display mode: unavailable")
            self.root.after(0, lambda: self.info_text.set("\n".join(lines)))

        self._start_worker(work)

    def _save_profile(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = {str(code): var.get() for code, var in self.vcp_vars.items()}
        data.update({str(code): var.get() for code, var in self.all_vars.items()})
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.log(f"Profile saved: {path}")

    def _load_profile(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for code, var in {**self.vcp_vars, **self.all_vars}.items():
            if str(code) in data:
                var.set(int(data[str(code)]))
        self.log(f"Profile loaded: {path}")

    def _dump_vcp(self) -> None:
        if self.ddc is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return

        def work():
            lines = []
            for code in range(0x00, 0x100):
                for phys in self.ddc.physical_monitors():
                    current, maximum = self.ddc.get_vcp(phys.hPhysicalMonitor, code)
                    if current is not None:
                        lines.append(f"VCP 0x{code:02X} {VCP_NAMES.get(code, '')}: current={current} max={maximum}")
            if not lines:
                lines.append("No responding VCP codes found.")
            text = "\n".join(lines)
            self.root.after(0, lambda t=text: self._set_diag(t))

        self._start_worker(work)

    def _dump_oled(self) -> None:
        if self.care is None:
            from tkinter import messagebox
            messagebox.showinfo("Not connected", "Connect to the monitor first.")
            return

        def work():
            mapping = {
                "panel_hours (0x7F)": self.care.read_panel_hours(),
                "apcs_enable (0x80)": self.care.read_apcs_enable(),
                "apcs_time (0x81)": self.care.read_apcs_time(),
                "aocs_enable (0x82)": self.care.read_aocs_enable(),
                "aocs_time (0x83)": self.care.read_aocs_time(),
            }
            lines = [f"{name}: {value}" for name, value in mapping.items()]
            text = "\n".join(lines)
            self.root.after(0, lambda t=text: self._set_diag(t))

        self._start_worker(work)

    def _set_diag(self, text: str) -> None:
        self.diag_text.delete("1.0", "end")
        self.diag_text.insert("end", text + "\n")
        self.log("Diagnostics readout completed.")

    def _toggle_auto_refresh(self) -> None:
        if self.auto_refresh.get():
            self._schedule_auto_refresh()
            self.log("Auto-refresh enabled.")
        else:
            self.log("Auto-refresh disabled.")

    def _schedule_auto_refresh(self) -> None:
        if not self.auto_refresh.get():
            return
        if self.connected.get():
            self._refresh_all()
        self.root.after(30000, self._schedule_auto_refresh)

    # --------------------------------------------------------------- worker
    def _start_worker(self, work: Callable[[], None]) -> None:
        if self._worker is not None and self._worker.is_alive():
            self.log("Busy; wait for the current operation.")
            return

        def runner():
            try:
                work()
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.log(f"Error: {e}"))

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")


def main() -> None:
    root = ctk.CTk()
    Fo48uGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()