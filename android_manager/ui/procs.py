# -*- coding: utf-8 -*-
"""Раздел интерфейса: ProcsTab."""

import functools
import tkinter as tk
from tkinter import ttk

from ..parsing import PROC_CMD, num, parse_proc_output
from ..paths import ADB
from ..proc import run
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import tooltip_btn


class ProcsTab:
    """Mix-in для App: методы этого раздела окна."""

    def _build_procs(self, f):
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        top.add(ttk.Label(top, text="Сортировка:"))
        for label, key in [("по нагрузке CPU", "cpu"), ("по памяти", "mem"), ("по имени", "name"), ("по PID", "pid")]:
            top.add(tooltip_btn(ttk.Button(top, text=label, command=functools.partial(self.proc_sort_by, key)),
                           f"Сортировать по {label}"))
        self.proc_filter = tk.StringVar()
        self.proc_filter.trace_add("write", lambda *a: self.fill_procs())
        top.add(ttk.Entry(top, textvariable=self.proc_filter, width=22))
        top.add(ttk.Label(top, text="фильтр по имени"))
        self.auto_proc = tk.BooleanVar(value=False)
        top.add(ttk.Checkbutton(top, text="авто (каждые 3 с)", variable=self.auto_proc))
        top.add(tooltip_btn(ttk.Button(top, text="Обновить", command=self.refresh_procs),
                           "Обновить список процессов"))
        top.add(tooltip_btn(ttk.Button(top, text="Копировать выбранные", command=self.proc_copy),
                           "Скопировать выбранные процессы в буфер обмена"))
        top.add(tooltip_btn(ttk.Button(top, text="Завершить выбранный", command=self.kill_selected),
                           "Завершить выбранный процесс (kill)"))
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True, pady=6)
        self.ptree = ttk.Treeview(body, columns=("pid", "name", "mem", "cpu", "state"), show="headings",
                                  selectmode="extended")
        for col, title, width, anchor in [("pid", "PID", 70, "center"), ("name", "Название процесса", 420, "w"),
                                          ("mem", "Память, МБ", 110, "center"),
                                          ("cpu", "CPU, %", 90, "center"), ("state", "Состояние", 90, "center")]:
            self.ptree.heading(col, text=title)
            self.ptree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(body, command=self.ptree.yview)
        self.ptree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.ptree.pack(side="left", fill="both", expand=True)
        self.ptree.bind("<Button-3>", self.proc_menu)
        self.proc_count = ttk.Label(f, text="Процессы загружаются...")
        self.proc_count.pack(anchor="w")

    def proc_sort_by(self, key):
        if self.proc_sort[0] == key:
            self.proc_sort = (key, not self.proc_sort[1])
        else:
            self.proc_sort = (key, key in ("cpu", "mem"))
        self.fill_procs()

    def refresh_procs(self):
        s = self.serial.get().strip()
        if not s or self.proc_busy:
            return
        self.proc_busy = True
        self.proc_count.config(text="Процессы загружаются...")

        def job():
            _, out, _ = run([ADB, "-s", s, "shell", PROC_CMD], 90)
            return parse_proc_output(out)

        def done(res):
            self.proc_busy = False
            if isinstance(res, Exception):
                self.proc_count.config(text=f"Ошибка: {res}")
                return
            self.proc_rows = res
            self.fill_procs()

        self.bg(job, done)

    def fill_procs(self):
        q = self.proc_filter.get().strip().lower() if hasattr(self, "proc_filter") else ""
        rows = [r for r in self.proc_rows if q in r["name"].lower()]
        key, rev = self.proc_sort
        keyf = {"cpu": lambda r: r["cpu"], "mem": lambda r: r["mem"], "name": lambda r: r["name"].lower(),
                "pid": lambda r: num(r["pid"])}[key]
        rows.sort(key=keyf, reverse=rev)
        self.ptree.delete(*self.ptree.get_children())
        for r in rows[:1000]:
            self.ptree.insert("", "end", iid=r["pid"], values=(
                r["pid"], r["name"], f"{r['mem']:.1f}", f"{r['cpu']:.1f}", r["state"]))
        self.proc_count.config(text=f"Процессов: {len(self.proc_rows)} (показано {min(len(rows), 1000)})")

    def _proc_lines(self, pids):
        lines = []
        for pid in pids:
            v = self.ptree.item(pid, "values")
            if v:
                lines.append(f"{v[0]}\t{v[1]}\t{v[2]} МБ\tCPU {v[3]}%")
        return "\n".join(lines)

    def proc_copy(self):
        sel = list(self.ptree.selection())
        if not sel:
            self.log("Выберите процессы в списке")
            return
        self.copy_text(self._proc_lines(sel))

    def proc_menu(self, event):
        row = self.ptree.identify_row(event.y)
        if row and row not in self.ptree.selection():
            self.ptree.selection_set(row)
        sel = list(self.ptree.selection())
        if not sel:
            return
        items = [
            ("Копировать название", lambda: self.copy_text("\n".join(self.ptree.item(p, "values")[1] for p in sel))),
            ("Копировать PID", lambda: self.copy_text("\n".join(self.ptree.item(p, "values")[0] for p in sel))),
            ("Копировать строку", lambda: self.copy_text(self._proc_lines(sel))),
            ("Завершить процесс", self.kill_selected),
        ]
        self.popup(items, event.x_root, event.y_root)

    def kill_selected(self):
        s = self.dev()
        pids = list(self.ptree.selection())
        if not s or not pids:
            self.log("Выберите процессы в списке")
            return
        cmd = "kill -9 " + " ".join(pids)
        self.bg(lambda: run([ADB, "-s", s, "shell", cmd], 30),
                lambda res: (self.log(f"Завершено процессов: {len(pids)} ({(res[1] + res[2]).strip() or 'готово'})"),
                             self.refresh_procs()))

    def _auto_tick(self):
        try:
            if self.nb.index("current") == self.nb.index(self.tools_tab) and self.serial.get().strip():
                cur = self.sub_tools.index("current")
                if cur == 1 and self.auto_state.get():
                    self.refresh_state()
                elif cur == 2 and self.auto_proc.get():
                    self.refresh_procs()
        except tk.TclError:
            pass
        self.after(3000, self._auto_tick)

    def _set_show_touches(self, enable=True):
        """Включает/выключает 'Показывать касания' в настройках разработчика на устройстве."""
        s = self.dev()
        if not s:
            return
        val = "1" if enable else "0"
        def done(res):
            if isinstance(res, tuple):
                rc, out, err = res
                if rc == 0:
                    self.log(f"Показывать касания: {'включено' if enable else 'выключено'}")
                else:
                    self.log(f"Ошибка: {err or out}")
            else:
                self.log(f"Ошибка: {res}")
        self.bg(lambda: run([ADB, "-s", s, "shell", "settings", "put", "system", "show_touches", val], 15), done)
