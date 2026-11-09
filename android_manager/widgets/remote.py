# -*- coding: utf-8 -*-
"""Окно пульта: масштабирование, нажатия, режим редактирования."""

import tkinter as tk
from tkinter import ttk

from ..config import C, KEY_COL, REMOTE_H, REMOTE_W
from ..storage import save_settings
from ..util import fit_scale, hit_button
from .canvas import round_rect
from .frames import FlowFrame
from .tooltip import tooltip_btn


class RemoteWindow(tk.Toplevel):
    """Окно пульта. Масштаб подстраивается под размер окна: пульт всегда весь виден."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Пульт")
        self.configure(bg=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.drag = None
        self.moved = False
        self.scale, self.ox, self.oy = 1.0, 0, 0
        head = FlowFrame(self, gap=4)
        head.pack(fill="x", padx=6, pady=6)
        self.box = ttk.Combobox(head, textvariable=app.remote_var, state="readonly", width=28)
        head.add(self.box)
        self.box.bind("<<ComboboxSelected>>", lambda e: app.remote_select(app.remote_var.get()))
        self.edit_btn = tooltip_btn(ttk.Button(head, text="Редактировать: " + ("вкл" if app.remote_edit else "выкл"),
                                   command=app.remote_toggle_edit),
                           "Включить/выключить режим редактирования кнопок пульта")
        head.add(self.edit_btn)
        head.add(tooltip_btn(ttk.Button(head, text="+ Кнопка", command=app.remote_add_button),
                           "Добавить новую кнопку на пульт"))
        head.add(tooltip_btn(ttk.Button(head, text="Новый пульт", command=app.remote_new),
                           "Создать новый пульт"))
        head.add(tooltip_btn(ttk.Button(head, text="Копия", command=app.remote_copy),
                           "Создать копию текущего пульта"))
        head.add(tooltip_btn(ttk.Button(head, text="Переименовать", command=app.remote_rename),
                           "Переименовать текущий пульт"))
        head.add(tooltip_btn(ttk.Button(head, text="Удалить пульт", command=app.remote_delete),
                           "Удалить текущий пульт"))
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self.close())
        # Ensure initial draw after window is laid out
        self.after(50, self._initial_draw)

    def _initial_draw(self):
        """Принудительная перерисовка после того, как окно получило размер."""
        self.update_idletasks()
        self.draw()

    def close(self):
        self.app.remote_win = None
        self.destroy()

    def to_logical(self, x, y):
        return (x - self.ox) / self.scale, (y - self.oy) / self.scale

    def draw(self):
        cw, ch = max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)
        self.scale = fit_scale(cw, ch)
        self.ox = (cw - REMOTE_W * self.scale) / 2
        self.oy = (ch - REMOTE_H * self.scale) / 2
        s, ox, oy = self.scale, self.ox, self.oy
        self.canvas.delete("all")
        round_rect(self.canvas, ox + 10 * s, oy + 10 * s, ox + (REMOTE_W - 10) * s, oy + (REMOTE_H - 10) * s,
                   34 * s, fill=C["body"], outline=C["border"], width=2)
        if self.app.remote_edit:
            self.canvas.create_text(ox + REMOTE_W * s / 2, oy + 22 * s,
                                    text="РЕДАКТИРОВАНИЕ: тяните кнопку, нажмите для настройки",
                                    fill=C["warn"], font=("Segoe UI", max(7, int(8 * s))))
        for b in self.app.current_remote_buttons():
            r = b["r"] * s
            cx, cy = ox + b["x"] * s, oy + b["y"] * s
            outline = C["warn"] if self.app.remote_edit else "#3c5a7d"
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=b.get("color", KEY_COL),
                                    outline=outline, width=2)
            self.canvas.create_text(cx, cy, text=b["label"], fill=C["text"],
                                    font=("Segoe UI", max(6, int(9 * s)), "bold"))

    def _press(self, ev):
        # Ensure canvas has focus for click events
        self.canvas.focus_set()
        lx, ly = self.to_logical(ev.x, ev.y)
        buttons = self.app.current_remote_buttons()
        if not buttons:
            return
        idx = hit_button(buttons, lx, ly)
        self.drag = idx
        self.moved = False
        if idx is not None and not self.app.remote_edit:
            self.app.remote_press(buttons[idx])

    def _motion(self, ev):
        if self.drag is None or not self.app.remote_edit:
            return
        lx, ly = self.to_logical(ev.x, ev.y)
        b = self.app.current_remote_buttons()[self.drag]
        b["x"] = min(max(lx, 20), REMOTE_W - 20)
        b["y"] = min(max(ly, 30), REMOTE_H - 20)
        self.moved = True
        self.draw()

    def _release(self, ev):
        if self.drag is None:
            return
        idx = self.drag
        self.drag = None
        if self.app.remote_edit:
            if self.moved:
                save_settings(self.app.S)
            elif idx is not None:
                self.app.remote_button_dialog(idx)
        self.draw()
