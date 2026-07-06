"""
RemoteFlash — custom Tk widgets.

CollapsibleFrame : a card with a clickable, collapsing header.
StepItem         : one row of the guided-flow sidebar.
SelectableList   : a flat list of clickable rows (replaces comboboxes).
"""

import tkinter as tk
from tkinter import ttk

import theme
from theme import *  # colours + steps (fonts are read via theme.FONT_*)


# ─── Collapsible Frame ─────────────────────────────────────────────
class CollapsibleFrame(ttk.Frame):
    """A card-style frame with a clickable header that collapses/expands."""

    def __init__(self, parent, title="", padding=12, **kwargs):
        super().__init__(parent, style="Card.TFrame", **kwargs)
        self.title = title
        self.padding = padding
        self.is_expanded = True

        # Clickable header bar
        self.header = ttk.Frame(self, style="CardHeader.TFrame", padding=(12, 9))
        self.header.pack(fill="x", expand=False)

        self.chevron = ttk.Label(self.header, text="▾", style="CardChevron.TLabel")
        self.chevron.pack(side="left")
        self.header_label = ttk.Label(self.header, text=title, style="CardHeader.TLabel")
        self.header_label.pack(side="left", padx=(8, 0))

        # Thin accent rule under the header
        self.rule = ttk.Frame(self, style="Rule.TFrame", height=1)
        self.rule.pack(fill="x")

        # Content frame with padding
        self.content_frame = ttk.Frame(self, style="Card.TFrame", padding=padding)
        self.content_frame.pack(fill="both", expand=True)

        for widget in (self.header, self.chevron, self.header_label):
            widget.bind("<Button-1>", lambda _e: self._toggle())
            widget.bind("<Enter>", lambda _e: self.header.configure(style="CardHeaderHover.TFrame"))
            widget.bind("<Leave>", lambda _e: self.header.configure(style="CardHeader.TFrame"))

    def _toggle(self):
        """Toggle between expanded and collapsed states"""
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.rule.pack(fill="x", after=self.header)
            self.content_frame.pack(fill="both", expand=True)
            self.chevron.config(text="▾")
        else:
            self.content_frame.pack_forget()
            self.rule.pack_forget()
            self.chevron.config(text="▸")

    def get_content_frame(self):
        """Return the frame where to place content"""
        return self.content_frame


# ─── Sidebar step item ─────────────────────────────────────────────
class StepItem(tk.Frame):
    """One entry of the guided-flow sidebar: badge, title, live status."""

    def __init__(self, parent, index, icon, title, on_click):
        super().__init__(parent, bg=BG_DARK, cursor="hand2")
        self.index = index
        self.on_click = on_click

        self.accent = tk.Frame(self, width=3, bg=BG_DARK)
        self.accent.pack(side="left", fill="y")

        self.body = tk.Frame(self, bg=BG_DARK)
        self.body.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=10)
        self.body.columnconfigure(1, weight=1)

        self.badge = tk.Label(self.body, text=str(index + 1), width=2,
                              font=(theme.FONT_FAMILY, 10, "bold"),
                              bg=BG_HOVER, fg=TEXT_DIM)
        self.badge.grid(row=0, column=0, rowspan=2, sticky="n", padx=(0, 9))

        self.title_lbl = tk.Label(self.body, text=f"{icon} {title}",
                                  font=theme.FONT_SECTION, bg=BG_DARK, fg=TEXT,
                                  anchor="w")
        self.title_lbl.grid(row=0, column=1, sticky="w")

        self.sub_lbl = tk.Label(self.body, text="", font=(theme.FONT_FAMILY, 9),
                                bg=BG_DARK, fg=TEXT_DIM, anchor="w",
                                justify="left")
        self.sub_lbl.grid(row=1, column=1, sticky="w")

        for w in (self, self.body, self.badge, self.title_lbl, self.sub_lbl):
            w.bind("<Button-1>", lambda _e: self.on_click(self.index))
            w.bind("<Enter>", lambda _e: self._hover(True))
            w.bind("<Leave>", lambda _e: self._hover(False))

        self._state = "todo"
        self.set_state("todo", "")

    def _hover(self, on):
        if self._state == "active":
            return
        bg = BG_HOVER if on else BG_DARK
        for w in (self, self.body, self.title_lbl, self.sub_lbl):
            w.configure(bg=bg)

    def set_state(self, state, subtitle):
        """state: 'todo' | 'active' | 'done' (done can also be active)"""
        self._state = "active" if "active" in state else "todo"
        active = "active" in state
        done = "done" in state

        bg = BG_CARD if active else BG_DARK
        for w in (self, self.body, self.title_lbl, self.sub_lbl):
            w.configure(bg=bg)
        self.accent.configure(bg=BLUE_ACCENT if active else bg)
        self.title_lbl.configure(fg=TEXT_HEADING if active else TEXT)

        if done:
            self.badge.configure(text="✓", bg=DONE_BG, fg=GREEN_OK)
        elif active:
            self.badge.configure(text=str(self.index + 1), bg=BLUE_ACCENT, fg="white")
        else:
            self.badge.configure(text=str(self.index + 1), bg=BG_HOVER, fg=TEXT_DIM)

        self.sub_lbl.configure(text=subtitle)


# ─── Clickable device list (replaces comboboxes) ───────────────────
class SelectableList(tk.Frame):
    """Flat list of clickable rows with hover + selected states."""

    def __init__(self, parent, on_select=None, empty_text="Nothing detected yet"):
        super().__init__(parent, bg=BG_CARD)
        self.on_select = on_select
        self.empty_text = empty_text
        self.items = []          # dicts: {value, title, subtitle}
        self.selected_idx = -1

    def set_items(self, items, keep_value=None):
        self.items = list(items)
        self.selected_idx = -1
        if keep_value is not None:
            for i, it in enumerate(self.items):
                if it["value"] == keep_value:
                    self.selected_idx = i
                    break
        if self.selected_idx < 0 and self.items:
            self.selected_idx = 0
        self._render()
        if self.on_select and self.selected_idx >= 0:
            self.on_select(self.items[self.selected_idx]["value"])

    def get(self):
        if 0 <= self.selected_idx < len(self.items):
            return self.items[self.selected_idx]["value"]
        return ""

    def selected_item(self):
        if 0 <= self.selected_idx < len(self.items):
            return self.items[self.selected_idx]
        return None

    def _render(self):
        for child in self.winfo_children():
            child.destroy()

        if not self.items:
            tk.Label(self, text=self.empty_text, bg=BG_CARD, fg=TEXT_DIM,
                     font=(theme.FONT_FAMILY, 9, "italic"), anchor="w",
                     pady=6).pack(fill="x")
            return

        for i, item in enumerate(self.items):
            selected = (i == self.selected_idx)
            row = tk.Frame(
                self, bg=SELECT_BG if selected else BG_CARD2, cursor="hand2",
                highlightbackground=SELECT_BORDER if selected else BORDER,
                highlightthickness=1,
            )
            row.pack(fill="x", pady=2)

            dot = tk.Label(row, text="◉" if selected else "○",
                           bg=row["bg"], fg=BLUE_ACCENT if selected else TEXT_DIM,
                           font=(theme.FONT_FAMILY, 11))
            dot.pack(side="left", padx=(8, 6), pady=6)

            box = tk.Frame(row, bg=row["bg"])
            box.pack(side="left", fill="x", expand=True, pady=4)
            tk.Label(box, text=item["title"], bg=row["bg"],
                     fg=TEXT_HEADING if selected else TEXT,
                     font=theme.FONT_BOLD, anchor="w").pack(fill="x")
            if item.get("subtitle"):
                tk.Label(box, text=item["subtitle"], bg=row["bg"], fg=TEXT_DIM,
                         font=(theme.FONT_FAMILY, 8), anchor="w").pack(fill="x")

            widgets = [row, dot, box] + list(box.winfo_children())
            for w in widgets:
                w.bind("<Button-1>", lambda _e, idx=i: self._pick(idx))
                if not selected:
                    w.bind("<Enter>", lambda _e, r=row: self._paint(r, BG_HOVER))
                    w.bind("<Leave>", lambda _e, r=row: self._paint(r, BG_CARD2))

    @staticmethod
    def _paint(row, color):
        row.configure(bg=color)
        for child in row.winfo_children():
            child.configure(bg=color)
            for sub in child.winfo_children():
                sub.configure(bg=color)

    def _pick(self, idx):
        self.selected_idx = idx
        self._render()
        if self.on_select:
            self.on_select(self.items[idx]["value"])
