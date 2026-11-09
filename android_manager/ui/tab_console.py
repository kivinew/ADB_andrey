# -*- coding: utf-8 -*-
"""Раздел интерфейса: ConsoleTab."""

import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from ..config import C
from ..paths import ADB
from ..proc import run
from ..scriptapi import ScriptAPI
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import Tooltip, tooltip_btn
from installer.config import NO_WIN


BUILTIN_CMDS = ["getprop", "setprop", "pm", "am", "settings", "input", "dumpsys", "logcat", "dmesg",
                "ps", "top", "cat", "ls", "cd", "grep", "head", "tail", "df", "du", "free", "uptime",
                "reboot", "ip", "ifconfig", "netstat", "wm", "cmd", "monkey", "screencap", "svc", "sh",
                "echo", "mount", "chmod", "rm", "mkdir", "cp", "mv", "id", "whoami", "uname", "date",
                "sleep", "kill", "pkill", "tr", "cut", "sort", "uniq", "wc", "which", "find", "stat",
                "ping", "vmstat", "clear", "awk", "sed"]
SUBCMDS = {
    "pm": ["list", "path", "clear", "uninstall", "disable-user", "enable", "trim-caches", "install",
           "grant", "revoke", "dump"],
    "am": ["start", "force-stop", "broadcast", "startservice", "kill"],
    "settings": ["get", "put", "list", "delete"],
    "input": ["keyevent", "tap", "swipe", "text"],
    "dumpsys": ["meminfo", "package", "activity", "cpuinfo", "battery", "wifi", "SurfaceFlinger", "window"],
    "wm": ["size", "density", "reset"],
    "logcat": ["-d", "-c", "-b", "-v", "-s", "-t"],
}
PKG_CMDS = ("pm", "am", "monkey")
PKG_SUBS = ("clear", "uninstall", "disable-user", "enable", "path", "force-stop", "start", "-p")


class ConsoleTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ вкладка «Консоль»
    def tab_console(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="Консоль")
        Tooltip(f, "ADB shell с подсказками, автодополнением команд и историей")
        self.console_tab = f
        self.console = scrolledtext.ScrolledText(f, bg=C["term"], fg=C["ok"], font=("Consolas", 10),
                                                 relief="flat", wrap="word", insertbackground=C["text"])
        self.console.pack(fill="both", expand=True)
        quick = ttk.LabelFrame(f, text="Мои команды (ЛКМ - выполнить, ПКМ - изменить / удалить / двигать)", padding=6)
        quick.pack(fill="x", pady=(4, 0))
        self.bar_frames["console"] = FlowFrame(quick, gap=6)
        self.bar_frames["console"].pack(fill="x")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="$").pack(side="left")
        self.cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(row, textvariable=self.cmd_var, font=("Consolas", 10))
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=4)
        tooltip_btn(ttk.Button(row, text="Выполнить", style="Accent.TButton", command=self.shell_run),
                           "Выполнить команду из поля ввода на подключённом устройстве").pack(side="left")
        tooltip_btn(ttk.Button(row, text="Очистить", command=lambda: self.console.delete("1.0", "end")),
                           "Очистить вывод консоли").pack(side="left", padx=4)
        tooltip_btn(ttk.Button(row, text="Открыть окно", command=self.open_console_window),
                           "Открыть системную консоль (cmd.exe) с интерактивным adb shell").pack(side="left", padx=4)
        tooltip_btn(ttk.Button(row, text="Kill PID", command=self.kill_clipboard_pid),
                           "Убить процесс с PID из буфера обмена на устройстве").pack(side="left", padx=4)
        self.sug = tk.Listbox(f, height=8, bg=C["panel"], fg=C["text"], font=("Consolas", 10),
                              selectbackground=C["sel"], relief="flat", activestyle="none")
        e = self.cmd_entry
        e.bind("<Return>", self._console_enter)
        e.bind("<Tab>", self._console_tab)
        e.bind("<Up>", lambda ev: self._console_move(-1))
        e.bind("<Down>", lambda ev: self._console_move(1))
        e.bind("<Escape>", lambda ev: self._sug_hide())
        e.bind("<KeyRelease>", self._console_typed)
        self.sug.bind("<Double-Button-1>", lambda ev: self._sug_accept())

    def console_exec(self, cmd):
        self.cmd_var.set(cmd)
        self.shell_run()

    def kill_clipboard_pid(self):
        """Убивает процесс с PID из буфера обмена на подключённом устройстве."""
        s = self.dev()
        if not s:
            return
        try:
            pid = self.clipboard_get().strip()
        except tk.TclError:
            self.log("Буфер обмена пуст")
            return
        if not pid.isdigit():
            self.log("В буфере обмена не число (PID)")
            return
        self.log(f"Kill PID {pid} на {s}...")
        self.console.insert("end", f"$ kill -9 {pid}\n")
        self.console.see("end")
        api = ScriptAPI(s, "", threading.Event())
        def done(res):
            text = res if isinstance(res, str) else f"Ошибка: {res}"
            if text.strip():
                self.console.insert("end", text.rstrip() + "\n")
            self.console.see("end")
        self.bg(lambda: api.shell(f"kill -9 {pid}", timeout=10), done)

    def open_console_window(self):
        """Открывает системную консоль с интерактивным adb shell на устройстве."""
        s = self.serial.get().strip()
        if not s:
            self.log("Сначала подключите устройство")
            return
        # Запускаем adb shell напрямую в новом окне консоли
        # Это даст настоящий интерактивный shell на Android устройстве
        try:
            subprocess.Popen(
                [ADB, "-s", s, "shell"],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.log("Открыт adb shell для {}".format(s))
        except Exception as e:
            self.log("Ошибка запуска adb shell: {}".format(e))

    def candidates(self, text):
        parts = text.split(" ")
        cur = parts[-1]
        if len(parts) == 1:
            pool = set(BUILTIN_CMDS) | set(self.cache["bins"])
            return cur, sorted(c for c in pool if c.startswith(cur))[:60]
        cmd = parts[0]
        prev = parts[-2]
        if "/" in cur:
            d, _, base = cur.rpartition("/")
            directory = d if d else "/"
            prefix = cur[:len(cur) - len(base)]
            listing = self.cache["dirs"].get(directory)
            if listing is None:
                self._fetch_dir(directory)
                return cur, []
            return cur, [prefix + n for n in listing if n.startswith(base)][:60]
        if cmd == "pm" and len(parts) == 3 and parts[1] == "list":
            return cur, [x for x in ["packages"] if x.startswith(cur)]
        if cmd in PKG_CMDS and (prev in PKG_SUBS or len(parts) >= 3) and not cur.startswith("-"):
            return cur, [p for p in self.cache["pkgs"] if p.startswith(cur)][:60]
        if cmd == "getprop" and len(parts) >= 2:
            return cur, [p for p in self.cache["props"] if p.startswith(cur)][:60]
        if cmd in SUBCMDS and len(parts) == 2:
            return cur, [s for s in SUBCMDS[cmd] if s.startswith(cur)]
        if prev == "-p":
            return cur, [p for p in self.cache["pkgs"] if p.startswith(cur)][:60]
        return cur, []

    def _fetch_dir(self, directory):
        s = self.serial.get().strip()
        if not s or directory in self.cache["pending"]:
            return
        self.cache["pending"].add(directory)

        def job():
            _, o, _ = run([ADB, "-s", s, "shell", f'ls -p "{directory}" 2>/dev/null'], 20)
            return sorted(x.strip() for x in o.splitlines() if x.strip())

        def done(res):
            self.cache["pending"].discard(directory)
            if isinstance(res, list):
                self.cache["dirs"][directory] = res
                if self.focus_get() is self.cmd_entry:
                    self._console_typed(None)

        self.bg(job, done)

    def _console_typed(self, ev):
        if ev is not None and ev.keysym in ("Up", "Down", "Return", "Tab", "Escape", "Shift_L", "Shift_R",
                                            "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        _, items = self.candidates(self.cmd_var.get())
        if not items:
            self._sug_hide()
            return
        self.sug.delete(0, "end")
        for it in items:
            self.sug.insert("end", it)
        self.sug.configure(height=min(len(items), 8))
        if not self.sug_visible:
            self.sug.pack(fill="x", pady=(2, 0), after=self.cmd_entry.master)
            self.sug_visible = True

    def _sug_hide(self):
        if self.sug_visible:
            self.sug.pack_forget()
            self.sug_visible = False

    def _replace_last(self, cand):
        text = self.cmd_var.get()
        cur = text.split(" ")[-1]
        new = text[:len(text) - len(cur)] + cand
        if not cand.endswith("/"):
            new += " "
        self.cmd_var.set(new)
        self.cmd_entry.icursor("end")

    def _sug_accept(self):
        sel = self.sug.curselection()
        if not sel:
            return False
        self._replace_last(self.sug.get(sel[0]))
        self._sug_hide()
        self._console_typed(None)
        return True

    def _console_tab(self, ev):
        """Tab дописывает команду: выбранную подсказку, единственную подсказку или общее начало."""
        if self.sug_visible and self.sug.curselection():
            self._sug_accept()
            return "break"
        _, items = self.candidates(self.cmd_var.get())
        if not items:
            return "break"
        if len(items) == 1:
            self._replace_last(items[0])
            self._sug_hide()
            self._console_typed(None)
            return "break"
        common = os.path.commonprefix(items)
        cur = self.cmd_var.get().split(" ")[-1]
        if len(common) > len(cur):
            self._replace_last(common)
            self.cmd_var.set(self.cmd_var.get().rstrip(" "))
        self._console_typed(None)
        return "break"

    def _console_move(self, d):
        if self.sug_visible:
            size = self.sug.size()
            cur = self.sug.curselection()
            idx = (cur[0] + d) if cur else (0 if d > 0 else size - 1)
            idx = min(max(idx, 0), size - 1)
            self.sug.selection_clear(0, "end")
            self.sug.selection_set(idx)
            self.sug.see(idx)
            return "break"
        if not self.hist_list:
            return "break"
        self.hist_i = min(max(self.hist_i + d, 0), len(self.hist_list))
        self.cmd_var.set(self.hist_list[self.hist_i] if self.hist_i < len(self.hist_list) else "")
        self.cmd_entry.icursor("end")
        return "break"

    def _console_enter(self, ev):
        if self.sug_visible and self.sug.curselection():
            self._sug_accept()
            return "break"
        self._sug_hide()
        self.shell_run()
        return "break"

    def shell_run(self):
        cmd = self.cmd_var.get().strip()
        s = self.dev()
        if not cmd or not s:
            return
        if cmd == "clear":
            self.console.delete("1.0", "end")
            self.cmd_var.set("")
            return
        # Команды с непрерывным выводом (стриминг)
        streaming_cmds = ("dmesg -w", "top", "watch ", "ping ", "tail -f")
        is_streaming = any(cmd.startswith(sc) for sc in streaming_cmds)
        # logcat: стриминг только если НЕТ флагов завершения (-d, -c, -t)
        if cmd.startswith("logcat"):
            parts = cmd.split()
            has_finish_flag = any(p in ("-d", "-c", "-t", "--dump", "--clear") for p in parts)
            if not has_finish_flag:
                is_streaming = True
        self.hist_list.append(cmd)
        self.hist_i = len(self.hist_list)
        self.cmd_var.set("")
        self.console.insert("end", f"$ {cmd}\n")
        self.console.see("end")

        if is_streaming:
            self._start_streaming(cmd, s)
        else:
            # logcat -c / -d / -t: запускать напрямую через adb logcat (не shell)
            if cmd.startswith("logcat") and any(p in ("-c", "-d", "-t", "--clear", "--dump") for p in cmd.split()):
                self._run_direct_logcat(cmd, s)
            else:
                api = ScriptAPI(s, "", threading.Event())

                def done(res):
                    text = res if isinstance(res, str) else f"Ошибка: {res}"
                    if text.strip():
                        self.console.insert("end", text.rstrip() + "\n")
                    self.console.see("end")

                self.bg(lambda: api.shell(cmd, timeout=120), done)

    def _run_direct_logcat(self, cmd, serial):
        """Запускает logcat -c/-d/-t напрямую через adb logcat (быстро, без shell)."""
        def done(res):
            # run() возвращает (rc, out, err)
            if isinstance(res, tuple) and len(res) == 3:
                rc, out, err = res
                text = (out + err).strip()
                if rc != 0 and text:
                    text = f"Ошибка (код {rc}): {text}"
            elif isinstance(res, str):
                text = res
            else:
                text = f"Ошибка: {res}"
            if text.strip():
                self.console.insert("end", text.rstrip() + "\n")
            self.console.see("end")

        self.bg(lambda: run([ADB, "-s", serial] + cmd.split(), 30), done)

    def _start_streaming(self, cmd, serial):
        """Запускает команду с непрерывным выводом (logcat, dmesg -w, top и т.д.)."""
        # Останавливаем предыдущую стриминговую сессию, если есть
        if getattr(self, '_stream_polling', False):
            self._stop_current_streaming()

        self.stream_proc = None
        self.stream_stop = threading.Event()
        self._stream_queue = queue.Queue()

        # Если в команде есть shell-операторы (|, >, >>, &&, ||, ;), запускаем через shell
        shell_ops = ("|", ">", ">>", "&&", "||", ";")
        use_shell = any(op in cmd for op in shell_ops)

        # Для logcat используем прямой adb logcat (без shell) — стримит сразу
        # НО если есть pipe/операторы — нужно через shell
        if cmd.startswith("logcat") and not use_shell:
            adb_cmd = [ADB, "-s", serial, "logcat"]
        else:
            adb_cmd = [ADB, "-s", serial, "shell", cmd]

        def reader():
            try:
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                self.stream_proc = subprocess.Popen(
                    adb_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,  # unbuffered
                    universal_newlines=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=NO_WIN,
                    env=env
                )
                # Читаем по символам для мгновенного вывода
                while True:
                    if self.stream_stop.is_set():
                        break
                    chunk = self.stream_proc.stdout.read(4096)
                    if not chunk:
                        break
                    # Разбиваем на строки
                    lines = chunk.splitlines(True)
                    for line in lines:
                        if line.endswith("\n"):
                            self._stream_queue.put(line.rstrip("\n"))
                        else:
                            # Неполная строка - накопить или выводить как есть
                            self._stream_queue.put(line.rstrip("\n"))
                rc = self.stream_proc.wait()
                if not self.stream_stop.is_set():
                    self._stream_queue.put(("__END__", f"[завершено с кодом {rc}]"))
            except Exception as e:
                self._stream_queue.put(("__END__", f"[ошибка: {e}]"))

        def stop_streaming():
            if self.stream_proc and self.stream_proc.poll() is None:
                self.stream_stop.set()
                try:
                    self.stream_proc.terminate()
                except Exception:
                    pass
                self._stream_queue.put(("__END__", "[остановлено пользователем]"))

        def on_stream_end(msg):
            self._append_console(msg)
            self._remove_stream_stop_btn()
            self._stream_polling = False

        self._on_stream_end = on_stream_end
        self._remove_stream_stop_btn = lambda: (
            self._stream_stop_btn.pack_forget() if hasattr(self, '_stream_stop_btn') else None
        )

        # Кнопка остановки
        self._stream_stop_btn = tooltip_btn(ttk.Button(
            self.cmd_entry.master, text="■ Стоп",
            command=stop_streaming, style="Accent.TButton"
        ), "Остановить стриминг (logcat, top, dmesg -w и т.д.)")
        self._stream_stop_btn.pack(side="left", padx=4)

        # Запускаем ридер и поллер очереди
        threading.Thread(target=reader, daemon=True).start()
        self._stream_polling = True
        self._poll_stream_queue()

    def _stop_current_streaming(self):
        """Останавливает текущую стриминговую сессию и убирает кнопку."""
        if hasattr(self, 'stream_stop'):
            self.stream_stop.set()
        if hasattr(self, 'stream_proc') and self.stream_proc and self.stream_proc.poll() is None:
            try:
                self.stream_proc.terminate()
            except Exception:
                pass
        if hasattr(self, '_stream_stop_btn'):
            try:
                self._stream_stop_btn.pack_forget()
            except Exception:
                pass
        self._stream_polling = False

    def _poll_stream_queue(self):
        """Периодически забирает строки из очереди и пишет в консоль."""
        if not getattr(self, '_stream_polling', False):
            return
        try:
            while True:
                item = self._stream_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__END__":
                    self._on_stream_end(item[1])
                    return
                self._append_console(item)
        except queue.Empty:
            pass
        if self._stream_polling:
            self.after(50, self._poll_stream_queue)

    def _append_console(self, text):
        self.console.insert("end", text + "\n")
        self.console.see("end")
