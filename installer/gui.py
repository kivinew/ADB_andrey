# -*- coding: utf-8 -*-
"""Окно установщика."""

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from android_manager.config import APP_TITLE, VERSION
from android_manager.widgets.tooltip import tooltip_btn
from .config import DEFAULT_PARENT
from .service import InstallError, install, resolve_install_dir


# ================================================================ окно установщика
class InstallerWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Установка: {APP_TITLE} {VERSION}")
        self.geometry("760x560")
        self.configure(bg="#14202e")
        self.q = queue.Queue()
        self.parent_dir = DEFAULT_PARENT
        ttk.Style(self).theme_use("clam")

        tk.Label(self, text=APP_TITLE, bg="#1e4170", fg="#ffffff", font=("Segoe UI", 16, "bold"),
                 anchor="w", padx=14, pady=10).pack(fill="x")
        pick = tk.Frame(self, bg="#14202e")
        pick.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(pick, text="Куда установить:", bg="#14202e", fg="#e6edf5",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = tk.Frame(pick, bg="#14202e")
        row.pack(fill="x", pady=4)
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(row, textvariable=self.path_var, font=("Segoe UI", 10),
                                   bg="#1e2e42", fg="#e6edf5", insertbackground="#e6edf5", relief="flat")
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.browse_btn = tk.Button(row, text="Выбрать папку...", command=self.browse, bg="#243a55",
                                    fg="#e6edf5", relief="flat", padx=12, pady=4)
        tooltip_btn(self.browse_btn, "Выбрать папку установки программы")
        self.browse_btn.pack(side="left", padx=(8, 0))
        self.path_var.trace_add("write", lambda *a: self._update_hint())
        self.hint = tk.Label(pick, text="", bg="#14202e", fg="#9fb4cc", font=("Segoe UI", 9), anchor="w",
                             justify="left", wraplength=700)
        self.hint.pack(fill="x")
        self.path_var.set(resolve_install_dir(self.parent_dir))

        self.log_box = scrolledtext.ScrolledText(self, bg="#0b121b", fg="#e6edf5", font=("Consolas", 10),
                                                 relief="flat", wrap="word", height=18)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        # Контекстное меню для копирования
        self.log_menu = tk.Menu(self, tearoff=0)
        self.log_menu.add_command(label="Копировать", command=self._copy_log_selection)
        self.log_menu.add_command(label="Копировать всё", command=self._copy_all_log)
        self.log_box.bind("<Button-3>", self._show_log_menu)
        self.btn = tk.Button(self, text="Установить",
                             font=("Segoe UI", 11, "bold"), bg="#5aa9f0",
                             fg="#0b1a2b", relief="flat", padx=24, pady=8, command=self.start)
        tooltip_btn(self.btn, "Запустить установку в выбранную папку (нужен интернет)")
        self.btn.pack(pady=(0, 12))
        self.write("Выберите папку установки (по умолчанию - профиль пользователя) и нажмите «Установить».")
        self.write("Нужен интернет. Установка занимает несколько минут.")

    def _update_hint(self):
        self.hint.config(text=f"Программа будет установлена в: {self.path_var.get().strip()}")

    def browse(self):
        chosen = filedialog.askdirectory(parent=self, initialdir=self.parent_dir,
                                         title="Выберите папку, куда установить Android ТВ-Менеджер")
        if chosen:
            self.parent_dir = chosen
            self.path_var.set(resolve_install_dir(chosen))

    def write(self, text):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def start(self):
        install_dir = self.path_var.get().strip()
        if not install_dir:
            self.write("ОШИБКА: укажите папку установки")
            return
        self.btn.config(state="disabled", text="Идёт установка...")
        self.browse_btn.config(state="disabled")
        self.path_entry.config(state="disabled")
        threading.Thread(target=self._worker, args=(os.path.abspath(install_dir),), daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, install_dir):
        try:
            install(lambda m: self.q.put(("log", m)), install_dir)
            self.q.put(("done", "ok"))
        except InstallError as e:
            self.q.put(("log", "ОШИБКА: " + str(e)))
            self.q.put(("done", "fail"))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"ОШИБКА: {e!r}"))
            self.q.put(("done", "fail"))

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.write(val)
                elif kind == "done":
                    if val == "ok":
                        self.btn.config(text="Готово", bg="#7fd68f", state="normal", command=self.destroy)
                    else:
                        self.btn.config(text="Закрыть", bg="#ff7b7b", state="normal", command=self.destroy)
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show_log_menu(self, ev):
        try:
            self.log_menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            self.log_menu.grab_release()

    def _copy_log_selection(self):
        try:
            text = self.log_box.get("sel.first", "sel.last")
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
        except tk.TclError:
            pass

    def _copy_all_log(self):
        text = self.log_box.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
