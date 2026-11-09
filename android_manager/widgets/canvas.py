# -*- coding: utf-8 -*-
"""Рисование на Canvas: скругление, спарклайн, индикатор."""

import tkinter as tk

from ..config import C


# ---------------------------------------------------------------- виджеты
def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Spark(tk.Canvas):
    """График последних значений в процентах."""

    def __init__(self, master, color, w=280, h=64):
        super().__init__(master, width=w, height=h, bg=C["term"], highlightthickness=0)
        self.color, self.w, self.h = color, w, h

    def draw(self, values, label=""):
        self.delete("all")
        for pct in (25, 50, 75):
            y = self.h - (pct / 100) * (self.h - 6) - 3
            self.create_line(0, y, self.w, y, fill="#1d3247")
        vals = [v for v in values if v is not None]
        if len(vals) >= 2:
            step = self.w / max(1, len(values) - 1)
            pts = []
            for i, v in enumerate(values):
                v = 0 if v is None else v
                pts += [i * step, self.h - (max(0, min(100, v)) / 100) * (self.h - 6) - 3]
            self.create_line(*pts, fill=self.color, width=2, smooth=True)
        if label:
            self.create_text(self.w - 6, 4, anchor="ne", fill=C["text"], text=label, font=("Segoe UI", 9, "bold"))


class Gauge(tk.Canvas):
    """Шкала занятости памяти: цвет меняется от зелёного к красному."""

    def __init__(self, master, title):
        super().__init__(master, width=330, height=58, bg=C["bg"], highlightthickness=0)
        self.title = title

    def draw(self, used, total):
        self.delete("all")
        if not total:
            self.create_text(4, 4, anchor="nw", fill=C["muted"], text=f"{self.title}: нет данных",
                             font=("Segoe UI", 9))
            return
        pct = min(100.0, used * 100.0 / total)
        color = C["ok"] if pct < 70 else (C["warn"] if pct < 90 else C["err"])
        self.create_text(4, 2, anchor="nw", fill=C["text"], font=("Segoe UI", 9, "bold"),
                         text=f"{self.title}: {used} из {total} МБ  ({pct:.0f}%)")
        self.create_rectangle(4, 28, 326, 50, fill=C["panel"], outline=C["border"])
        self.create_rectangle(4, 28, 4 + 322 * pct / 100, 50, fill=color, outline="")
