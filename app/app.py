#!/usr/bin/env python3
"""
RemoteFlash — Pure Python SSH/SFTP firmware flashing tool.

Cross-platform, no external C/Perl/OpenSSL dependencies (uses paramiko).
The application is split into focused modules:

    constants.py       app identity + auto-update source
    theme.py           colour palette, fonts, ttk styles
    models.py          enums + data classes
    avr_signatures.py  AVR device-signature database
    ssh_client.py      pure-Python SSH/SFTP client
    config_manager.py  JSON config persistence
    widgets.py         custom Tk widgets
    app.py             main window + updater (this file)

Version: 1.2.0 · © IDEATON
"""

import os
import re
import sys
import time
import threading
import webbrowser
import urllib.request
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

import theme
from theme import *  # colours + STEPS (fonts are read via theme.FONT_*)
from constants import (
    APP_NAME, APP_VERSION, APP_TAGLINE, APP_PUBLISHER,
    APP_WEBSITE, APP_CONTACT, GITHUB_REPO, GITHUB_URL, GITHUB_API_LATEST,
)
from models import (
    LogLevel, LogEntry, AuthMethod, ConnectionProfile, TaskState,
)
from avr_signatures import AVR_SIGNATURES
from ssh_client import SSHClient
from config_manager import ConfigManager
from widgets import CollapsibleFrame, StepItem, SelectableList


class RemoteFlashApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1280x840")
        self.minsize(1020, 680)

        # Start maximized (Windows / macOS use 'zoomed', Linux uses '-zoomed')
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass

        self._set_window_icon()

        # Configuration
        self.config_data = ConfigManager.load()
        self.profiles: List[ConnectionProfile] = [
            ConnectionProfile(**p) for p in self.config_data.get("profiles", [])
        ]
        self.active_profile_idx = self.config_data.get("active_profile_idx", 0)

        # State
        self.is_connected = False
        self.file_path: Optional[Path] = None
        self.log_entries: deque = deque(maxlen=1000)
        self.task_state = TaskState.Idle
        self.ping_ms: Optional[float] = None
        self.ssh_client = SSHClient(timeout=self.config_data.get("ssh_timeout", 10))
        self.available_ports: List[dict] = []
        self.available_programmers: List[dict] = []
        self.remote_label_file = self.config_data.get(
            "remote_label_file", "/home/ideavr/ports-label.json")

        # Chip detection state
        self.detected_part: Optional[str] = None    # avrdude id, e.g. m328p
        self.detected_name: Optional[str] = None    # e.g. ATmega328P
        self.detected_sig: Optional[str] = None

        # Updater state
        self.latest_version: Optional[str] = None
        self.update_url: Optional[str] = None
        self.update_asset_name: Optional[str] = None
        self.release_page: Optional[str] = None

        # UI Variables
        self.custom_commands = self.config_data.get("custom_commands", [])
        self.selected_command = tk.StringVar(
            value=self.custom_commands[0] if self.custom_commands else "")
        self.custom_command = tk.StringVar()
        self.log_filter = tk.StringVar()
        self.remote_dir = tk.StringVar(value=self.config_data.get("remote_dir", "/tmp"))
        self.sudo_mode = tk.BooleanVar(value=False)
        self.delete_after_flash = tk.BooleanVar(
            value=self.config_data.get("delete_after_flash", False))
        self.selected_port = tk.StringVar(value="")
        self.selected_programmer = tk.StringVar(value="")
        self.flashing_mode = tk.StringVar(value="serial")   # "serial" | "usbasp"
        self.use_detected = tk.BooleanVar(value=True)

        self.current_step = 0
        self._busy_buttons: list = []

        self._setup_ui()
        self._wire_traces()
        self._add_log(LogLevel.Info,
                      f"{APP_NAME} v{APP_VERSION} — Pure Python. No OpenSSL required.")
        self._load_initial_profile()
        self._refresh_dynamic()

        # Check GitHub for a newer release shortly after startup
        self.after(1500, self._check_updates_async)

    # ─── Window icon (unchanged) ────────────────────────────────
    def _set_window_icon(self):
        """Set the window icon: bundled icon.ico if available (frozen exe or
        next to the script), otherwise fall back to the drawn pixel-art icon."""
        try:
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            for candidate in (base / "icon.ico",
                              base.parent / "build" / "icon.ico"):
                if candidate.exists():
                    self.iconbitmap(default=str(candidate))
                    return
        except Exception:
            pass
        try:
            icon_size = 64
            img = tk.PhotoImage(width=icon_size, height=icon_size)

            for y in range(20, 44):
                for x in range(34, 62):
                    if y == 20 or y == 43 or x == 34 or x == 61:
                        img.put("#2ecc71", (x, y))
                    else:
                        img.put("#1a6e3c", (x, y))
            for y in range(26, 38):
                for x in range(38, 56):
                    if y == 26 or y == 37 or x == 38 or x == 55:
                        img.put("#555555", (x, y))
                    else:
                        img.put("#111111", (x, y))
            for pin_x in [40, 44, 48, 52]:
                for y in range(44, 50):
                    img.put("#aaaaaa", (pin_x, y))
                    img.put("#aaaaaa", (pin_x + 1, y))
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if dx * dx + dy * dy <= 4:
                        img.put("#27ae60", (58 + dx, 23 + dy))
            cx, cy = 14, 12
            for dy in range(-6, 7):
                for dx in range(-6, 7):
                    if dx * dx + dy * dy <= 36:
                        img.put("#4285F4", (cx + dx, cy + dy))
            for y in range(20, 36):
                for x in range(11, 18):
                    img.put("#4285F4", (x, y))
            for x in range(18, 34):
                img.put("#4285F4", (x, 27))
                img.put("#4285F4", (x, 28))
            for step in range(8):
                img.put("#4285F4", (10 - step, 27 + step // 2))
                img.put("#4285F4", (10 - step, 28 + step // 2))
            for step in range(10):
                img.put("#4285F4", (13 - step // 3, 36 + step))
                img.put("#4285F4", (16 + step // 3, 36 + step))
            for x in range(28, 35):
                img.put("#f39c12", (x, 27))
                img.put("#f39c12", (x, 28))

            self.iconphoto(True, img)
            self._icon_img = img
        except Exception:
            pass

    # ─── Layout skeleton ────────────────────────────────────────
    def _setup_ui(self):
        theme.apply_theme(self)
        self._build_menubar()

        self.rowconfigure(0, weight=0)   # header
        self.rowconfigure(1, weight=0)   # update banner (hidden by default)
        self.rowconfigure(2, weight=1)   # main body
        self.rowconfigure(3, weight=0)   # status bar
        self.columnconfigure(0, weight=1)

        header = ttk.Frame(self, style="Root.TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._setup_header(header)

        self._build_update_banner()

        body = ttk.Frame(self, style="Root.TFrame")
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=0, minsize=230)   # sidebar
        body.columnconfigure(1, weight=11, minsize=430)  # active panel
        body.columnconfigure(2, weight=9)                # console

        self._build_sidebar(body)

        self.panel_container = tk.Frame(body, bg=BG_DARK)
        self.panel_container.grid(row=0, column=1, sticky="nsew", padx=(12, 12))
        self.panel_container.rowconfigure(0, weight=1)
        self.panel_container.columnconfigure(0, weight=1)

        self.panels = []
        for builder in (self._panel_connection, self._panel_firmware,
                        self._panel_target, self._panel_flash):
            panel = tk.Frame(self.panel_container, bg=BG_DARK)
            panel.grid(row=0, column=0, sticky="nsew")
            builder(panel)
            self.panels.append(panel)

        console = ttk.Frame(body, style="Root.TFrame")
        console.grid(row=0, column=2, sticky="nsew")
        console.rowconfigure(0, weight=1)
        console.columnconfigure(0, weight=1)
        self._setup_console_section(console)

        status = ttk.Frame(self, style="Root.TFrame")
        status.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 10))
        self._setup_status_bar(status)

        self._go_step(0)

    def _setup_header(self, parent):
        logo = ttk.Label(parent, text="⚡", style="Title.TLabel", foreground=BLUE_ACCENT)
        logo.pack(side="left", padx=(0, 10))

        text_box = ttk.Frame(parent, style="Root.TFrame")
        text_box.pack(side="left")
        ttk.Label(text_box, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(text_box, text=f"{APP_TAGLINE} · Pure Python · no OpenSSL",
                  style="Subtitle.TLabel").pack(anchor="w")

        # Connection pill (right side of header)
        self.conn_pill = tk.Label(parent, text="● Disconnected", font=theme.FONT_BOLD,
                                  bg="#FEE2E2", fg=RED_ERR, padx=12, pady=5)
        self.conn_pill.pack(side="right")

        # About button
        about = tk.Label(parent, text="ℹ  About", font=theme.FONT_BASE,
                         bg=BG_DARK, fg=TEXT_DIM, cursor="hand2", padx=10)
        about.pack(side="right", padx=(0, 8))
        about.bind("<Button-1>", lambda _e: self._show_about())
        about.bind("<Enter>", lambda _e: about.config(fg=BLUE_ACCENT))
        about.bind("<Leave>", lambda _e: about.config(fg=TEXT_DIM))

    # ─── Sidebar ────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        side = tk.Frame(parent, bg=BG_DARK)
        side.grid(row=0, column=0, sticky="nsew")

        self.step_items: List[StepItem] = []
        for i, (icon, title, _desc) in enumerate(STEPS):
            item = StepItem(side, i, icon, title, self._go_step)
            item.pack(fill="x", pady=2)
            self.step_items.append(item)

        tk.Frame(side, bg=BG_DARK).pack(fill="both", expand=True)  # spacer

        self.progress = ttk.Progressbar(
            side, mode="indeterminate", style="Accent.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(8, 4))
        self.progress.pack_forget()

    def _go_step(self, index: int):
        self.current_step = max(0, min(index, len(self.panels) - 1))
        self.panels[self.current_step].tkraise()
        self._refresh_dynamic()

    # ─── Small UI helpers ───────────────────────────────────────
    def _panel_header(self, parent, title, desc):
        box = tk.Frame(parent, bg=BG_DARK)
        box.pack(fill="x", pady=(0, 10))
        ttk.Label(box, text=title, style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(box, text=desc, style="PanelDesc.TLabel").pack(anchor="w")

    def _card(self, parent, title=None):
        outer = tk.Frame(parent, bg=BG_CARD,
                         highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", pady=(0, 10))
        inner = ttk.Frame(outer, style="Card.TFrame", padding=12)
        inner.pack(fill="both", expand=True)
        if title:
            ttk.Label(inner, text=title, style="Section.TLabel").pack(
                anchor="w", pady=(0, 8))
        return inner

    def _nav(self, parent, back=False, next_=False):
        bar = tk.Frame(parent, bg=BG_DARK)
        bar.pack(fill="x", side="bottom", pady=(4, 0))
        if back:
            ttk.Button(bar, text="←  Back",
                       command=lambda: self._go_step(self.current_step - 1),
                       width=10).pack(side="left")
        if next_:
            btn = self._make_action_button(
                bar, "Next  →", lambda: self._go_step(self.current_step + 1),
                BLUE_ACCENT, BLUE_HOVER, BLUE_PRESS)
            btn.pack(side="right", ipadx=18, ipady=6)

    def _make_action_button(self, parent, text, command, base, hover, press):
        btn = tk.Button(
            parent, text=text, command=command,
            font=theme.FONT_BTN, bg=base, fg="white",
            activebackground=press, activeforeground="white",
            relief="flat", bd=0, cursor="hand2",
            highlightthickness=0,
            disabledforeground="#C9D2E3",
        )
        btn._base, btn._hover = base, hover

        def on_enter(_e):
            if str(btn["state"]) != "disabled":
                btn.config(bg=btn._hover)

        def on_leave(_e):
            if str(btn["state"]) != "disabled":
                btn.config(bg=btn._base)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # ─── Panel 1 · Connection ───────────────────────────────────
    def _panel_connection(self, parent):
        self._panel_header(parent, "🌐 Connection",
                           "Pick a profile, check the host, connect.")

        card = self._card(parent, "Profile")
        row = ttk.Frame(card)
        row.pack(fill="x")
        self.profile_combo = ttk.Combobox(
            row, values=[p.name for p in self.profiles],
            state="readonly", width=22)
        if self.profiles:
            self.profile_combo.current(
                min(self.active_profile_idx, len(self.profiles) - 1))
        self.profile_combo.pack(fill="x", expand=True)
        self.profile_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_profile_selected(self.profile_combo.current()))
        btns = ttk.Frame(card)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="➕ New", command=self._new_profile, width=7).pack(side="left", padx=(0, 3))
        ttk.Button(btns, text="💾 Save", command=self._save_current_profile, width=7).pack(side="left", padx=3)
        ttk.Button(btns, text="✏️ Rename", command=self._rename_profile, width=9).pack(side="left", padx=3)
        ttk.Button(btns, text="🗑 Delete", command=self._delete_profile, width=8).pack(side="left", padx=3)

        card = self._card(parent, "Server")
        grid = ttk.Frame(card)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="IP / Hostname").grid(row=0, column=0, sticky="w", pady=4)
        self.ip_var = tk.StringVar(value=self._active_profile().ip)
        ttk.Entry(grid, textvariable=self.ip_var).grid(row=0, column=1, sticky="ew", pady=4, padx=(10, 0))

        ttk.Label(grid, text="Username").grid(row=1, column=0, sticky="w", pady=4)
        self.username_var = tk.StringVar(value=self._active_profile().username)
        ttk.Entry(grid, textvariable=self.username_var).grid(row=1, column=1, sticky="ew", pady=4, padx=(10, 0))

        ttk.Label(grid, text="Port").grid(row=2, column=0, sticky="w", pady=4)
        self.port_var = tk.IntVar(value=self._active_profile().port)
        ttk.Spinbox(grid, from_=1, to=65535, textvariable=self.port_var).grid(
            row=2, column=1, sticky="ew", pady=4, padx=(10, 0))

        ttk.Label(grid, text="Auth method").grid(row=3, column=0, sticky="w", pady=4)
        auth_frame = ttk.Frame(grid)
        auth_frame.grid(row=3, column=1, sticky="w", pady=4, padx=(10, 0))
        self.auth_var = tk.StringVar(value=self._active_profile().auth_method)
        for method in [AuthMethod.RsaKey.value, AuthMethod.Password.value]:
            ttk.Radiobutton(auth_frame, text=method.title(),
                            variable=self.auth_var, value=method).pack(side="left", padx=(0, 10))

        ttk.Label(grid, text="SSH key").grid(row=4, column=0, sticky="w", pady=4)
        key_frame = ttk.Frame(grid)
        key_frame.grid(row=4, column=1, sticky="ew", pady=4, padx=(10, 0))
        key_frame.columnconfigure(0, weight=1)
        self.key_path_var = tk.StringVar(value=self._active_profile().rsa_key_path or "")
        ttk.Entry(key_frame, textvariable=self.key_path_var).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(key_frame, text="🔑 Browse", command=self._select_ssh_key, width=10).grid(row=0, column=1)

        ttk.Label(grid, text="Password").grid(row=5, column=0, sticky="w", pady=4)
        pw_frame = ttk.Frame(grid)
        pw_frame.grid(row=5, column=1, sticky="ew", pady=4, padx=(10, 0))
        pw_frame.columnconfigure(0, weight=1)
        self.password_var = tk.StringVar(value=self._active_profile().password)
        self.password_entry = ttk.Entry(pw_frame, textvariable=self.password_var, show="*")
        self.password_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.show_password = tk.BooleanVar(value=False)

        def toggle_password():
            self.password_entry.config(show="" if self.show_password.get() else "*")

        ttk.Checkbutton(pw_frame, text="Show", variable=self.show_password,
                        command=toggle_password).grid(row=0, column=1)

        # Action row
        actions = tk.Frame(parent, bg=BG_DARK)
        actions.pack(fill="x", pady=(2, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=2)

        self.btn_ping = self._make_action_button(
            actions, "📡  Ping", self._ping_host, BLUE_ACCENT, BLUE_HOVER, BLUE_PRESS)
        self.btn_ping.grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=13)

        self.connect_button = self._make_action_button(
            actions, "🔗  Connect", self._toggle_connection,
            GREEN_OK, GREEN_HOVER, GREEN_PRESS)
        self.connect_button.grid(row=0, column=1, sticky="ew", ipady=13)

        self._busy_buttons += [self.btn_ping, self.connect_button]
        self._nav(parent, back=False, next_=True)

    # ─── Panel 2 · Firmware ─────────────────────────────────────
    def _panel_firmware(self, parent):
        self._panel_header(parent, "📁 Firmware",
                           "Choose the file to upload and where it lands.")

        card = self._card(parent, "Firmware file")
        self.btn_pick_file = self._make_action_button(
            card, "📂  Select firmware file…", self._select_file,
            BLUE_ACCENT, BLUE_HOVER, BLUE_PRESS)
        self.btn_pick_file.pack(fill="x", ipady=10)
        self.file_label = ttk.Label(card, text="No file selected", style="CardDim.TLabel")
        self.file_label.pack(anchor="w", pady=(8, 0))

        card = self._card(parent, "Remote directory")
        ttk.Entry(card, textvariable=self.remote_dir).pack(fill="x")
        ttk.Label(card, text="The file is uploaded there over SFTP before flashing.",
                  style="CardDim.TLabel").pack(anchor="w", pady=(6, 0))

        # Restore last file
        last_file = self.config_data.get("last_file_path")
        if last_file and Path(last_file).exists():
            self.file_path = Path(last_file)
            size = self.file_path.stat().st_size / 1024
            self.file_label.config(
                text=f"{self.file_path.name}  ({size:.1f} KB)", foreground=GREEN_OK)

        self._nav(parent, back=True, next_=True)

    # ─── Panel 3 · Target ───────────────────────────────────────
    def _panel_target(self, parent):
        self._panel_header(parent, "🎯 Target",
                           "How the chip is reached on the remote device.")

        card = self._card(parent, "Flashing mode")
        mode_row = ttk.Frame(card)
        mode_row.pack(anchor="w")
        ttk.Radiobutton(mode_row, text="Serial port (TTY)",
                        variable=self.flashing_mode, value="serial").pack(side="left", padx=(0, 14))
        ttk.Radiobutton(mode_row, text="USBasp programmer",
                        variable=self.flashing_mode, value="usbasp").pack(side="left")

        card = self._card(parent, "Serial ports")
        self.port_list = SelectableList(
            card, on_select=self._on_port_pick,
            empty_text="No ports — connect first, then Rescan.")
        self.port_list.pack(fill="x")
        row = ttk.Frame(card)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="🔄 Rescan", command=self._refresh_ports, width=10).pack(side="left")
        ttk.Button(row, text="✏️ Rename",
                   command=lambda: self._edit_device_label(self.port_list, "port"),
                   width=10).pack(side="left", padx=(6, 0))

        card = self._card(parent, "USBasp programmers")
        self.programmer_list = SelectableList(
            card, on_select=self._on_programmer_pick,
            empty_text="No USBasp found — connect first, then Rescan.")
        self.programmer_list.pack(fill="x")
        row = ttk.Frame(card)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="🔄 Rescan", command=self._refresh_programmers, width=10).pack(side="left")
        ttk.Button(row, text="✏️ Rename",
                   command=lambda: self._edit_device_label(self.programmer_list, "programmer"),
                   width=10).pack(side="left", padx=(6, 0))

        card = self._card(parent, "Chip detection")
        self.btn_detect = self._make_action_button(
            card, "🔍  Detect AVR chip", self._detect_avr,
            BLUE_ACCENT, BLUE_HOVER, BLUE_PRESS)
        self.btn_detect.pack(fill="x", ipady=9)
        self._busy_buttons.append(self.btn_detect)

        chip_row = ttk.Frame(card)
        chip_row.pack(fill="x", pady=(8, 0))
        self.chip_label = tk.Label(chip_row, text="No chip detected yet",
                                   bg=BG_CARD2, fg=TEXT_DIM, font=theme.FONT_BOLD,
                                   padx=10, pady=5)
        self.chip_label.pack(side="left")
        ttk.Checkbutton(card, text="Adapt avrdude “-p” automatically to the detected chip",
                        variable=self.use_detected).pack(anchor="w", pady=(8, 0))

        self._nav(parent, back=True, next_=True)

    # ─── Panel 4 · Flash ────────────────────────────────────────
    def _panel_flash(self, parent):
        self._panel_header(parent, "⚡ Flash",
                           "Review the command, then send it.")

        card = self._card(parent, "Command")
        row = ttk.Frame(card)
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        self.command_combo = ttk.Combobox(
            row, textvariable=self.selected_command,
            values=self.custom_commands, state="readonly")
        self.command_combo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(row, text="➕", command=self._add_command, width=3).grid(row=0, column=1, padx=1)
        ttk.Button(row, text="🗑", command=self._remove_command, width=3).grid(row=0, column=2, padx=1)

        ttk.Label(card, text="Custom (overrides preset):", style="CardDim.TLabel").pack(
            anchor="w", pady=(8, 2))
        ttk.Entry(card, textvariable=self.custom_command).pack(fill="x")

        opts = ttk.Frame(card)
        opts.pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(opts, text="sudo", variable=self.sudo_mode).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opts, text="Delete file after flash",
                        variable=self.delete_after_flash).pack(side="left")

        card = self._card(parent, "What will run")
        self.preview_label = tk.Label(
            card, text="", bg=BG_CARD2, fg="#1D4ED8", font=(theme.FONT_MONO, 9),
            anchor="w", justify="left", wraplength=420, padx=10, pady=8)
        self.preview_label.pack(fill="x")

        actions = tk.Frame(parent, bg=BG_DARK)
        actions.pack(fill="x", pady=(2, 0))
        actions.columnconfigure(0, weight=1)

        self.btn_flash = self._make_action_button(
            actions, "⚡  Upload & Flash", self._run_full_process,
            GREEN_OK, GREEN_HOVER, GREEN_PRESS)
        self.btn_flash.grid(row=0, column=0, sticky="ew", ipady=14)

        self.btn_read = self._make_action_button(
            actions, "📥  Read flash from controller (backup)", self._read_flash,
            "#FF8C00", "#E67E00", "#CC7000")
        self.btn_read.grid(row=1, column=0, sticky="ew", ipady=9, pady=(6, 0))

        self._busy_buttons += [self.btn_flash, self.btn_read]
        self._nav(parent, back=True, next_=False)

    # ─── Console & status bar ───────────────────────────────────
    def _setup_console_section(self, parent):
        frame = ttk.LabelFrame(parent, text=" Console ", padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        control_frame = ttk.Frame(frame)
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(control_frame, text="🔎").pack(side="left", padx=(0, 4))
        filter_entry = ttk.Entry(control_frame, textvariable=self.log_filter, width=22)
        filter_entry.pack(side="left", padx=(0, 8))
        self.log_filter.trace_add("write", lambda *_: self._render_logs())

        ttk.Button(control_frame, text="🗑  Clear", command=self._clear_logs).pack(side="right", padx=(6, 0))
        ttk.Button(control_frame, text="📋  Copy", command=self._copy_logs).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            frame, state="disabled", wrap="word",
            bg=BG_CARD2, fg=TEXT, insertbackground=TEXT,
            selectbackground=BLUE_ACCENT, selectforeground="white",
            font=(theme.FONT_MONO, 10), relief="flat", borderwidth=0,
            padx=10, pady=8,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")
        try:
            self.log_text.vbar.configure(
                background=BG_CARD2, troughcolor=BG_DARK,
                activebackground=BG_HOVER, borderwidth=0,
                highlightthickness=0, width=12,
            )
        except Exception:
            pass

        self.log_text.tag_config("INFO", foreground="#374151")
        self.log_text.tag_config("SUCCESS", foreground=GREEN_OK)
        self.log_text.tag_config("ERROR", foreground=RED_ERR)
        self.log_text.tag_config("WARNING", foreground=ORANGE_WARN)
        self.log_text.tag_config("DEBUG", foreground=TEXT_DIM)
        self.log_text.tag_config("COMMAND", foreground="#1D4ED8")

    def _setup_status_bar(self, parent):
        ttk.Frame(parent, style="Rule.TFrame", height=1).pack(fill="x", pady=(0, 6))
        bar = ttk.Frame(parent, style="Root.TFrame")
        bar.pack(fill="x")
        self.status_label = ttk.Label(bar, text="● Disconnected",
                                      style="Status.TLabel", foreground=RED_ERR)
        self.status_label.pack(side="left", padx=(2, 16))
        self.profile_label = ttk.Label(bar, text="", style="Dim.TLabel")
        self.profile_label.pack(side="left", padx=8)
        ttk.Label(bar, text=f"v{APP_VERSION}", style="Dim.TLabel").pack(
            side="right", padx=(8, 2))
        self.ping_label = ttk.Label(bar, text="", style="Dim.TLabel")
        self.ping_label.pack(side="right", padx=8)

    # ─── Menu bar ────────────────────────────────
    def _build_menubar(self):
        """Top menu bar: File → Check for Updates / Exit."""
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Check for Updates…",
            command=lambda: self._check_updates_async(manual=True))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    # ─── About dialog ───────────────────────────────────────────
    def _show_about(self):
        dialog = tk.Toplevel(self)
        dialog.title(f"About {APP_NAME}")
        dialog.geometry("400x330")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG_CARD)

        tk.Label(dialog, text="⚡", font=(theme.FONT_FAMILY, 28), bg=BG_CARD,
                 fg=BLUE_ACCENT).pack(pady=(18, 0))
        tk.Label(dialog, text=APP_NAME, font=(theme.FONT_FAMILY, 16, "bold"),
                 bg=BG_CARD, fg=TEXT_HEADING).pack()
        tk.Label(dialog, text=f"Version {APP_VERSION}", font=theme.FONT_BASE,
                 bg=BG_CARD, fg=TEXT_DIM).pack()
        tk.Label(dialog, text=APP_TAGLINE, font=theme.FONT_BASE,
                 bg=BG_CARD, fg=TEXT).pack(pady=(2, 12))

        tk.Frame(dialog, bg=BORDER, height=1).pack(fill="x", padx=24)

        info = tk.Frame(dialog, bg=BG_CARD)
        info.pack(pady=12)

        def _row(label, value, url=None):
            r = tk.Frame(info, bg=BG_CARD)
            r.pack(anchor="w", pady=2)
            tk.Label(r, text=label, font=theme.FONT_BOLD, bg=BG_CARD,
                     fg=TEXT, width=9, anchor="w").pack(side="left")
            lbl = tk.Label(r, text=value, font=theme.FONT_BASE, bg=BG_CARD,
                           fg=BLUE_ACCENT if url else TEXT,
                           cursor="hand2" if url else "arrow")
            lbl.pack(side="left")
            if url:
                lbl.bind("<Button-1>", lambda _e: webbrowser.open(url))

        _row("Company", APP_PUBLISHER)
        _row("Website", APP_WEBSITE.replace("https://", ""), APP_WEBSITE)
        _row("Contact", APP_CONTACT, f"mailto:{APP_CONTACT}")
        _row("GitHub", GITHUB_REPO, GITHUB_URL)

        tk.Label(dialog, text=f"© 2026 {APP_PUBLISHER} — All rights reserved",
                 font=(theme.FONT_FAMILY, 8), bg=BG_CARD, fg=TEXT_DIM).pack(pady=(4, 0))

        ttk.Button(dialog, text="Close", command=dialog.destroy,
                   width=10).pack(pady=10)
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    # ─── Update banner & auto-updater ───────────────────────────
    def _build_update_banner(self):
        """Top banner shown when a newer GitHub release exists (hidden by default)."""
        self.update_banner = tk.Frame(self, bg=SELECT_BG,
                                      highlightbackground=BLUE_ACCENT,
                                      highlightthickness=1)
        inner = tk.Frame(self.update_banner, bg=SELECT_BG)
        inner.pack(fill="x", padx=12, pady=7)

        self.update_label = tk.Label(inner, text="", bg=SELECT_BG,
                                     fg=TEXT_HEADING, font=theme.FONT_BOLD)
        self.update_label.pack(side="left")

        dismiss = tk.Label(inner, text="✕", bg=SELECT_BG, fg=TEXT_DIM,
                           font=theme.FONT_BOLD, cursor="hand2", padx=6)
        dismiss.pack(side="right")
        dismiss.bind("<Button-1>", lambda _e: self.update_banner.grid_remove())

        self.btn_update = self._make_action_button(
            inner, "⬇  Download update", self._download_update,
            BLUE_ACCENT, BLUE_HOVER, BLUE_PRESS)
        self.btn_update.pack(side="right", padx=(0, 10), ipadx=10, ipady=3)

        self.update_banner.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.update_banner.grid_remove()

    def _show_update_banner(self):
        if not self.latest_version:
            return
        self.update_label.config(
            text=f"🚀  New version v{self.latest_version} available"
                 f"  (you have v{APP_VERSION})")
        self.update_banner.grid()

    @staticmethod
    def _version_tuple(v: str):
        nums = [int(n) for n in re.findall(r"\d+", v)[:4]]
        return tuple(nums + [0] * (4 - len(nums)))

    def _check_updates_async(self, manual=False):
        threading.Thread(target=lambda: self._check_updates_worker(manual),
                         daemon=True).start()

    def _check_updates_worker(self, manual=False):
        try:
            req = urllib.request.Request(
                GITHUB_API_LATEST,
                headers={"User-Agent": APP_NAME,
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.load(resp)

            tag = (data.get("tag_name") or "").strip().lstrip("vV")
            if not tag:
                return
            if self._version_tuple(tag) <= self._version_tuple(APP_VERSION):
                self._add_log(LogLevel.Debug, f"Up to date (v{APP_VERSION}).")
                if manual:
                    self._ui(lambda: messagebox.showinfo(
                        "No updates",
                        f"You're running the latest version (v{APP_VERSION})."))
                return

            self.latest_version = tag
            self.release_page = (data.get("html_url")
                                 or f"https://github.com/{GITHUB_REPO}/releases/latest")
            # Prefer the installer asset ("…Setup….exe"); fall back to any .exe
            exe_assets = [a for a in data.get("assets", [])
                          if a.get("name", "").lower().endswith(".exe")]
            chosen = next((a for a in exe_assets
                           if "setup" in a.get("name", "").lower()),
                          exe_assets[0] if exe_assets else None)
            if chosen:
                self.update_url = chosen.get("browser_download_url")
                self.update_asset_name = chosen.get("name")

            self._add_log(LogLevel.Info,
                          f"Update available: v{tag} (current: v{APP_VERSION})")
            self._ui(self._show_update_banner)
        except Exception as e:
            # Offline / rate-limited / no releases yet — stay quiet unless asked
            self._add_log(LogLevel.Debug, f"Update check skipped: {e}")
            if manual:
                self._ui(lambda: messagebox.showwarning(
                    "Update check failed",
                    f"Could not check for updates:\n{e}"))

    def _download_update(self):
        if not self.update_url:
            # Release has no .exe asset — open the releases page instead
            webbrowser.open(self.release_page
                            or f"https://github.com/{GITHUB_REPO}/releases/latest")
            return
        self.btn_update.config(state="disabled", text="Downloading…")
        threading.Thread(target=self._download_update_worker, daemon=True).start()

    def _download_update_worker(self):
        try:
            import tempfile
            dest_dir = Path.home() / "Downloads"
            if not dest_dir.exists():
                dest_dir = Path(tempfile.gettempdir())
            dest = dest_dir / self.update_asset_name

            self._add_log(LogLevel.Info,
                          f"Downloading {self.update_asset_name} → {dest}")
            req = urllib.request.Request(
                self.update_url, headers={"User-Agent": APP_NAME})
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0)
                done, last_pct = 0, -25
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = int(done * 100 / total)
                        if pct >= last_pct + 25:
                            last_pct = pct
                            self._add_log(LogLevel.Debug, f"Download… {pct}%")

            self._add_log(LogLevel.Success, f"Update downloaded: {dest}")
            self._ui(lambda: self._prompt_install_update(dest))
        except Exception as e:
            self._add_log(LogLevel.Error, f"Update download failed: {e}")
            self._ui(lambda: self.btn_update.config(
                state="normal", text="⬇  Download update",
                bg=self.btn_update._base))

    def _prompt_install_update(self, dest: Path):
        self.btn_update.config(text="✓  Downloaded")
        if messagebox.askyesno(
                "Update ready",
                f"{dest.name} has been downloaded.\n\n"
                f"Run the installer now? {APP_NAME} will close."):
            try:
                os.startfile(dest)              # Windows
            except AttributeError:              # non-Windows fallback
                import subprocess
                subprocess.Popen(["xdg-open", str(dest)])
            self.on_closing()

    # ─── Live refresh (sidebar, preview, pill) ──────────────────
    def _wire_traces(self):
        for var in (self.selected_command, self.custom_command, self.sudo_mode,
                    self.flashing_mode, self.selected_port,
                    self.selected_programmer, self.remote_dir,
                    self.use_detected):
            var.trace_add("write", lambda *_: self._refresh_dynamic())

    @staticmethod
    def _trunc(s: str, n: int = 30) -> str:
        return s if len(s) <= n else s[: n - 1] + "…"

    def _refresh_dynamic(self):
        """Recompute sidebar statuses + command preview. Main-thread only."""
        if not hasattr(self, "step_items"):
            return

        profile = self._active_profile()

        # Step 1
        if self.is_connected:
            s1, d1 = f"{profile.username}@{profile.ip} ✓", True
        else:
            s1, d1 = f"{profile.username}@{profile.ip}", False

        # Step 2
        if self.file_path:
            s2, d2 = self._trunc(self.file_path.name), True
        else:
            s2, d2 = "No file selected", False

        # Step 3
        mode = self.flashing_mode.get()
        if mode == "usbasp":
            tgt = self.selected_programmer.get()
            s3 = "USBasp" if tgt else "USBasp — none found"
            d3 = bool(tgt)
        else:
            tgt = self.selected_port.get()
            s3 = self._trunc(tgt.split("/")[-1]) if tgt else "Serial — no port"
            d3 = bool(tgt)
        if self.detected_name:
            s3 += f" · {self.detected_name}"

        # Step 4
        base = (self.custom_command.get().strip()
                or self.selected_command.get().strip())
        s4 = self._trunc(base.split()[0] if base else "No command", 26)
        d4 = False

        states = [(d1, s1), (d2, s2), (d3, s3), (d4, s4)]
        for i, (done, sub) in enumerate(states):
            state = ("done " if done else "") + ("active" if i == self.current_step else "todo")
            self.step_items[i].set_state(state, sub)

        # Command preview
        if hasattr(self, "preview_label"):
            fname = self.file_path.name if self.file_path else "<firmware>"
            remote_path = f"{self.remote_dir.get().rstrip('/')}/{fname}"
            self.preview_label.config(text=f"$ {self._compose_command(remote_path)}")

        # Chip badge
        if hasattr(self, "chip_label"):
            if self.detected_name:
                self.chip_label.config(
                    text=f"✓ {self.detected_name}  (0x{self.detected_sig})  →  -p {self.detected_part}",
                    bg=DONE_BG, fg=GREEN_PRESS)
            else:
                self.chip_label.config(text="No chip detected yet",
                                       bg=BG_CARD2, fg=TEXT_DIM)

    # ─── Command composition (shared by preview + flash) ────────
    def _compose_command(self, remote_path: str) -> str:
        cmd = (self.custom_command.get().strip()
               or self.selected_command.get().strip())

        if "avrdude" in cmd:
            if self.detected_part and self.use_detected.get():
                cmd = re.sub(r"-p\s+\S+", f"-p {self.detected_part}", cmd)
            if "-P" not in cmd:
                if self.flashing_mode.get() == "usbasp":
                    prog = self.selected_programmer.get()
                    if prog:
                        cmd = cmd.replace("-U", f"-P {prog} -U", 1)
                else:
                    port = self.selected_port.get()
                    if port:
                        cmd = cmd.replace("-U", f"-P {port} -U", 1)
        elif "esptool" in cmd:
            port = self.selected_port.get()
            if port and "--port" not in cmd:
                parts = cmd.split()
                cmd = f"{parts[0]} --port {port} " + " ".join(parts[1:])
        elif "dfu-util" in cmd:
            port = self.selected_port.get()
            if port and "--device" not in cmd:
                cmd = f"{cmd} --device {port}"

        cmd = f"{cmd}{remote_path}"
        if self.sudo_mode.get():
            cmd = f"sudo {cmd}"
        return cmd

    # ─── Profiles ───────────────────────────────────────────────
    def _load_initial_profile(self):
        profile = self._active_profile()
        if not hasattr(profile, "port_labels") or profile.port_labels is None:
            profile.port_labels = {}
        self.ip_var.set(profile.ip)
        self.username_var.set(profile.username)
        self.port_var.set(profile.port)
        self.auth_var.set(profile.auth_method)
        self.password_var.set(profile.password or "")
        self.key_path_var.set(profile.rsa_key_path or "")
        self._update_status()

    def _active_profile(self) -> ConnectionProfile:
        return self.profiles[min(self.active_profile_idx, len(self.profiles) - 1)]

    def _save_current_profile(self):
        profile = self._active_profile()
        profile.ip = self.ip_var.get()
        profile.username = self.username_var.get()
        profile.port = self.port_var.get()
        profile.auth_method = self.auth_var.get()
        profile.password = self.password_var.get()
        profile.rsa_key_path = self.key_path_var.get() or None
        self._persist_config()
        self._add_log(LogLevel.Success, f"Saved profile: {profile.name}")

    def _new_profile(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Profile")
        dialog.geometry("300x110")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG_CARD)

        ttk.Label(dialog, text="Profile name:").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.pack(pady=5)
        name_entry.focus()

        def create():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Profile name cannot be empty")
                return
            if any(p.name == name for p in self.profiles):
                messagebox.showerror("Error", f"Profile '{name}' already exists")
                return
            self.profiles.append(ConnectionProfile(name=name))
            self.active_profile_idx = len(self.profiles) - 1
            self._persist_config()
            self._refresh_profile_selector()
            dialog.destroy()
            self._add_log(LogLevel.Success, f"Created profile: {name}")

        ttk.Button(dialog, text="Create", command=create).pack(pady=8)
        dialog.bind("<Return>", lambda e: create())

    def _rename_profile(self):
        profile = self._active_profile()

        dialog = tk.Toplevel(self)
        dialog.title("Rename Profile")
        dialog.geometry("300x110")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG_CARD)

        ttk.Label(dialog, text="New profile name:").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.pack(pady=5)
        name_entry.insert(0, profile.name)
        name_entry.select_range(0, "end")
        name_entry.focus()

        def rename():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Profile name cannot be empty", parent=dialog)
                return
            if any(p.name == name for i, p in enumerate(self.profiles)
                   if i != self.active_profile_idx):
                messagebox.showerror("Error", f"Profile '{name}' already exists", parent=dialog)
                return
            old = profile.name
            profile.name = name
            self._persist_config()
            # Refresh the selector without resetting the connection state
            self.profile_combo.config(values=[p.name for p in self.profiles])
            self.profile_combo.current(self.active_profile_idx)
            dialog.destroy()
            self._add_log(LogLevel.Success, f"Renamed profile '{old}' → '{name}'")

        ttk.Button(dialog, text="Rename", command=rename).pack(pady=8)
        dialog.bind("<Return>", lambda e: rename())

    def _delete_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showerror("Error", "Cannot delete the last profile")
            return
        profile = self._active_profile()
        if messagebox.askyesno("Confirm", f"Delete profile '{profile.name}'?"):
            self.profiles.pop(self.active_profile_idx)
            self.active_profile_idx = max(0, self.active_profile_idx - 1)
            self._persist_config()
            self._refresh_profile_selector()
            self._add_log(LogLevel.Warning, f"Deleted profile: {profile.name}")

    def _on_profile_selected(self, idx: int):
        self.active_profile_idx = idx
        profile = self._active_profile()
        self.ip_var.set(profile.ip)
        self.username_var.set(profile.username)
        self.port_var.set(profile.port)
        self.auth_var.set(profile.auth_method)
        self.password_var.set(profile.password or "")
        self.key_path_var.set(profile.rsa_key_path or "")
        self.is_connected = False
        if not hasattr(profile, "port_labels") or profile.port_labels is None:
            profile.port_labels = {}
        self._update_status()

    def _refresh_profile_selector(self):
        self.profile_combo.config(values=[p.name for p in self.profiles])
        self.profile_combo.current(min(self.active_profile_idx, len(self.profiles) - 1))
        self._on_profile_selected(self.profile_combo.current())

    def _select_ssh_key(self):
        filename = filedialog.askopenfilename(
            title="Select SSH Private Key",
            filetypes=[
                ("SSH Keys", "id_rsa id_ecdsa id_ed25519 *.pem"),
                ("PuTTY Keys", "*.ppk"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.key_path_var.set(filename)
            self._add_log(LogLevel.Info, f"Selected SSH key: {filename}")

    def _persist_config(self):
        self.config_data["active_profile_idx"] = self.active_profile_idx
        self.config_data["ssh_timeout"] = self.config_data.get("ssh_timeout", 10)
        self.config_data["remote_label_file"] = self.remote_label_file
        self.config_data["remote_dir"] = self.remote_dir.get()
        self.config_data["delete_after_flash"] = self.delete_after_flash.get()
        self.config_data["custom_commands"] = self.custom_commands
        self.config_data["last_file_path"] = str(self.file_path) if self.file_path else None
        self.config_data["profiles"] = [asdict(p) for p in self.profiles]
        ConfigManager.save(self.config_data)

    # ─── Firmware file ──────────────────────────────────────────
    def _select_file(self):
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Firmware", "*.bin *.hex *.elf *.img *.fw"),
                ("All files", "*.*"),
            ]
        )
        if filename:
            self.file_path = Path(filename)
            size = self.file_path.stat().st_size / 1024
            self.file_label.config(
                text=f"{self.file_path.name}  ({size:.1f} KB)", foreground=GREEN_OK)
            self._persist_config()
            self._refresh_dynamic()

    # ─── Device lists ───────────────────────────────────────────
    def _on_port_pick(self, value):
        self.selected_port.set(value)

    def _on_programmer_pick(self, value):
        self.selected_programmer.set(value)

    def _port_items(self) -> List[dict]:
        labels = self._active_profile().port_labels or {}
        items = []
        for p in self.available_ports:
            label = labels.get(p["path"], "")
            items.append({
                "value": p["path"],
                "title": f"{label}  ·  {p['name']}" if label else p["name"],
                "subtitle": p["path"] + (f"  —  {p['description']}" if p.get("description") else ""),
            })
        return items

    def _programmer_items(self) -> List[dict]:
        labels = self._active_profile().port_labels or {}
        items = []
        for p in self.available_programmers:
            label = labels.get(p["path"], "")
            items.append({
                "value": p["path"],
                "title": f"{label}  ·  {p['name']}" if label else p["name"],
                "subtitle": p.get("description", ""),
            })
        return items

    def _apply_device_lists(self):
        """Push scanned devices into both SelectableLists (main thread)."""
        def _do():
            self.port_list.set_items(self._port_items(),
                                     keep_value=self.selected_port.get() or None)
            if not self.port_list.get():
                self.selected_port.set("")
            self.programmer_list.set_items(self._programmer_items(),
                                           keep_value=self.selected_programmer.get() or None)
            if not self.programmer_list.get():
                self.selected_programmer.set("")
            self._refresh_dynamic()
        self._ui(_do)

    def _refresh_ports(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Not connected. Please connect first.")
            return
        self._set_busy(True)

        def worker():
            try:
                self._add_log(LogLevel.Info, "Scanning for serial ports…")
                self.available_ports = self.ssh_client.list_available_ports()
                if self.available_ports:
                    self._add_log(LogLevel.Success,
                                  f"Found {len(self.available_ports)} port(s)")
                else:
                    self._add_log(LogLevel.Warning, "No serial ports found on device")
                self._apply_device_lists()
            except Exception as e:
                self._add_log(LogLevel.Error, f"Port scan failed: {e}")
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_programmers(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Not connected. Please connect first.")
            return
        self._set_busy(True)

        def worker():
            try:
                self._add_log(LogLevel.Info, "Scanning for USBasp programmers…")
                self.available_programmers = self.ssh_client.list_available_programmers()
                if self.available_programmers:
                    self._add_log(LogLevel.Success,
                                  f"Found {len(self.available_programmers)} programmer(s)")
                else:
                    self._add_log(LogLevel.Warning, "No USBasp programmers found")
                self._apply_device_lists()
            except Exception as e:
                self._add_log(LogLevel.Error, f"Programmer scan failed: {e}")
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def _edit_device_label(self, dev_list: SelectableList, kind: str):
        item = dev_list.selected_item()
        if not item:
            messagebox.showerror("Error", f"No {kind} in the list. Rescan first.")
            return

        path = item["value"]
        profile = self._active_profile()
        if not hasattr(profile, "port_labels") or profile.port_labels is None:
            profile.port_labels = {}
        current_label = profile.port_labels.get(path, "")

        dialog = tk.Toplevel(self)
        dialog.title(f"Rename {kind}")
        dialog.geometry("380x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG_CARD)

        ttk.Label(dialog, text=path, style="Section.TLabel").pack(pady=(12, 4))
        ttk.Label(dialog, text="Custom label (e.g. 'Main ATmega', 'Arduino Uno'):").pack(
            anchor="w", padx=12, pady=(4, 2))
        entry = ttk.Entry(dialog, width=42)
        entry.pack(padx=12, pady=4)
        entry.insert(0, current_label)
        entry.focus()

        def save_label():
            new_label = entry.get().strip()
            if not new_label:
                profile.port_labels.pop(path, None)
                self._add_log(LogLevel.Info, f"Removed label for {path}")
            else:
                profile.port_labels[path] = new_label
                self._add_log(LogLevel.Success, f"Labeled {path} as '{new_label}'")
            self._persist_config()
            if self.is_connected:
                threading.Thread(target=self._save_labels_to_remote,
                                 args=(profile.port_labels,), daemon=True).start()
            self._apply_device_lists()
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=save_label).pack(pady=8)
        dialog.bind("<Return>", lambda e: save_label())

    def _save_labels_to_remote(self, labels: dict):
        try:
            if self.ssh_client.save_port_labels(labels, self.remote_label_file):
                self._add_log(LogLevel.Success, f"Labels saved to {self.remote_label_file}")
            else:
                self._add_log(LogLevel.Warning, "Failed to save labels to remote file")
        except Exception as e:
            self._add_log(LogLevel.Error, f"Error saving labels: {e}")

    # ─── AVR chip detection ─────────────────────────────────────
    def _detect_avr(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Not connected. Please connect first.")
            return
        self._set_busy(True)
        threading.Thread(target=self._detect_avr_worker, daemon=True).start()

    def _detect_avr_worker(self):
        self._add_log(LogLevel.Info, "=== Detecting AVR chip ===")
        cmd = "avrdude -p m328p"
        if self.flashing_mode.get() == "usbasp":
            cmd += " -c usbasp"
            prog = self.selected_programmer.get()
            if prog:
                cmd += f" -P {prog}"
        else:
            cmd += " -c arduino"
            port = self.selected_port.get()
            if port:
                cmd += f" -P {port}"
            else:
                self._add_log(LogLevel.Warning,
                              "Serial mode but no port selected — trying anyway")
        if self.sudo_mode.get():
            cmd = f"sudo {cmd}"

        self._add_log(LogLevel.Command, f"$ {cmd}")
        try:
            out, err, _code = self.ssh_client.exec_command(cmd)
            text = f"{out}\n{err}"

            m = re.search(r"[Dd]evice signature\s*=\s*0x([0-9a-fA-F]{6})", text)
            if not m:
                for line in text.split("\n"):
                    if line.strip():
                        self._add_log(LogLevel.Debug, line.strip())
                self._add_log(LogLevel.Error,
                              "No device signature in avrdude output. "
                              "Check wiring, mode and that avrdude is installed remotely.")
                return

            sig = m.group(1).lower()
            if sig in ("000000", "ffffff"):
                self._add_log(LogLevel.Error,
                              f"Bad signature 0x{sig} — chip not responding "
                              "(check wiring / power / ISP clock).")
                return

            if sig in AVR_SIGNATURES:
                part, name = AVR_SIGNATURES[sig]
                self.detected_part, self.detected_name = part, name
                self.detected_sig = sig.upper()
                self._add_log(LogLevel.Success,
                              f"Detected {name} (signature 0x{sig.upper()}) → avrdude -p {part}")
                if self.use_detected.get():
                    self._add_log(LogLevel.Info,
                                  f"Flash command will use “-p {part}” automatically.")
            else:
                # avrdude sometimes guesses the part itself: "(probably m1284p)"
                guess = re.search(r"\(probably (\S+?)\)", text)
                if guess:
                    part = guess.group(1)
                    self.detected_part = part
                    self.detected_name = part
                    self.detected_sig = sig.upper()
                    self._add_log(LogLevel.Success,
                                  f"Signature 0x{sig.upper()} → avrdude suggests -p {part}")
                else:
                    self.detected_part = None
                    self.detected_name = None
                    self.detected_sig = None
                    self._add_log(LogLevel.Warning,
                                  f"Unknown signature 0x{sig.upper()} — not in local database.")
            self._ui(self._refresh_dynamic)
        except Exception as e:
            self._add_log(LogLevel.Error, f"Detection failed: {e}")
        finally:
            self._set_busy(False)

    # ─── Commands (presets) ─────────────────────────────────────
    def _add_command(self):
        dialog = tk.Toplevel(self)
        dialog.title("Add Command")
        dialog.geometry("420x140")
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=BG_CARD)

        ttk.Label(dialog, text="Enter command:").pack(pady=5)
        cmd_entry = ttk.Entry(dialog, width=52)
        cmd_entry.pack(pady=5, padx=10)
        cmd_entry.focus()

        def add():
            cmd = cmd_entry.get().strip()
            if not cmd:
                messagebox.showerror("Error", "Command cannot be empty")
                return
            if cmd in self.custom_commands:
                messagebox.showerror("Error", "This command already exists")
                return
            self.custom_commands.append(cmd)
            self.command_combo.config(values=self.custom_commands)
            self.selected_command.set(cmd)
            self._persist_config()
            dialog.destroy()
            self._add_log(LogLevel.Success, f"Added command: {cmd}")

        ttk.Button(dialog, text="Add", command=add).pack(pady=8)
        dialog.bind("<Return>", lambda e: add())

    def _remove_command(self):
        current = self.selected_command.get()
        if not current:
            messagebox.showerror("Error", "No command selected")
            return
        if len(self.custom_commands) <= 1:
            messagebox.showerror("Error", "Cannot delete the last command")
            return
        if messagebox.askyesno("Confirm", f"Delete command: {current}?"):
            self.custom_commands.remove(current)
            self.command_combo.config(values=self.custom_commands)
            self.selected_command.set(self.custom_commands[0])
            self._persist_config()
            self._add_log(LogLevel.Warning, f"Removed command: {current}")

    # ─── Ping / Connect ─────────────────────────────────────────
    def _ping_host(self):
        self._set_busy(True)
        threading.Thread(target=self._ping_host_worker, daemon=True).start()

    def _ping_host_worker(self):
        try:
            profile = self._active_profile()
            self._add_log(LogLevel.Info, f"Ping → {self.ip_var.get()}…")
            ms = self.ssh_client.ping_host(self.ip_var.get())
            if ms is not None:
                self._add_log(LogLevel.Success, f"Ping OK: {ms:.0f} ms (TCP)")
                self.ping_ms = ms
                self._update_status()
            else:
                self._add_log(LogLevel.Warning, f"Host {self.ip_var.get()} unreachable")
        finally:
            self._set_busy(False)

    def _toggle_connection(self):
        if self.is_connected:
            try:
                self.ssh_client.disconnect()
            except Exception:
                pass
            self.is_connected = False
            self._add_log(LogLevel.Info, "Disconnected.")
            self._update_status()
        else:
            self._set_busy(True)
            threading.Thread(target=self._connect_worker, daemon=True).start()

    def _connect_worker(self):
        profile = self._active_profile()
        profile.ip = self.ip_var.get()
        profile.username = self.username_var.get()
        profile.port = self.port_var.get()
        profile.auth_method = self.auth_var.get()
        profile.password = self.password_var.get()
        profile.rsa_key_path = self.key_path_var.get() or None

        self._add_log(LogLevel.Info,
                      f"Connecting to {profile.username}@{profile.ip}:{profile.port}…")
        try:
            start = time.time()
            self.ssh_client.connect(profile)
            elapsed = (time.time() - start) * 1000
            self._add_log(LogLevel.Success, f"Connected! ({elapsed:.0f} ms)")

            for probe in ("uname -a", "uptime"):
                try:
                    out, _, _ = self.ssh_client.exec_command(probe)
                    if out:
                        self._add_log(LogLevel.Debug, out)
                except Exception:
                    pass

            # Port labels stored on the remote device
            try:
                remote_labels = self.ssh_client.load_port_labels(self.remote_label_file)
                if remote_labels and isinstance(remote_labels, dict):
                    profile.port_labels.update(remote_labels)
                    self._add_log(LogLevel.Success,
                                  f"Loaded labels from {self.remote_label_file}")
            except Exception as e:
                self._add_log(LogLevel.Debug, f"Could not load remote labels: {e}")

            self.is_connected = True

            # Auto-scan devices
            self._add_log(LogLevel.Info, "Auto-scanning serial ports + USBasp…")
            try:
                self.available_ports = self.ssh_client.list_available_ports()
                self.available_programmers = self.ssh_client.list_available_programmers()
                self._add_log(
                    LogLevel.Success,
                    f"Found {len(self.available_ports)} port(s), "
                    f"{len(self.available_programmers)} USBasp programmer(s)")
                self._apply_device_lists()
            except Exception as e:
                self._add_log(LogLevel.Warning, f"Device scan failed: {e}")

            # Guided flow: jump to the Firmware step
            self._ui(lambda: self._go_step(1))
        except Exception as e:
            self._add_log(LogLevel.Error, f"Connection failed: {e}")
            self.is_connected = False
        finally:
            self._update_status()
            self._set_busy(False)

    # ─── Busy state ─────────────────────────────────────────────
    def _set_busy(self, busy: bool):
        def _apply():
            state = "disabled" if busy else "normal"
            for b in self._busy_buttons:
                b.config(state=state, bg=("#9AA3B2" if busy else b._base))
            if busy:
                self.progress.pack(fill="x", pady=(8, 4))
                self.progress.start(14)
            else:
                self.progress.stop()
                self.progress.pack_forget()
        self._ui(_apply)

    # ─── Flash / read flash ─────────────────────────────────────
    def _run_full_process(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Not connected. Please connect first.")
            return
        if not self.file_path:
            messagebox.showerror("Error", "No file selected.")
            return
        self._set_busy(True)
        threading.Thread(target=self._run_full_process_worker, daemon=True).start()

    def _run_full_process_worker(self):
        file_name = self.file_path.name
        remote_path = f"{self.remote_dir.get().rstrip('/')}/{file_name}"

        self._add_log(LogLevel.Info, f"=== Flash: {file_name} ===")
        try:
            self._add_log(LogLevel.Info, f"Uploading {file_name} → {remote_path}")
            self.ssh_client.sftp_upload(self.file_path, remote_path)
            self._add_log(LogLevel.Success, f"File uploaded: {remote_path}")

            full_cmd = self._compose_command(remote_path)
            if self.detected_part and self.use_detected.get() and "avrdude" in full_cmd:
                self._add_log(LogLevel.Debug,
                              f"Using detected chip: -p {self.detected_part}")

            self._add_log(LogLevel.Command, f"$ {full_cmd}")
            out, err, code = self.ssh_client.exec_command(full_cmd)

            if out:
                for line in out.split("\n"):
                    if line.strip():
                        self._add_log(LogLevel.Debug, line)
            if err:
                for line in err.split("\n"):
                    if line.strip():
                        self._add_log(LogLevel.Warning, line)

            if code == 0:
                self._add_log(LogLevel.Success, "Flash successful!")
                self._add_log(LogLevel.Success, "=== Operation completed successfully ✓ ===")
            else:
                self._add_log(LogLevel.Error, f"Flash failed with code {code}")

            if self.delete_after_flash.get():
                self.ssh_client.exec_command(f"rm -f {remote_path}")
                self._add_log(LogLevel.Info, f"Removed: {remote_path}")
        except Exception as e:
            self._add_log(LogLevel.Error, f"Process failed: {e}")
        finally:
            self._set_busy(False)

    def _read_flash(self):
        if not self.is_connected:
            messagebox.showerror("Error", "Not connected. Please connect first.")
            return

        base_cmd = (self.custom_command.get().strip()
                    or self.selected_command.get().strip())
        match_p = re.search(r"-p\s+(\S+)", base_cmd)
        match_c = re.search(r"-c\s+(\S+)", base_cmd)
        prefill_mcu = self.detected_part or (match_p.group(1) if match_p else "m328p")
        prefill_prog = match_c.group(1) if match_c else "usbasp"

        dialog = tk.Toplevel(self)
        dialog.title("Read Flash from Controller")
        dialog.geometry("380x210")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        grid = ttk.Frame(dialog)
        grid.pack(fill="both", expand=True, padx=15, pady=15)
        grid.columnconfigure(1, weight=1)

        ttk.Label(grid, text="MCU type  (-p):").grid(row=0, column=0, sticky="w", pady=6)
        mcu_var = tk.StringVar(value=prefill_mcu)
        ttk.Combobox(
            grid, textvariable=mcu_var,
            values=sorted({p for p, _ in AVR_SIGNATURES.values()}),
            width=22,
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=6)

        ttk.Label(grid, text="Programmer  (-c):").grid(row=1, column=0, sticky="w", pady=6)
        prog_var = tk.StringVar(value=prefill_prog)
        ttk.Combobox(
            grid, textvariable=prog_var,
            values=["usbasp", "arduino", "wiring", "stk500v2", "usbtiny", "avrisp", "avrisp2"],
            width=22,
        ).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=6)

        ttk.Separator(grid).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        btn_frame = ttk.Frame(grid)
        btn_frame.grid(row=3, column=0, columnspan=2)

        def proceed():
            mcu = mcu_var.get().strip()
            programmer = prog_var.get().strip()
            if not mcu or not programmer:
                messagebox.showerror("Error", "MCU type and programmer are required.",
                                     parent=dialog)
                return
            save_path = filedialog.asksaveasfilename(
                title="Save firmware backup as",
                defaultextension=".hex",
                filetypes=[("Intel HEX", "*.hex"), ("All files", "*.*")],
                initialfile="firmware_backup.hex",
                parent=dialog,
            )
            if not save_path:
                return
            dialog.destroy()
            self._set_busy(True)
            threading.Thread(
                target=self._read_flash_worker,
                args=(Path(save_path), mcu, programmer),
                daemon=True,
            ).start()

        ttk.Button(btn_frame, text="📥 Read Flash", command=proceed, width=16).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy, width=10).pack(side="left", padx=5)
        dialog.bind("<Return>", lambda e: proceed())

    def _read_flash_worker(self, local_save_path: Path, mcu: str, programmer: str):
        self._add_log(LogLevel.Info, "=== Reading flash from controller ===")

        remote_tmp = f"/tmp/flash_read_{local_save_path.stem}.hex"
        read_cmd = f"avrdude -p {mcu} -c {programmer}"

        if self.flashing_mode.get() == "usbasp" or "usbasp" in programmer.lower():
            if self.selected_programmer.get():
                read_cmd += f" -P {self.selected_programmer.get()}"
        elif self.selected_port.get():
            read_cmd += f" -P {self.selected_port.get()}"

        read_cmd += f" -U flash:r:{remote_tmp}:i"
        if self.sudo_mode.get():
            read_cmd = f"sudo {read_cmd}"

        self._add_log(LogLevel.Command, f"$ {read_cmd}")
        try:
            out, err, code = self.ssh_client.exec_command(read_cmd)

            if out:
                for line in out.split("\n"):
                    if line.strip():
                        self._add_log(LogLevel.Debug, line)
            if err:
                for line in err.split("\n"):
                    if line.strip():
                        self._add_log(LogLevel.Warning, line)

            if code != 0:
                self._add_log(LogLevel.Error, f"avrdude read failed (exit code {code})")
                return

            self._add_log(LogLevel.Info, f"Downloading {remote_tmp} → {local_save_path}")
            self.ssh_client.sftp_download(remote_tmp, local_save_path)

            size = local_save_path.stat().st_size / 1024
            self._add_log(LogLevel.Success,
                          f"Firmware saved: {local_save_path.name} ({size:.1f} KB)")
            self._add_log(LogLevel.Success, "=== Read flash completed successfully ✓ ===")

            self.ssh_client.exec_command(f"rm -f {remote_tmp}")
        except Exception as e:
            self._add_log(LogLevel.Error, f"Read flash failed: {e}")
        finally:
            self._set_busy(False)

    # ─── Logs & status ──────────────────────────────────────────
    def _ui(self, func):
        try:
            self.after(0, func)
        except RuntimeError:
            pass

    def _matches_filter(self, entry: "LogEntry") -> bool:
        needle = self.log_filter.get().strip().lower()
        if not needle:
            return True
        return needle in entry.message.lower() or needle in entry.level.value.lower()

    def _add_log(self, level: LogLevel, message: str):
        entry = LogEntry(level=level, message=message, timestamp="")
        self.log_entries.append(entry)

        def _append():
            if not self._matches_filter(entry):
                return
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"{entry.format_display()}\n", level.value)
            self.log_text.see("end")
            self.log_text.config(state="disabled")

        self._ui(_append)

    def _render_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        for entry in self.log_entries:
            if self._matches_filter(entry):
                self.log_text.insert("end", f"{entry.format_display()}\n", entry.level.value)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_logs(self):
        self.log_entries.clear()
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _copy_logs(self):
        text = "\n".join(f"[{e.timestamp}] {e.message}" for e in self.log_entries)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Logs copied to clipboard")

    def _update_status(self):
        profile = self._active_profile()

        def _apply():
            if self.is_connected:
                self.status_label.config(text="● Connected", foreground=GREEN_OK)
                self.conn_pill.config(text="● Connected", bg=DONE_BG, fg=GREEN_PRESS)
                self.connect_button.config(text="✓  Connected — click to disconnect")
                self.connect_button._base, self.connect_button._hover = GREEN_OK, RED_ERR
                if str(self.connect_button["state"]) != "disabled":
                    self.connect_button.config(bg=GREEN_OK)
            else:
                self.status_label.config(text="● Disconnected", foreground=RED_ERR)
                self.conn_pill.config(text="● Disconnected", bg="#FEE2E2", fg=RED_ERR)
                self.connect_button.config(text="🔗  Connect")
                self.connect_button._base, self.connect_button._hover = GREEN_OK, GREEN_HOVER
                if str(self.connect_button["state"]) != "disabled":
                    self.connect_button.config(bg=GREEN_OK)
            self.profile_label.config(text=f"{profile.username}@{profile.ip}:{profile.port}")
            if self.ping_ms:
                self.ping_label.config(text=f"Ping: {self.ping_ms:.0f} ms")
            self._refresh_dynamic()

        self._ui(_apply)

    def on_closing(self):
        self._persist_config()
        self.ssh_client.disconnect()
        self.destroy()


def main():
    app = RemoteFlashApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
