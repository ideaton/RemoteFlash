"""
RemoteFlash — visual theme: colour palette, fonts, guided-flow steps and the
ttk style setup.

Fonts are resolved at runtime against what's installed (call apply_theme once,
after the Tk root exists). Read the FONT_* values through the module
(``theme.FONT_BASE``) so callers always see the resolved family.
"""

import tkinter as tk
from tkinter import ttk

# ─── Colour palette ────────────────────────────────────────────────
# A cohesive modern light palette applied to every ttk widget below.
BLUE_ACCENT = "#2563EB"   # primary accent
BLUE_HOVER = "#1D4ED8"
BLUE_PRESS = "#1E40AF"
GREEN_OK = "#16A34A"
GREEN_HOVER = "#15803D"
GREEN_PRESS = "#166534"
RED_ERR = "#DC2626"
ORANGE_WARN = "#D97706"

BG_DARK = "#F8F9FA"       # window background
BG_CARD = "#FFFFFF"       # card / section background
BG_CARD2 = "#F1F3F5"      # inset (entries, console)
BG_HOVER = "#E9ECEF"      # hovered surface
BORDER = "#DEE2E6"        # subtle separators / outlines
BORDER_FOCUS = BLUE_ACCENT

TEXT = "#212529"          # primary text
TEXT_DIM = "#6C757D"      # secondary / muted text
TEXT_HEADING = "#0F172A"

SELECT_BG = "#DBEAFE"     # selected row (light blue)
SELECT_BORDER = BLUE_ACCENT
DONE_BG = "#DCFCE7"       # green badge background

# ─── Fonts (family resolved at runtime by apply_theme) ─────────────
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Cascadia Mono"
FONT_BASE = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 10, "bold")
FONT_TITLE = (FONT_FAMILY, 19, "bold")
FONT_SUBTITLE = (FONT_FAMILY, 10)
FONT_SECTION = (FONT_FAMILY, 11, "bold")
FONT_BTN = (FONT_FAMILY, 11, "bold")

# ─── Guided-flow steps ─────────────────────────────────────────────
STEPS = [
    ("🌐", "Connection", "SSH target device"),
    ("📁", "Firmware", "File to upload"),
    ("🎯", "Target", "Port · programmer · chip"),
    ("⚡", "Flash", "Command & run"),
]

# Colours + steps are safe to bind by name; fonts must be read via
# ``theme.FONT_*`` so they reflect the runtime resolution done in apply_theme.
__all__ = [
    "BLUE_ACCENT", "BLUE_HOVER", "BLUE_PRESS",
    "GREEN_OK", "GREEN_HOVER", "GREEN_PRESS",
    "RED_ERR", "ORANGE_WARN",
    "BG_DARK", "BG_CARD", "BG_CARD2", "BG_HOVER",
    "BORDER", "BORDER_FOCUS",
    "TEXT", "TEXT_DIM", "TEXT_HEADING",
    "SELECT_BG", "SELECT_BORDER", "DONE_BG",
    "STEPS", "apply_theme",
]


def apply_theme(root: tk.Tk):
    """Resolve fonts against installed families and configure every ttk style.

    Call once, after the Tk root has been created.
    """
    import tkinter.font as tkfont

    global FONT_FAMILY, FONT_MONO, FONT_BASE, FONT_BOLD, FONT_TITLE
    global FONT_SUBTITLE, FONT_SECTION, FONT_BTN
    available = set(tkfont.families())

    def pick(candidates, fallback):
        for name in candidates:
            if name in available:
                return name
        return fallback

    FONT_FAMILY = pick(["Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans"], "TkDefaultFont")
    FONT_MONO = pick(["Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo", "DejaVu Sans Mono"], "TkFixedFont")
    FONT_BASE = (FONT_FAMILY, 10)
    FONT_BOLD = (FONT_FAMILY, 10, "bold")
    FONT_TITLE = (FONT_FAMILY, 19, "bold")
    FONT_SUBTITLE = (FONT_FAMILY, 10)
    FONT_SECTION = (FONT_FAMILY, 11, "bold")
    FONT_BTN = (FONT_FAMILY, 11, "bold")

    root.configure(bg=BG_DARK)
    root.option_add("*TCombobox*Listbox.background", BG_CARD2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", BLUE_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", FONT_BASE)

    style = ttk.Style()
    style.theme_use("clam")

    style.configure(".", background=BG_DARK, foreground=TEXT,
                    fieldbackground=BG_CARD2, bordercolor=BORDER,
                    font=FONT_BASE)
    style.configure("TFrame", background=BG_CARD)
    style.configure("Root.TFrame", background=BG_DARK)
    style.configure("Card.TFrame", background=BG_CARD)
    style.configure("Rule.TFrame", background=BORDER)

    style.configure("TLabel", background=BG_CARD, foreground=TEXT)
    style.configure("Card.TLabel", background=BG_CARD, foreground=TEXT)
    style.configure("Section.TLabel", background=BG_CARD,
                    foreground=TEXT_HEADING, font=FONT_SECTION)
    style.configure("PanelTitle.TLabel", background=BG_DARK,
                    foreground=TEXT_HEADING, font=(FONT_FAMILY, 15, "bold"))
    style.configure("PanelDesc.TLabel", background=BG_DARK,
                    foreground=TEXT_DIM, font=FONT_SUBTITLE)
    style.configure("Title.TLabel", background=BG_DARK,
                    foreground=TEXT_HEADING, font=FONT_TITLE)
    style.configure("Subtitle.TLabel", background=BG_DARK,
                    foreground=TEXT_DIM, font=FONT_SUBTITLE)
    style.configure("Dim.TLabel", background=BG_DARK, foreground=TEXT_DIM)
    style.configure("CardDim.TLabel", background=BG_CARD, foreground=TEXT_DIM)
    style.configure("Status.TLabel", background=BG_DARK, font=FONT_BOLD)
    style.configure("Chip.TLabel", background=DONE_BG, foreground=GREEN_PRESS,
                    font=FONT_BOLD, padding=(8, 3))

    style.configure("TButton", background=BG_CARD2, foreground=TEXT,
                    bordercolor=BORDER, focuscolor=BG_CARD,
                    relief="flat", padding=(10, 6), font=FONT_BASE)
    style.map("TButton",
              background=[("pressed", BG_DARK), ("active", BG_HOVER)],
              foreground=[("disabled", TEXT_DIM)],
              bordercolor=[("active", BLUE_ACCENT)])

    for el in ("TEntry", "TSpinbox"):
        style.configure(el, fieldbackground=BG_CARD2, foreground=TEXT,
                        bordercolor=BORDER, insertcolor=TEXT,
                        relief="flat", padding=5)
        style.map(el, bordercolor=[("focus", BORDER_FOCUS)],
                  lightcolor=[("focus", BORDER_FOCUS)],
                  darkcolor=[("focus", BORDER_FOCUS)])
    style.configure("TSpinbox", arrowcolor=TEXT_DIM)

    style.configure("TCombobox", fieldbackground=BG_CARD2, background=BG_CARD2,
                    foreground=TEXT, arrowcolor=TEXT_DIM, bordercolor=BORDER,
                    relief="flat", padding=5)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_CARD2)],
              foreground=[("readonly", TEXT)],
              bordercolor=[("focus", BORDER_FOCUS), ("active", BLUE_ACCENT)],
              arrowcolor=[("active", BLUE_ACCENT)])

    for el in ("TCheckbutton", "TRadiobutton"):
        style.configure(el, background=BG_CARD, foreground=TEXT,
                        focuscolor=BG_CARD, indicatorcolor=BG_CARD2,
                        indicatorbackground=BG_CARD2)
        style.map(el,
                  background=[("active", BG_CARD)],
                  foreground=[("disabled", TEXT_DIM)],
                  indicatorcolor=[("selected", BLUE_ACCENT),
                                  ("active", BG_HOVER)])

    style.configure("TLabelframe", background=BG_CARD, bordercolor=BORDER,
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=BG_CARD,
                    foreground=TEXT_HEADING, font=FONT_SECTION)

    for el in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(el, background=BG_CARD2, troughcolor=BG_DARK,
                        bordercolor=BG_DARK, arrowcolor=TEXT_DIM,
                        relief="flat")
        style.map(el, background=[("active", BG_HOVER)])

    style.configure("Accent.Horizontal.TProgressbar",
                    troughcolor=BG_CARD2, background=BLUE_ACCENT,
                    bordercolor=BG_CARD2, lightcolor=BLUE_ACCENT,
                    darkcolor=BLUE_ACCENT, thickness=6)
