# -*- coding: utf-8 -*-
"""Раздел интерфейса: AppsTab."""

import csv
import functools
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

from ..config import C
from ..parsing import mem_from_meminfo, parse_df_mb, parse_pkgs
from ..paths import ADB, P
from ..proc import run
from ..storage import save_settings
from ..widgets.canvas import Gauge
from ..widgets.frames import ButtonPanel, FlowFrame
from ..widgets.tooltip import Tooltip, tooltip_btn


class AppsTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ вкладка «Приложения»
    def tab_apps(self, nb):
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text="Приложения")
        Tooltip(f, "Управление пакетами: список, фильтр, действия, пресеты, APK")
        gauges = FlowFrame(f, gap=10)
        gauges.pack(fill="x", pady=(0, 6))
        self.g_ram = gauges.add(Gauge(gauges, "Оперативная память (RAM)"))
        self.g_disk = gauges.add(Gauge(gauges, "Долговременная память (/data)"))
        self.g_ram.draw(0, 0)
        self.g_disk.draw(0, 0)

        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        self.filter_var = tk.StringVar(value="Все")
        top.add(ttk.Combobox(top, textvariable=self.filter_var, state="readonly", width=16,
                             values=["Все", "Пользовательские", "Системные", "Отключённые"]))
        self.filter_var.trace_add("write", lambda *a: self.fill_apps())
        top.add(tooltip_btn(ttk.Button(top, text="Обновить список", command=self.load_apps),
                           "Обновить список пакетов с устройства"))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.fill_apps())
        top.add(ttk.Entry(top, textvariable=self.search_var, width=26))
        top.add(ttk.Label(top, text="поиск по имени пакета"))
        self.ram_lbl = ttk.Label(top, text="")
        top.add(self.ram_lbl)

        body = ttk.Frame(f)
        body.pack(fill="both", expand=True, pady=4)
        side_fr = ttk.LabelFrame(body, text="Действия над выбранными приложениями",
                                 padding=8)
        side_fr.pack(side="right", fill="y", padx=(8, 0))
        self.bar_frames["apps"] = ButtonPanel(side_fr, columns=2, gap=8)
        self.bar_frames["apps"].pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, columns=("pkg", "typ", "state", "mem"), show="headings",
                                 selectmode="extended")
        for col, title, width in [("pkg", "Пакет", 420), ("typ", "Тип", 130),
                                  ("state", "Состояние", 120), ("mem", "Память, МБ", 110)]:
            self.tree.heading(col, text=title, command=lambda k=col: self.sort_by(k))
            self.tree.column(col, width=width, anchor="w" if col == "pkg" else "center")
        sb = ttk.Scrollbar(body, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Button-3>", self.app_menu)

        pres = ttk.LabelFrame(f, text="Пресеты и установка APK", padding=10)
        pres.pack(fill="x", pady=(4, 0))

        # --- строка 1: пресеты
        pres_row = ttk.Frame(pres)
        pres_row.pack(fill="x", pady=(0, 8))
        self.preset_var = tk.StringVar()
        self.preset_box = ttk.Combobox(pres_row, textvariable=self.preset_var, state="readonly", width=26)
        self.preset_box.pack(side="left", padx=(0, 6))
        tooltip_btn(ttk.Button(pres_row, text="Загрузить пресет", command=self.preset_load),
                           "Применить сохранённый набор действий к выбранным пакетам").pack(side="left", padx=(0, 6))
        tooltip_btn(ttk.Button(pres_row, text="Сохранить выбранные как пресет", command=self.preset_save),
                           "Сохранить текущий выбор пакетов как пресет для повторного использования").pack(side="left")

        # --- строка 2: установка APK
        apk_row = ttk.Frame(pres)
        apk_row.pack(fill="x", pady=(0, 8))
        ttk.Label(apk_row, text="APK из папки apk:").pack(side="left", padx=(0, 6))
        self.apk_var = tk.StringVar()
        self.apk_box = ttk.Combobox(apk_row, textvariable=self.apk_var, state="readonly", width=28)
        self.apk_box.pack(side="left", padx=(0, 6))
        tooltip_btn(ttk.Button(apk_row, text="Установить", style="Accent.TButton", command=self.install_apk),
                           "Установить выбранный APK на устройство (adb install)").pack(side="left", padx=(0, 6))
        tooltip_btn(ttk.Button(apk_row, text="Добавить APK в папку", command=self.add_apk),
                           "Выбрать APK-файл и скопировать его в папку apk программы").pack(side="left")

        # --- строка 3: экспорт
        exp_row = ttk.Frame(pres)
        exp_row.pack(fill="x")
        tooltip_btn(ttk.Button(exp_row, text="Экспорт списка (CSV)", command=self.export_csv),
                           "Экспортировать список пакетов в CSV-файл").pack(side="left")

        self.reload_presets()

    def reload_apks(self):
        files = sorted(fn for fn in os.listdir(P("apk")) if fn.lower().endswith(".apk"))
        self.apk_box["values"] = files
        if files and self.apk_var.get() not in files:
            self.apk_var.set(files[0])

    def add_apk(self):
        path = filedialog.askopenfilename(filetypes=[("APK", "*.apk")])
        if path:
            shutil.copy(path, P("apk", os.path.basename(path)))
            self.reload_apks()
            self.apk_var.set(os.path.basename(path))
            self.log(f"APK добавлен в папку apk: {os.path.basename(path)}")

    def install_apk(self):
        s = self.dev()
        name = self.apk_var.get()
        if not s or not name:
            self.log("Выберите устройство и APK")
            return
        self.log(f"Установка {name}...")
        self.bg(lambda: run([ADB, "-s", s, "install", "-r", P("apk", name)], 300),
                lambda res: (self.show_text("Установка APK", (res[1] + res[2]).strip()), self.load_apps()))

    def reload_presets(self):
        self.preset_box["values"] = list(self.S["app_presets"].keys())

    def preset_save(self):
        sel = list(self.tree.selection())
        if not sel:
            self.log("Выберите приложения в списке")
            return
        vals = self.ask_fields("Новый пресет", ["Название"])
        if not vals or not vals["Название"].strip():
            return
        self.S["app_presets"][vals["Название"].strip()] = sel
        save_settings(self.S)
        self.reload_presets()
        self.log(f"Пресет сохранён: {len(sel)} приложений")

    def preset_load(self):
        name = self.preset_var.get()
        pkgs = self.S["app_presets"].get(name)
        if not pkgs:
            self.log("Выберите пресет")
            return
        existing = [p for p in pkgs if self.tree.exists(p)]
        self.tree.selection_set(existing)
        if existing:
            self.tree.see(existing[0])
        self.log(f"Пресет «{name}»: выбрано {len(existing)} из {len(pkgs)}")

    def load_apps(self):
        s = self.dev()
        if not s:
            return

        def job():
            _, allp, _ = run([ADB, "-s", s, "shell", "pm list packages"], 60)
            _, usr, _ = run([ADB, "-s", s, "shell", "pm list packages -3"], 60)
            _, dis, _ = run([ADB, "-s", s, "shell", "pm list packages -d"], 60)
            _, ps, _ = run([ADB, "-s", s, "shell", "ps -A -o NAME,RSS"], 30)
            _, mi, _ = run([ADB, "-s", s, "shell", "cat /proc/meminfo"], 15)
            _, df, _ = run([ADB, "-s", s, "shell", "df -k /data | tail -1"], 15)
            mem = {}
            for line in ps.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[-1].isdigit():
                    name = parts[0].split(":")[0]
                    mem[name] = mem.get(name, 0) + int(parts[-1])
            return parse_pkgs(allp), set(parse_pkgs(usr)), set(parse_pkgs(dis)), mem, mi, df

        def done(res):
            if isinstance(res, Exception):
                self.log(f"Ошибка: {res}")
                return
            pkgs, usr, dis, mem, mi, df = res
            self.app_rows = []
            for p in pkgs:
                state = "отключено" if p in dis else ("запущено" if p in mem else "остановлено")
                self.app_rows.append({"pkg": p, "typ": "пользовательское" if p in usr else "системное",
                                      "state": state, "mem": mem.get(p, 0) / 1024})
            total, avail = mem_from_meminfo(mi)
            self.g_ram.draw(total - avail, total)
            disk = parse_df_mb(df)
            if disk:
                self.g_disk.draw(disk[0], disk[1])
            self.ram_lbl.config(text=f"Пакетов: {len(pkgs)}")
            self.fill_apps()
            self.log(f"Пакетов: {len(pkgs)}. Память = RSS процессов (приблизительно)")

        self.log("Загрузка списка приложений...")
        self.bg(job, done)

    def fill_apps(self):
        q = self.search_var.get().strip().lower()
        flt = self.filter_var.get()
        rows = []
        for r in self.app_rows:
            if q and q not in r["pkg"].lower():
                continue
            if flt == "Пользовательские" and r["typ"] != "пользовательское":
                continue
            if flt == "Системные" and r["typ"] != "системное":
                continue
            if flt == "Отключённые" and r["state"] != "отключено":
                continue
            rows.append(r)
        keyf = {"pkg": lambda r: r["pkg"], "typ": lambda r: r["typ"], "state": lambda r: r["state"],
                "mem": lambda r: r["mem"]}[self.sort_key]
        rows.sort(key=keyf, reverse=self.sort_rev)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=r["pkg"], values=(
                r["pkg"], r["typ"], r["state"], f"{r['mem']:.0f}" if r["mem"] else "-"))

    def sort_by(self, col):
        if self.sort_key == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key, self.sort_rev = col, (col == "mem")
        self.fill_apps()

    def app_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        items = []
        for i, it in enumerate(self.S["bars"]["apps"]):
            items.append((it["name"], functools.partial(self.apps_run, it)))
        items.append(("Копировать название пакета", self.copy_selected_pkg))
        sel = self.tree.selection()
        if len(sel) == 1:
            pkg = sel[0]
            items.append(("Добавить кнопку: " + pkg, functools.partial(self.add_launch_button, pkg)))
        self.popup(items, event.x_root, event.y_root)

    def add_launch_button(self, pkg):
        """Создаёт кнопку запуска для конкретного пакета."""
        name = f"Запуск: {pkg}"
        cmd = f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
        self.S["bars"]["apps"].append({"name": name, "cmd": cmd, "per_pkg": False})
        save_settings(self.S)
        self.render_bar("apps")
        self.log(f"Добавлена кнопка запуска для {pkg}")

    def copy_selected_pkg(self):
        sel = self.tree.selection()
        if sel:
            self.copy_text("\n".join(sel))

    def apps_run(self, item):
        """Выполняет команду-шаблон над выбранными приложениями. {pkg} заменяется на имя пакета."""
        s = self.dev()
        pkgs = list(self.tree.selection())
        if not s:
            return
        if item.get("per_pkg", True):
            if not pkgs:
                self.log("Выберите приложения в списке")
                return
            cmds = [item.get("cmd", "").replace("{pkg}", p) for p in pkgs]
        else:
            cmds = [item.get("cmd", "")]
        name = item.get("name", "Действие")
        self.log(f"{name}: {len(cmds)} шт...")

        def job():
            outs = []
            for c in cmds:
                _, o, e = run([ADB, "-s", s, "shell", c], 120)
                outs.append(f"$ {c}\n{(o + e).rstrip()}")
            return "\n\n".join(outs)

        def done(res):
            # Вывод в консоль вместо отдельного окна
            self.nb.select(self.console_tab)
            if isinstance(res, Exception):
                self.console.insert("end", f"$ {name}\nОшибка: {res}\n\n")
            else:
                self.console.insert("end", f"$ {name}\n{res}\n\n")
            self.console.see("end")
            self.load_apps()

        self.bg(job, done)

    def apps_action_edit(self, idx):
        self.log(f"apps_action_edit called with idx={idx}")
        if idx is not None:
            it = self.S["bars"]["apps"][idx]
        else:
            it = {"name": "Новое действие", "cmd": "", "per_pkg": True}
        vals = self.ask_apps_action(it)
        self.log(f"ask_apps_action returned: {vals}")
        if vals is None:
            self.log("vals is None, returning")
            return
        if vals == "delete":
            self.log("vals == delete")
            if idx is not None:
                self.bar_delete("apps", idx)
            return
        if idx is not None:
            self.S["bars"]["apps"][idx] = vals
        else:
            self.S["bars"]["apps"].append(vals)
        save_settings(self.S)
        self.render_bar("apps")
        self.log("Button saved and bar rendered")

    def ask_apps_action(self, it):
        win = tk.Toplevel(self)
        win.title("Действие над приложением")
        win.geometry("640x300")
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        nv = tk.StringVar(value=it.get("name", ""))
        pv = tk.BooleanVar(value=it.get("per_pkg", True))
        ttk.Label(frm, text="Название кнопки").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=nv, width=44).grid(row=0, column=1, sticky="we", padx=6, pady=3)
        ttk.Checkbutton(frm, text="Выполнять для каждого выбранного приложения ({pkg} = имя пакета)",
                        variable=pv).grid(row=1, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Label(frm, text="Команда shell").grid(row=2, column=0, sticky="nw")
        txt = scrolledtext.ScrolledText(frm, height=5, bg=C["term"], fg=C["text"], font=("Consolas", 10),
                                        relief="flat", insertbackground=C["text"])
        txt.grid(row=2, column=1, sticky="we", padx=6, pady=3)
        txt.insert("1.0", it.get("cmd", ""))
        frm.grid_columnconfigure(1, weight=1)
        result = {}

        def ok():
            result["v"] = {"name": nv.get().strip() or "Действие", "cmd": txt.get("1.0", "end").strip(),
                           "per_pkg": pv.get()}
            win.destroy()

        def delete():
            result["v"] = "delete"
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=3, column=0, columnspan=2, sticky="we", pady=(8, 0))
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

    def export_csv(self):
        rows = [self.tree.item(i, "values") for i in self.tree.get_children()]
        if not rows:
            self.log("Список пуст")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="apps.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Пакет", "Тип", "Состояние", "Память, МБ"])
            w.writerows(rows)
        self.log(f"Экспортировано строк: {len(rows)}")
