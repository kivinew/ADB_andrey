# -*- coding: utf-8 -*-
"""Раздел интерфейса: ScriptsTab."""

import datetime
import json
import os
import re
import sys
import time
import traceback
from tkinter import ttk, filedialog, scrolledtext

from ..config import C
from ..parsing import detect_pc_ip
from ..paths import P, SCRIPTS_DIR
from ..scriptapi import AdbModule, ScriptAPI, ScriptStop
from ..storage import import_script_file, save_settings
from ..util import read_text
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import Tooltip, tooltip_btn


class ScriptsTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ вкладка «Скрипты» (Python)
    def tab_scripts(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="Скрипты")
        Tooltip(f, "Запуск Python-скриптов, результат в окне, остановка")
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        top.add(tooltip_btn(ttk.Button(top, text="■ Остановить", command=self.stop_script),
                           "Остановить выполняющийся скрипт"))
        top.add(tooltip_btn(ttk.Button(top, text="Открыть папку скриптов", command=self.open_scripts_folder),
                           "Открыть папку scripts в проводнике"))
        top.add(ttk.Label(top, text="«+ Добавить скрипт» спрашивает путь к .py; копия сохраняется в папку scripts. "
                                    "ЛКМ - запустить, ПКМ - изменить / удалить / двигать."))
        bars = ttk.LabelFrame(f, text="Мои скрипты", padding=8)
        bars.pack(fill="x", pady=8)
        self.bar_frames["scripts"] = FlowFrame(bars, gap=6)
        self.bar_frames["scripts"].pack(fill="x")
        outf = ttk.LabelFrame(f, text="Результат скрипта", padding=6)
        outf.pack(fill="both", expand=True)
        rb = FlowFrame(outf, gap=6)
        rb.pack(fill="x", pady=(0, 4))
        rb.add(tooltip_btn(ttk.Button(rb, text="Копировать результат",
                          command=lambda: self.copy_text(self.script_out.get("1.0", "end").rstrip())),
                           "Скопировать весь результат скрипта в буфер обмена"))
        rb.add(tooltip_btn(ttk.Button(rb, text="Очистить результат", command=lambda: self.script_out.delete("1.0", "end")),
                           "Очистить окно результата"))
        self.script_out = scrolledtext.ScrolledText(outf, height=10, bg=C["term"], fg=C["ok"],
                                                    font=("Consolas", 10), relief="flat", wrap="word")
        self.script_out.pack(fill="both", expand=True)

    def open_scripts_folder(self):
        if os.name == "nt":
            os.startfile(SCRIPTS_DIR)

    def add_script_file(self):
        path = filedialog.askopenfilename(title="Выберите скрипт Python",
                                          filetypes=[("Python", "*.py"), ("Все файлы", "*.*")])
        if not path:
            return
        vals = self.ask_fields("Название кнопки", ["Название кнопки"],
                               defaults={"Название кнопки": os.path.splitext(os.path.basename(path))[0]})
        if not vals or not vals["Название кнопки"].strip():
            return
        name = vals["Название кнопки"].strip()
        fn = import_script_file(SCRIPTS_DIR, path, name)
        self.S["bars"].setdefault("scripts", []).append({"name": name, "kind": "script", "file": fn})
        save_settings(self.S)
        self.render_bar("scripts")
        self.log(f"Скрипт сохранён в папку scripts: {fn}")

    def script_edit(self, idx):
        it = self.S["bars"]["scripts"][idx]
        path = P("scripts", it.get("file", ""))
        text = read_text(path) if os.path.isfile(path) else ""
        vals = self.ask_multiline(
            "Скрипт", it.get("name", ""), text,
            hint=f"Файл: scripts\\{it.get('file', '')}. Команды на устройство: adb.shell(\"...\"), вывод: print(...). "
                 "Изменения сохраняются в файл.",
            can_delete=True)
        if vals is None:
            return
        if vals == "delete":
            self.bar_delete("scripts", idx)
            return
        name, code = vals
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code + "\n")
        self.S["bars"]["scripts"][idx]["name"] = name or it.get("name", "Скрипт")
        save_settings(self.S)
        self.render_bar("scripts")

    def stop_script(self):
        if self.script_running:
            self.stop_ev.set()
            self.log("Остановка скрипта...")
        else:
            self.log("Скрипт не выполняется")

    def _script_hint(self, text):
        """Пишет пояснение и в окно результата, и в журнал: иначе причина не видна."""
        self.script_out.insert("end", text + "\n")
        self.script_out.see("end")
        self.log(text)

    def run_script(self, item):
        name = item.get("name", "Скрипт")
        if self.script_running:
            self._script_hint("Скрипт уже выполняется. Дождитесь окончания или нажмите «Остановить»")
            return
        s = self.serial.get().strip()
        if not s:
            self._script_hint("Сначала подключите устройство: скрипты работают с выбранным устройством")
            return
        path = P("scripts", item.get("file", ""))
        if not os.path.isfile(path):
            self._script_hint(f"Файл скрипта не найден: {path}")
            return
        code = read_text(path)
        self.stop_ev.clear()
        self.script_running = True
        self.script_buf = []
        self.script_out.delete("1.0", "end")
        self.script_out.insert("end", f"▶ {name}  ({datetime.datetime.now():%H:%M:%S})\n")
        api = ScriptAPI(s, self.pc_ip(), self.stop_ev)
        q = self.script_q

        def script_print(*args, sep=" ", end="\n", **kwargs):
            q.put(sep.join(str(a) for a in args) + end)

        # Создаём модуль adb: все методы ScriptAPI доступны и как adb.<метод>, и через import adb
        adb_module = AdbModule(api)
        # Кладем в namespace и sys.modules, чтобы import adb работал
        namespace = {"adb": adb_module, "print": script_print, "sleep": api.sleep,
                     "time": time, "json": json, "re": re, "os": os}
        prev_adb = sys.modules.get("adb")
        sys.modules["adb"] = adb_module

        def job():
            import sys
            scripts_dir = os.path.dirname(path)
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            try:
                exec(compile(code, path, "exec"), namespace)  # noqa: S102 - скрипт пишет пользователь
                return "ok", ""
            except ScriptStop:
                return "stopped", ""
            except Exception:  # noqa: BLE001
                return "error", traceback.format_exc()

        def done(res):
            # возвращаем прежний adb: следующий запуск не должен наследовать этот API
            if prev_adb is None:
                sys.modules.pop("adb", None)
            else:
                sys.modules["adb"] = prev_adb
            self._drain_script()
            self.script_running = False
            status, tb = res if isinstance(res, tuple) else ("error", str(res))
            label = {"ok": "готово", "stopped": "остановлено", "error": "ошибка"}[status]
            if tb:
                self.script_out.insert("end", "\n" + tb)
            self.script_out.insert("end", f"\n■ {label}\n")
            self.script_out.see("end")
            if not "".join(self.script_buf).strip() and not tb:
                self.script_out.insert("end", "(скрипт не выводил текст)\n")
                self.script_out.see("end")
            self.log(f"Скрипт «{name}»: {label}")

        self.log(f"Запуск скрипта «{name}»")
        self.bg(job, done)

    def pc_ip(self):
        return self.S.get("pc_ip") or detect_pc_ip()
