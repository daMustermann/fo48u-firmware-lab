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

ACCENT = "#7c5cff"


class Fo48uGui:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title("FO48U Controller")
        self.root.geometry("1240x820")
        self.root.minsize(1040, 700)

        self.connected = ctk.BooleanVar(value=False)
        self.write_enabled = ctk.BooleanVar(value=False)
        self.transport = None
        self.care = None
        self.ddc = None
        self._worker = None

        self.oled_vars = {k: ctk.StringVar(value="—") for k in
                          ("panel_hours", "apcs_time", "aocs_time", "apcs_enable", "aocs_enable")}

        self.vcp_vars = {}
        self.crosshair_index = ctk.IntVar(value=1)
        self.hw_text = ctk.StringVar(value="Not refreshed")

        self._build_layout()
        self.log("Ready. Read-only mode is active by default.")

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        top = ctk.CTkFrame(self.root, corner_radius=0)
        top.pack(fill="x", padx=18, pady=(14, 6))

        ctk.CTkLabel(top, text="FO48U Controller", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        self.status_label = ctk.CTkLabel(top, text="read-only", text_color="#9aa3b2")
        self.status_label.pack(side="left", padx=14)

        self.connect_switch = ctk.CTkSwitch(top, text="Connect", variable=self.connected, command=self._toggle_connect)
        self.connect_switch.pack(side="right", padx=8)
        self.write_switch = ctk.CTkSwitch(top, text="Write access", variable=self.write_enabled, command=self._toggle_write)
        self.write_switch.pack(side="right", padx=8)

        self.tabs = ctk.CTkTabview(self.root, width=1180, height=700)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=8)

        self._build_oled_tab()
        self._build_monitor_tab()
        self._build_crosshair_tab()
        self._build_hardware_tab()
        self._build_profiles_tab()
        self._build_log_tab()

        self._update_status()

    # --------------------------------------------------------------- OLED tab
    def _build_oled_tab(self) -> None:
        tab = self.tabs.add("OLED care")
        grid = ctk.CTkFrame(tab, fg_color="transparent")
        grid.pack(fill="x", pady=8)

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
            ctk.CTkLabel(card, text=label, text_color="#9aa3b2", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(card, textvariable=self.oled_vars[key], font=ctk.CTkFont(size=24, weight="bold"),
                         text_color="#00d4ff").pack(anchor="w", padx=14, pady=(0, 12))

        for c in range(3):
            grid.columnconfigure(c, weight=1)

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=12)
        ctk.CTkButton(row, text="Refresh", command=self._refresh_oled).pack(side="left", padx=6)
        self.apcs_button = ctk.CTkButton(row, text="Trigger APCS", fg_color="#ff5c7a", hover_color="#ff7a93",
                                         command=lambda: self._trigger("apcs"))
        self.apcs_button.pack(side="left", padx=6)
        self.aocs_button = ctk.CTkButton(row, text="Trigger AOCS", fg_color="#ff5c7a", hover_color="#ff7a93",
                                         command=lambda: self._trigger("aocs"))
        self.aocs_button.pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Unverified manual triggers", text_color="#9aa3b2").pack(side="left", padx=10)
        self._update_action_state()

    # ----------------------------------------------------------- monitor tab
    def _build_monitor_tab(self) -> None:
        tab = self.tabs.add("Monitor controls")
        self.vcp_items = [
            ("Brightness", 0x10),
            ("Contrast", 0x12),
            ("Red gain", 0x16),
            ("Green gain", 0x18),
            ("Blue gain", 0x1A),
            ("Volume", 0x62),
            ("Sharpness", 0x87),
        ]
        for name, code in self.vcp_items:
            card = ctk.CTkFrame(tab, corner_radius=14)
            card.pack(fill="x", pady=6, padx=4)
            ctk.CTkLabel(card, text=name, font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=14, pady=(10, 2))
            var = ctk.IntVar(value=50)
            self.vcp_vars[code] = var
            ctk.CTkSlider(card, from_=0, to=100, variable=var).pack(fill="x", padx=14, pady=4)
            ctk.CTkButton(card, text="Apply", width=90, command=lambda c=code, v=var: self._apply_vcp(c, v.get())).pack(anchor="e", padx=14, pady=(2, 10))

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=10)
        ctk.CTkButton(row, text="Read all VCP", command=self._read_vcp).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="DDC/CI standard controls", text_color="#9aa3b2").pack(side="left", padx=10)

    # ---------------------------------------------------------- crosshair tab
    def _build_crosshair_tab(self) -> None:
        tab = self.tabs.add("Crosshair")
        card = ctk.CTkFrame(tab, corner_radius=14)
        card.pack(fill="x", pady=8, padx=4)
        ctk.CTkLabel(card, text="Hardware crosshair (monitor OSD)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row, text="Preset index").pack(side="left")
        ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, 8)], variable=self.crosshair_index).pack(side="left", padx=10)
        ctk.CTkButton(row, text="Apply to monitor", fg_color="#ff5c7a", hover_color="#ff7a93",
                      command=self._apply_crosshair).pack(side="left", padx=10)
        ctk.CTkLabel(card, text="Sends the byte-verified E0 55 <index> frame via the same transport.",
                     text_color="#9aa3b2").pack(anchor="w", padx=14, pady=(6, 12))

    # ----------------------------------------------------------- hardware tab
    def _build_hardware_tab(self) -> None:
        tab = self.tabs.add("Hardware")
        card = ctk.CTkFrame(tab, corner_radius=14)
        card.pack(fill="both", expand=True, pady=8, padx=4)
        ctk.CTkLabel(card, text="System metrics", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        ctk.CTkLabel(card, textvariable=self.hw_text, justify="left", text_color="#9aa3b2").pack(anchor="w", padx=14, pady=6)
        ctk.CTkButton(card, text="Refresh metrics", command=self._refresh_hw).pack(anchor="w", padx=14, pady=10)

    # ----------------------------------------------------------- profiles tab
    def _build_profiles_tab(self) -> None:
        tab = self.tabs.add("Profiles")
        card = ctk.CTkFrame(tab, corner_radius=14)
        card.pack(fill="x", pady=8, padx=4)
        ctk.CTkLabel(card, text="Save/load monitor control profiles (JSON)", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=14, pady=(12, 6))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=10)
        ctk.CTkButton(row, text="Save profile", command=self._save_profile).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Load profile", command=self._load_profile).pack(side="left", padx=6)

    # --------------------------------------------------------------- log tab
    def _build_log_tab(self) -> None:
        tab = self.tabs.add("Log")
        self.log_text = ctk.CTkTextbox(tab, corner_radius=14)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=8)

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
        self.apcs_button.configure(state=state)
        self.aocs_button.configure(state=state)

    def _update_status(self) -> None:
        if self.write_enabled.get():
            self.status_label.configure(text="WRITE ACCESS ENABLED", text_color="#ff5c7a")
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

    # ---------------------------------------------------------- crosshair
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

    # ----------------------------------------------------------- hardware
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
                out = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader"],
                                             text=True, stderr=subprocess.DEVNULL)
                lines.append("GPU: " + out.strip())
            except Exception:
                lines.append("GPU: nvidia-smi not available")
            self.root.after(0, lambda: self.hw_text.set("\n".join(lines)))

        self._start_worker(work)

    # ----------------------------------------------------------- profiles
    def _save_profile(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = {str(code): var.get() for code, var in self.vcp_vars.items()}
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.log(f"Profile saved: {path}")

    def _load_profile(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for code, var in self.vcp_vars.items():
            if str(code) in data:
                var.set(int(data[str(code)]))
        self.log(f"Profile loaded: {path}")

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