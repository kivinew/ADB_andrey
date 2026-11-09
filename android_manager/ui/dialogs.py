# -*- coding: utf-8 -*-
"""Раздел интерфейса: DialogsTab."""

import tkinter as tk
from tkinter import ttk, scrolledtext

from ..config import C
from ..paths import ADB
from ..proc import run
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import tooltip_btn


class DialogsTab:
    """Mix-in для App: методы этого раздела окна."""

    def show_text(self, title, text):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("820x520")
        win.configure(bg=C["bg"])
        win.transient(self)
        box = scrolledtext.ScrolledText(win, bg=C["term"], fg=C["text"], font=("Consolas", 10), wrap="word")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        box.insert("1.0", text if text.strip() else "(пустой ответ)")
        bar = FlowFrame(win, gap=6)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        bar.add(tooltip_btn(ttk.Button(bar, text="Копировать", command=lambda: self.copy_text(text)),
                           "Скопировать текст в буфер обмена"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Закрыть", style="Accent.TButton", command=win.destroy),
                           "Закрыть окно"))
        win.bind("<Escape>", lambda e: win.destroy())

    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("Скопировано в буфер обмена")

    def popup(self, items, x, y):
        m = tk.Menu(self, tearoff=0, bg=C["panel"], fg=C["text"], activebackground=C["sel"])
        if not items:
            m.add_command(label="(пусто)", state="disabled")
        for label, cmd in items:
            m.add_command(label=label, command=cmd)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    # ------------------------------------------------ общие диалоги
    def ask_fields(self, title, names, defaults=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both")
        vars_ = {}
        for i, n in enumerate(names):
            ttk.Label(frm, text=n).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=(defaults or {}).get(n, ""))
            ttk.Entry(frm, textvariable=v, width=44).grid(row=i, column=1, padx=6, pady=3)
            vars_[n] = v
        result = {}

        def ok():
            result.update({k: v.get() for k, v in vars_.items()})
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=len(names), column=0, columnspan=2, sticky="we", pady=(10, 0))
        bar.add(tooltip_btn(ttk.Button(bar, text="Отмена", command=win.destroy),
                           "Отменить"))
        bar.add(tooltip_btn(ttk.Button(bar, text="OK", style="Accent.TButton", command=ok),
                           "Подтвердить"))
        win.bind("<Return>", lambda e: ok())
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.wait_window()
        return result or None

    def ask_multiline(self, title, name, text, hint="", can_delete=False):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("660x480")
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        nv = tk.StringVar(value=name)
        ttk.Label(frm, text="Название кнопки").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=nv, width=48).grid(row=0, column=1, sticky="we", padx=6, pady=3)
        ttk.Label(frm, text="Команда / код").grid(row=1, column=0, sticky="nw")
        txt = scrolledtext.ScrolledText(frm, height=12, bg=C["term"], fg=C["text"], font=("Consolas", 10),
                                        relief="flat", insertbackground=C["text"], undo=True)
        txt.grid(row=1, column=1, sticky="nsew", padx=6, pady=3)
        txt.insert("1.0", text)
        ttk.Label(frm, text=hint, foreground=C["muted"], wraplength=520).grid(row=2, column=0, columnspan=2,
                                                                              sticky="w", pady=6)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(1, weight=1)
        result = {}

        def ok():
            result["v"] = (nv.get().strip(), txt.get("1.0", "end").rstrip("\n"))
            win.destroy()

        def delete():
            result["v"] = "delete"
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=3, column=0, columnspan=2, sticky="we")
        if can_delete:
            bar.add(tooltip_btn(ttk.Button(bar, text="Удалить", command=delete),
                           "Удалить элемент"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=ok),
                           "Сохранить изменения"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Отмена", command=win.destroy),
                           "Отменить без сохранения"))
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.wait_window()
        return result.get("v")

    def run_popup_cmd(self, label, cmd):
        s = self.dev()
        if not s or not cmd.strip():
            return
        self.log(f"Выполняется: {label}...")
        self.bg(lambda: run([ADB, "-s", s, "shell", cmd], 120), lambda res: self.show_result(label, res))

    def show_result(self, label, res):
        if isinstance(res, Exception):
            self.show_text(label, f"Ошибка: {res}")
            return
        rc, out, err = res
        text = (out + err).rstrip()
        self.log(f"{label}: код {rc}")
        self.show_text(f"{label} (код {rc})", text if text else "(команда выполнилась, вывода нет)")
