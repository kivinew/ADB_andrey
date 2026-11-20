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
        self._job = None
        self._force = False
        self._last_width = 0
        self.bind("<Configure>", self._queue_relayout)

    def _queue_relayout(self, _event=None, force=False):
        """Один relayout на пачку событий: при перетаскивании границы окна Tk
        успевает прислать десятки <Configure>, а winfo_reqwidth на каждого
        ребёнка — отдельный запрос к интерпретатору."""
        self._force = self._force or force
        if self._job is None:
            self._job = self.after(30, self._run_relayout)

    def _run_relayout(self):
        self._job = None
        force, self._force = self._force, False
        self.relayout(force=force)

    def add(self, widget):
        self.items.append(widget)
        self._queue_relayout(force=True)
        return widget

    def relayout(self, force=False):
        width = self.winfo_width()
        if width <= 1 or (width == self._last_width and not force):
            return
        self._last_width = width
        self.items = [w for w in self.items if w is not None and w.winfo_exists()]
        sizes = [(w.winfo_reqwidth(), w.winfo_reqheight()) for w in self.items]
        pos, total = flow_layout(sizes, width, self.gap)
        for w, (x, y) in zip(self.items, pos):
            w.place(x=x, y=y)
        h = max(total, 1)
        current_h = self.cget("height")
        if int(float(str(current_h) or 0)) != h:
            self.configure(height=h)

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []
        self._last_width = 0
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
