# -*- coding: utf-8 -*-
"""Всплывающие подсказки к кнопкам."""

import tkinter as tk


# ------------------------------------------------ tooltip-подсказки
class Tooltip:
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwin = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, ev=None):
        self.id = self.widget.after(self.delay, self.show)

    def on_leave(self, ev=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self.hide()

    def show(self):
        if self.tipwin:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipwin = tk.Toplevel(self.widget)
        self.tipwin.wm_overrideredirect(True)
        self.tipwin.wm_geometry(f"+{x}+{y}")
        self.tipwin.configure(bg="#243a55", bd=1, relief="solid")
        lbl = tk.Label(self.tipwin, text=self.text, justify="left", bg="#243a55",
                       fg="#e6edf5", font=("Segoe UI", 9), padx=6, pady=3)
        lbl.pack()
        self.tipwin.update_idletasks()

    def hide(self):
        if self.tipwin:
            self.tipwin.destroy()
            self.tipwin = None


def tooltip_btn(btn, text):
    Tooltip(btn, text)
    return btn
