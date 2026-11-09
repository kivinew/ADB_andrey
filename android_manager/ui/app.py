# -*- coding: utf-8 -*-
"""Главное окно приложения: каркас, стили, фон, журнал; собирает вкладки-миксины."""

import datetime
import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from ..config import APP_TITLE, C, VERSION
from ..paths import ADB, BASE, SCRCPY
from ..storage import load_settings, save_settings
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import Tooltip, tooltip_btn
from .dialogs import DialogsTab
from .connection import ConnectionTab
from .bars import BarsTab
from .tab_apps import AppsTab
from .tab_tools import ToolsTab
from .cards import CardsTab
from .procs import ProcsTab
from .actions import ActionsTab
from .tab_console import ConsoleTab
from .tab_scripts import ScriptsTab
from .tab_settings import SettingsTab


class App(DialogsTab, ConnectionTab, BarsTab, AppsTab, ToolsTab, CardsTab, ProcsTab, ActionsTab, ConsoleTab, ScriptsTab, SettingsTab, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} {VERSION}")
        self.geometry("1280x880")
        self.minsize(900, 600)
        self.configure(bg=C["bg"])
        self.S = load_settings()
        save_settings(self.S)
        self.jobs = queue.Queue()
        self.script_q = queue.Queue()
        self.stop_ev = threading.Event()
        self.script_running = False
        self.script_buf = []
        self.app_rows = []
        self.sort_key, self.sort_rev = "mem", True
        self.serial = tk.StringVar()
        self.status = tk.StringVar(value="Не подключено")
        self.devinfo = tk.StringVar(value="")
        self.hist_list, self.hist_i = [], 0
        self.cache = {"props": [], "pkgs": [], "bins": [], "dirs": {}, "pending": set()}
        self.sug_visible = False
        self.bar_frames = {}
        self.card_hist = {}
        self.state_busy = False
        self.proc_busy = False
        self.proc_rows = []
        self.proc_sort = ("cpu", True)
        self.remote_edit = False
        self.remote_win = None
        self.remote_var = tk.StringVar(value=self.S["remote_current"])

        self._style()
        self._build()
        self.render_bar("tools")
        self.render_bar("console")
        self.render_bar("scripts")
        self.render_bar("apps")
        self.render_cards()
        self.reload_programs_buttons()
        self.reload_apks()
        if not os.path.isfile(ADB) and not shutil.which("adb"):
            self.after(200, lambda: self.log("adb не найден. Переустановите программу через установщик."))
        self.refresh_devices()
        self.after(80, self._poll)
        self.after(1000, self._auto_tick)
        self.after(3000, self.check_connection)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------ фон и журнал
    def bg(self, job, done):
        def worker():
            try:
                res = job()
            except Exception as e:  # noqa: BLE001
                res = e
            self.jobs.put((done, res))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        self._drain_script()
        try:
            while True:
                done, res = self.jobs.get_nowait()
                try:
                    done(res)
                except Exception as e:  # noqa: BLE001
                    self.log(f"Ошибка интерфейса: {e}")
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _drain_script(self):
        try:
            while True:
                text = self.script_q.get_nowait()
                self.script_buf.append(text)
                self.script_out.insert("end", text)
                self.script_out.see("end")
        except queue.Empty:
            pass

    def log(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.out.insert("end", f"[{stamp}] {text}\n")
        self.out.see("end")

    def dev(self):
        s = self.serial.get().strip()
        if not s:
            self.log("Сначала подключите устройство")
            return None
        return s

    # ------------------------------------------------ стиль и горячие клавиши
    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        # Глубокий тёмный фон, приглушённые акценты
        st.configure(".", background=C["bg"], foreground=C["text"],
                     fieldbackground=C["panel"], bordercolor=C["border"],
                     lightcolor=C["border"], darkcolor=C["border"])
        st.configure("TFrame", background=C["bg"])
        st.configure("TLabel", background=C["bg"], foreground=C["text"])
        st.configure("TButton", background=C["panel"], foreground=C["text"], padding=(12, 8),
                     borderwidth=1, relief="flat")
        st.map("TButton", background=[("active", C["sel"]), ("pressed", C["accent"])],
               foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
        st.configure("Accent.TButton", background=C["accent"], foreground="#0b1a2b",
                     padding=(12, 8), borderwidth=0, relief="flat")
        st.map("Accent.TButton", background=[("active", "#7bbcf5"), ("pressed", C["accent"])])
        st.configure("TEntry", fieldbackground=C["panel"], foreground=C["text"],
                     insertcolor=C["text"], borderwidth=1, relief="flat")
        st.configure("TCombobox", fieldbackground=C["panel"], foreground=C["text"],
                     background=C["panel"], arrowcolor=C["text"], borderwidth=1, relief="flat")
        st.map("TCombobox", fieldbackground=[("readonly", C["panel"])],
               foreground=[("readonly", C["text"])])
        st.configure("TNotebook", background=C["bar"], borderwidth=0)
        st.configure("TNotebook.Tab", background=C["bar"], foreground=C["muted"],
                     padding=(16, 10), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", C["bg"])],
               foreground=[("selected", "#ffffff")])
        st.configure("Treeview", background=C["panel"], fieldbackground=C["panel"],
                     foreground=C["text"], rowheight=26, borderwidth=0)
        st.map("Treeview", background=[("selected", C["sel"])],
               foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=C["bar"], foreground=C["text"],
                     font=("Segoe UI", 9, "bold"), borderwidth=0, relief="flat")
        st.map("Treeview.Heading", background=[("active", C["sel"])])
        st.configure("TCheckbutton", background=C["bg"], foreground=C["text"])
        st.map("TCheckbutton", background=[("active", C["bg"])])
        st.configure("TLabelframe", background=C["bg"], bordercolor=C["border"],
                     borderwidth=1, relief="solid")
        st.configure("TLabelframe.Label", background=C["bg"], foreground=C["muted"],
                     font=("Segoe UI", 9, "bold"))
        self.bind_class("TEntry", "<Control-KeyPress>", self._ctrl_keys)
        self.bind_class("TCombobox", "<Control-KeyPress>", self._ctrl_keys)
        self.bind_class("Text", "<Control-KeyPress>", self._ctrl_keys)

    def _ctrl_keys(self, ev):
        if ev.keysym.lower() in ("v", "c", "x", "a"):
            return None
        w = ev.widget
        if ev.keycode == 86:
            w.event_generate("<<Paste>>")
        elif ev.keycode == 67:
            w.event_generate("<<Copy>>")
        elif ev.keycode == 88:
            w.event_generate("<<Cut>>")
        elif ev.keycode == 65:
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.selection_range(0, "end")
        else:
            return None
        return "break"

    # ------------------------------------------------ интерфейс
    def _build(self):
        head = tk.Frame(self, bg=C["head"])
        head.pack(fill="x")
        tk.Label(head, text=APP_TITLE, bg=C["head"], fg="#ffffff",
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        row = tk.Frame(head, bg=C["head"])
        row.pack(fill="x", padx=12, pady=(0, 8))
        self.status_lbl = tk.Label(row, textvariable=self.status, bg=C["head"], fg=C["err"],
                                   font=("Segoe UI", 10, "bold"))
        self.status_lbl.pack(side="left")
        tk.Label(row, textvariable=self.devinfo, bg=C["head"], fg=C["muted"], font=("Segoe UI", 10)).pack(side="right")

        bar = FlowFrame(self, gap=6)
        bar.pack(fill="x", padx=8, pady=6)
        bar.add(ttk.Label(bar, text="IP или URL:"))
        self.host_var = tk.StringVar()
        self.host_var.trace_add("write", self._fix_host)
        bar.add(ttk.Entry(bar, textvariable=self.host_var, width=28))
        bar.add(ttk.Label(bar, text="Порт:"))
        self.port_var = tk.StringVar(value="5555")
        self.port_var.trace_add("write", self._fix_port)
        bar.add(ttk.Entry(bar, textvariable=self.port_var, width=7))
        self.toggle_btn = tooltip_btn(ttk.Button(bar, text="Подключить", style="Accent.TButton", command=self.toggle_connection),
                           "Подключиться к устройству по IP:порт (adb connect)")
        bar.add(self.toggle_btn)
        bar.add(tooltip_btn(ttk.Button(bar, text="Сопрячь", command=self.pair_dialog),
                           "Сопрячь устройство по Wi-Fi (adb pair) — для Android 11+"))
        self.hist_btn = bar.add(tooltip_btn(ttk.Button(bar, text="История ▾", command=self.history_menu),
                           "История подключений — быстрый выбор IP"))
        self.fav_btn = bar.add(tooltip_btn(ttk.Button(bar, text="Избранное ▾", command=self.favorites_menu),
                           "Избранные устройства — сохранённые IP для быстрого доступа"))
        bar.add(ttk.Label(bar, text="Устройство:"))
        self.dev_box = ttk.Combobox(bar, textvariable=self.serial, width=26, state="readonly")
        bar.add(self.dev_box)
        self.dev_box.bind("<<ComboboxSelected>>", lambda e: self.device_info())
        bar.add(tooltip_btn(ttk.Button(bar, text="Обновить", command=self.refresh_devices),
                           "Обновить список подключённых устройств (adb devices -l)"))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.nb = nb
        self.tab_apps(nb)
        self.tab_tools(nb)
        self.tab_console(nb)
        self.tab_scripts(nb)
        self.tab_settings(nb)
        self.tab_logs(nb)
        self.tab_about(nb)
        nb.bind("<<NotebookTabChanged>>", lambda e: self.on_main_tab())

    def tab_logs(self, nb):
        """Журнал программы: все сообщения о действиях. Можно копировать и очистить."""
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="Логи")
        Tooltip(f, "Журнал действий программы: копировать или очистить")
        row = FlowFrame(f, gap=6)
        row.pack(fill="x")
        row.add(tooltip_btn(ttk.Button(row, text="Копировать всё", command=lambda: self.copy_text(self.out.get("1.0", "end").rstrip())),
                           "Скопировать весь лог в буфер обмена"))
        row.add(tooltip_btn(ttk.Button(row, text="Очистить", command=lambda: self.out.delete("1.0", "end")),
                           "Очистить лог"))
        self.out = scrolledtext.ScrolledText(f, bg=C["term"], fg=C["text"], insertbackground=C["text"],
                                             font=("Consolas", 10), relief="flat", wrap="word")
        self.out.pack(fill="both", expand=True, pady=(6, 0))

    # ------------------------------------------------ вкладка «О программе»
    def tab_about(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="О программе")
        Tooltip(f, "Версия, пути к adb/scrcpy, папка программы")
        ttk.Label(f, text=f"{APP_TITLE} {VERSION}", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Папка программы: {BASE}").pack(anchor="w", pady=4)
        ttk.Label(f, text=f"ADB: {ADB}").pack(anchor="w")
        ttk.Label(f, text=f"scrcpy: {SCRCPY}").pack(anchor="w")
        btn = ttk.Button(f, text="Открыть папку программы", command=lambda: os.startfile(BASE) if os.name == "nt" else None)
        Tooltip(btn, "Открыть папку с программой в проводнике")
        btn.pack(anchor="w", pady=12)

    # ------------------------------------------------ выход
    def on_close(self):
        self.stop_ev.set()
        save_settings(self.S)
        self.destroy()
