# -*- coding: utf-8 -*-
"""Раздел интерфейса: SettingsTab."""

import json
import tkinter as tk
from tkinter import ttk, filedialog

from ..config import C
from ..paths import P, SCRIPTS_DIR
from ..storage import apply_bundle, load_json_folder, make_bundle, save_settings, write_json
from ..util import slug
from ..widgets.frames import ScrollFrame
from ..widgets.tooltip import Tooltip, tooltip_btn


class SettingsTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ вкладка «Настройки»
    def tab_settings(self, nb):
        sf = ScrollFrame(nb)
        nb.add(sf, text="Настройки")
        Tooltip(sf, "IP ПК, путь Vysor, экспорт/импорт настроек и кнопок")
        f = sf.inner
        f.configure(padding=12)
        self.set_pc_ip = tk.StringVar(value=self.S.get("pc_ip", ""))
        ttk.Label(f, text="IP этого ПК (пусто = автоопределение)").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.set_pc_ip, width=24).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Текущий адрес: " + self.pc_ip()).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        ttk.Label(f, text="Путь к Vysor").grid(row=2, column=0, sticky="w")
        self.set_vysor = tk.StringVar(value=self.S.get("vysor_path", ""))
        ttk.Entry(f, textvariable=self.set_vysor, width=60).grid(row=2, column=1, sticky="w", padx=6)
        tooltip_btn(ttk.Button(f, text="Сохранить настройки", style="Accent.TButton", command=self.save_settings_ui),
                           "Сохранить IP ПК и путь к Vysor").grid(row=3, column=0, sticky="w", pady=12)
        tooltip_btn(ttk.Button(f, text="Экспорт всего в один файл...", command=self.export_bundle),
                           "Экспортировать все настройки, кнопки, скрипты, пульты в один JSON-файл").grid(row=4, column=0, sticky="w", pady=4)
        tooltip_btn(ttk.Button(f, text="Импорт из файла...", command=self.import_bundle),
                           "Импортировать настройки, кнопки, скрипты, пульты из JSON-файла").grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(f, text="В экспорт входят: кнопки, действия над приложениями, пульты, показатели состояния, "
                          "тексты всех скриптов из папки scripts, настройки scrcpy и программы-кнопки. "
                          "Адрес ПК, путь к Vysor и история не экспортируются.",
                  foreground=C["muted"], wraplength=760).grid(row=5, column=0, columnspan=2, sticky="w", pady=8)

    def save_settings_ui(self):
        self.S["pc_ip"] = self.set_pc_ip.get().strip()
        self.S["vysor_path"] = self.set_vysor.get().strip()
        save_settings(self.S)
        self.log("Настройки сохранены")

    def export_bundle(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="android_tv_export.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        bundle = make_bundle(self.S, SCRIPTS_DIR, load_json_folder(P("programs")))
        write_json(path, bundle)
        self.log(f"Экспортировано: {path} (скриптов: {len(bundle['scripts'])})")

    def import_bundle(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                bundle = json.load(fh)
            self.S, n, programs = apply_bundle(bundle, self.S, SCRIPTS_DIR)
        except (OSError, ValueError) as e:
            self.log(f"Не удалось импортировать: {e}")
            return
        for prog in programs:
            fn = prog.pop("file", slug(prog.get("name", "program")) + ".json")
            write_json(P("programs", fn), prog)
        save_settings(self.S)
        for bid in ("tools", "console", "scripts", "apps"):
            self.render_bar(bid)
        self.render_cards()
        self.remote_refresh_list()
        self.remote_var.set(self.S.get("remote_current", ""))
        self.remote_redraw()
        self.reload_programs_buttons()
        self.log(f"Импорт выполнен: скриптов в файле {n}")
