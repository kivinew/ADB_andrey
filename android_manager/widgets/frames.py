# -*- coding: utf-8 -*-
"""Контейнеры: адаптивный FlowFrame, сетка кнопок, прокручиваемая область."""

import tkinter as tk
from tkinter import ttk

from ..config import C
from ..util import flow_layout


class FlowFrame(ttk.Frame):
    """Контейнер: дочерние элементы переносятся на новую строку, когда не хватает ширины."""

    def __init__(self, master, gap=6, **kw):
        super().__init__(master, **kw)
        self.gap = gap
        self.items = []
        self._relayout_lock = False
        self.bind("<Configure>", lambda e: self.after_idle(self.relayout))

    def add(self, widget):
        self.items.append(widget)
        self.after_idle(self.relayout)
        return widget

    def relayout(self):
        # Debounce: prevent multiple rapid calls during window resize
        if self._relayout_lock:
            return
        self._relayout_lock = True
        try:
            self.items = [w for w in self.items if w is not None and w.winfo_exists()]
            sizes = [(w.winfo_reqwidth(), w.winfo_reqheight()) for w in self.items]
            pos, total = flow_layout(sizes, self.winfo_width(), self.gap)
            for w, (x, y) in zip(self.items, pos):
                w.place(x=x, y=y)
            h = max(total, 1)
            if int(float(self.cget("height") or 0)) != h:
                self.configure(height=h)
        finally:
            self._relayout_lock = False

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []
        self.configure(height=1)


class ButtonPanel(ttk.Frame):
    """Панель кнопок в виде равномерной сетки: 2 колонки, одинаковая ширина кнопок."""
    def __init__(self, master, columns=2, gap=8, **kw):
        super().__init__(master, **kw)
        self.columns = columns
        self.gap = gap
        self.items = []
        for c in range(columns):
            self.grid_columnconfigure(c, weight=1, uniform="btn")

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []

    def add(self, widget):
        row = len(self.items) // self.columns
        col = len(self.items) % self.columns
        widget.grid(row=row, column=col, sticky="we", padx=self.gap // 2, pady=self.gap // 2)
        self.items.append(widget)
        return widget


class ScrollFrame(ttk.Frame):
    """Прокручиваемая область: если окно маленькое, всё остаётся доступным."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, ev):
        self.canvas.yview_scroll(int(-ev.delta / 120), "units")
