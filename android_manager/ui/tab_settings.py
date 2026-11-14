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

        # --- Секция: Подключение ---
        ttk.Label(f, text="Подключение", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.set_pc_ip = tk.StringVar(value=self.S.get("pc_ip", ""))
        ttk.Label(f, text="IP этого ПК (пусто = автоопределение)").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.set_pc_ip, width=24).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Текущий адрес: " + self.pc_ip()).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 4))
        ttk.Label(f, text="Путь к Vysor").grid(row=3, column=0, sticky="w")
        self.set_vysor = tk.StringVar(value=self.S.get("vysor_path", ""))
        ttk.Entry(f, textvariable=self.set_vysor, width=60).grid(row=3, column=1, sticky="w", padx=6)

        # --- Секция: Интерфейс ---
        ttk.Label(f, text="Интерфейс", font=("Segoe UI", 10, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.set_theme = tk.StringVar(value=self.S.get("theme", "dark"))
        ttk.Label(f, text="Тема").grid(row=5, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.set_theme, values=["dark", "light", "auto"], state="readonly", width=12).grid(row=5, column=1, sticky="w", padx=6)

        self.set_font_size = tk.IntVar(value=self.S.get("font_size", 10))
        ttk.Label(f, text="Размер шрифта (8–16)").grid(row=6, column=0, sticky="w")
        ttk.Spinbox(f, textvariable=self.set_font_size, from_=8, to=16, width=6).grid(row=6, column=1, sticky="w", padx=6)

        self.set_confirm_dangerous = tk.BooleanVar(value=self.S.get("confirm_dangerous", True))
        ttk.Checkbutton(f, text="Подтверждать опасные действия (force-stop, uninstall, clear data)", variable=self.set_confirm_dangerous).grid(row=7, column=0, columnspan=2, sticky="w")

        self.set_auto_refresh = tk.IntVar(value=self.S.get("auto_refresh_packages", 30))
        ttk.Label(f, text="Автообновление списка пакетов (сек, 0 = выкл)").grid(row=8, column=0, sticky="w")
        ttk.Spinbox(f, textvariable=self.set_auto_refresh, from_=0, to=300, increment=5, width=6).grid(row=8, column=1, sticky="w", padx=6)

        # --- Секция: Консоль ---
        ttk.Label(f, text="Консоль", font=("Segoe UI", 10, "bold")).grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.set_console_history = tk.IntVar(value=self.S.get("console_history_limit", 500))
        ttk.Label(f, text="Лимит истории команд").grid(row=10, column=0, sticky="w")
        ttk.Spinbox(f, textvariable=self.set_console_history, from_=50, to=5000, increment=50, width=8).grid(row=10, column=1, sticky="w", padx=6)

        self.set_console_font = tk.IntVar(value=self.S.get("console_font_size", 10))
        ttk.Label(f, text="Шрифт консоли (8–16)").grid(row=11, column=0, sticky="w")
        ttk.Spinbox(f, textvariable=self.set_console_font, from_=8, to=16, width=6).grid(row=11, column=1, sticky="w", padx=6)

        # --- Секция: Пульт ---
        ttk.Label(f, text="Пульт", font=("Segoe UI", 10, "bold")).grid(row=12, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.set_remote_sound = tk.BooleanVar(value=self.S.get("remote_sound", True))
        ttk.Checkbutton(f, text="Звук при нажатии кнопок пульта", variable=self.set_remote_sound).grid(row=13, column=0, columnspan=2, sticky="w")

        # --- Секция: Диагностика ---
        ttk.Label(f, text="Диагностика (android_checkup)", font=("Segoe UI", 10, "bold")).grid(row=14, column=0, columnspan=2, sticky="w", pady=(12, 4))
        tooltip_btn(ttk.Button(f, text="Настроить серверы для пинга...", command=self.edit_checkup_servers),
                      "Редактировать список серверов, которые пингуются при диагностике").grid(row=15, column=0, sticky="w", pady=2)
        tooltip_btn(ttk.Button(f, text="Настроить DNS для проверки...", command=self.edit_checkup_dns),
                      "Редактировать список DNS-имён и ожидаемых IP").grid(row=15, column=1, sticky="w", padx=6, pady=2)

        # --- Кнопки действий ---
        ttk.Label(f, text="Действия", font=("Segoe UI", 10, "bold")).grid(row=16, column=0, columnspan=2, sticky="w", pady=(12, 4))
        tooltip_btn(ttk.Button(f, text="Сохранить настройки", style="Accent.TButton", command=self.save_settings_ui),
                      "Сохранить все настройки").grid(row=17, column=0, sticky="w", pady=4)
        tooltip_btn(ttk.Button(f, text="Экспорт всего в один файл...", command=self.export_bundle),
                      "Экспортировать все настройки, кнопки, скрипты, пульты в один JSON-файл").grid(row=18, column=0, sticky="w", pady=2)
        tooltip_btn(ttk.Button(f, text="Импорт из файла...", command=self.import_bundle),
                      "Импортировать настройки, кнопки, скрипты, пульты из JSON-файла").grid(row=18, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(f, text="В экспорт входят: кнопки, действия над приложениями, пульты, показатели состояния, "
                          "тексты всех скриптов из папки scripts, настройки scrcpy и программы-кнопки. "
                          "Адрес ПК, путь к Vysor и история не экспортируются.",
                  foreground=C["muted"], wraplength=760).grid(row=19, column=0, columnspan=2, sticky="w", pady=8)

    def save_settings_ui(self):
        self.S["pc_ip"] = self.set_pc_ip.get().strip()
        self.S["vysor_path"] = self.set_vysor.get().strip()
        self.S["theme"] = self.set_theme.get()
        self.S["font_size"] = self.set_font_size.get()
        self.S["confirm_dangerous"] = self.set_confirm_dangerous.get()
        self.S["auto_refresh_packages"] = self.set_auto_refresh.get()
        self.S["console_history_limit"] = self.set_console_history.get()
        self.S["console_font_size"] = self.set_console_font.get()
        self.S["remote_sound"] = self.set_remote_sound.get()
        save_settings(self.S)
        self.log("Настройки сохранены")

    def edit_checkup_servers(self):
        """Диалог редактирования списка серверов для пинга."""
        self._edit_json_list("Серверы для пинга (android_checkup)",
                             self.S.get("checkup_servers", []),
                             lambda data: self.S.update({"checkup_servers": data}),
                             [("name", "Имя"), ("ip", "IP-адрес")])

    def edit_checkup_dns(self):
        """Диалог редактирования списка DNS для проверки."""
        self._edit_json_list("DNS для проверки (android_checkup)",
                             self.S.get("checkup_dns", []),
                             lambda data: self.S.update({"checkup_dns": data}),
                             [("host", "Хост"), ("ip", "Ожидаемый IP")])

    def _edit_json_list(self, title, data, on_save, fields):
        """Универсальный диалог редактирования списка словарей."""
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=C["bg"])
        win.transient(self)
        win.grab_set()
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        tree = ttk.Treeview(frm, columns=[f[0] for f in fields], show="headings", height=10)
        for key, label in fields:
            tree.heading(key, text=label)
            tree.column(key, width=200 if key == "ip" else 300)
        tree.pack(fill="both", expand=True, pady=(0, 8))

        for item in data:
            tree.insert("", "end", values=[item.get(f[0], "") for f in fields])

        vars_dict = {f[0]: tk.StringVar() for f in fields}
        for i, (key, label) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=100+i, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=vars_dict[key], width=40).grid(row=100+i, column=1, padx=6, pady=2, sticky="w")

        def on_select(e):
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0])["values"]
                for i, key in enumerate(vars_dict):
                    vars_dict[key].set(vals[i] if i < len(vals) else "")

        tree.bind("<<TreeviewSelect>>", on_select)

        def add_item():
            vals = [vars_dict[k].get().strip() for k in vars_dict]
            if any(v for v in vals):
                tree.insert("", "end", values=vals)
                for v in vars_dict.values():
                    v.set("")

        def del_item():
            for sel in tree.selection():
                tree.delete(sel)

        def save():
            new_data = []
            for child in tree.get_children():
                vals = tree.item(child)["values"]
                new_data.append({fields[i][0]: vals[i] for i in range(len(fields))})
            on_save(new_data)
            save_settings(self.S)
            self.log(f"{title} сохранено ({len(new_data)} записей)")
            win.destroy()

        bar = ttk.Frame(frm)
        bar.grid(row=200, column=0, columnspan=2, sticky="we", pady=8)
        tooltip_btn(ttk.Button(bar, text="Добавить", command=add_item), "Добавить запись").pack(side="left")
        tooltip_btn(ttk.Button(bar, text="Удалить", command=del_item), "Удалить выбранную").pack(side="left", padx=4)
        tooltip_btn(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=save), "Сохранить и закрыть").pack(side="right")
        tooltip_btn(ttk.Button(bar, text="Отмена", command=win.destroy), "Отменить").pack(side="right", padx=4)

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