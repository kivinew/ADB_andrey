# -*- coding: utf-8 -*-
"""Раздел интерфейса: ActionsTab."""

import datetime
import functools
import os
import shlex
import shutil
import subprocess
import threading
from tkinter import ttk, filedialog

from ..parsing import split_target
from ..paths import ADB, P, SCRCPY
from ..proc import run
from ..scriptapi import ScriptAPI
from ..storage import load_json_folder, save_settings, write_json
from ..util import slug
from ..widgets.tooltip import tooltip_btn
from installer.config import NO_WIN


class ActionsTab:
    """Mix-in для App: методы этого раздела окна."""

    def scrcpy_start(self):
        s = self.dev()
        if not s:
            return
        self.S["scrcpy"].update({"max_size": self.sc_max.get().strip(), "fps": self.sc_fps.get().strip(),
                                 "bitrate": self.sc_br.get().strip(), "codec": self.sc_codec.get(),
                                 "show_touches": self.sc_touch.get(), "stay_awake": self.sc_awake.get(),
                                 "screen_off": self.sc_off.get()})
        save_settings(self.S)
        args = [SCRCPY, "-s", s, "--video-codec", self.sc_codec.get()]
        if self.sc_max.get().strip().isdigit() and int(self.sc_max.get()) > 0:
            args += ["--max-size", self.sc_max.get().strip()]
        if self.sc_fps.get().strip().isdigit():
            args += ["--max-fps", self.sc_fps.get().strip()]
        if self.sc_br.get().strip():
            args += ["--video-bit-rate", self.sc_br.get().strip()]
        if self.sc_touch.get():
            args.append("--show-touches")
        if self.sc_awake.get():
            args.append("--stay-awake")
        if self.sc_off.get():
            args.append("--turn-screen-off")
        env = os.environ.copy()
        env["ADB"] = ADB

        try:
            subprocess.Popen(args, env=env, creationflags=NO_WIN)
            self.log("scrcpy запущен")
        except FileNotFoundError:
            self.log(f"scrcpy не найден: {SCRCPY}. Переустановите программу через установщик")

    def vysor_start(self):
        path = self.S.get("vysor_path", "")
        if not path or not os.path.isfile(path):
            path = filedialog.askopenfilename(title="Укажите Vysor (exe)", filetypes=[("Программа", "*.exe")])
            if not path:
                return
            self.S["vysor_path"] = path
            save_settings(self.S)

        try:
            subprocess.Popen([path], creationflags=NO_WIN)
            self.log("Vysor запущен")
        except OSError as e:
            self.log(f"Не удалось запустить Vysor: {e}")

    def reload_programs_buttons(self):
        for w in self.prog_frame.winfo_children():
            w.destroy()
        for prog in load_json_folder(P("programs")):
            tooltip_btn(ttk.Button(self.prog_frame, text=prog.get("name", prog["file"]),
                       command=functools.partial(self.program_run, prog)),
                           f"Запустить программу: {prog.get('name', prog['file'])}").pack(fill="x", pady=1)

    def add_program(self):
        path = filedialog.askopenfilename(title="Программа", filetypes=[("Программа", "*.exe")])
        if not path:
            return
        vals = self.ask_fields("Добавить программу", ["Название кнопки", "Аргументы ({serial} {ip} {port})"],
                               defaults={"Название кнопки": os.path.splitext(os.path.basename(path))[0]})
        if not vals:
            return
        fn = os.path.basename(path)
        shutil.copy(path, P("programs", fn))
        write_json(P("programs", slug(vals["Название кнопки"]) + ".json"),
                   {"name": vals["Название кнопки"], "file": fn, "args": vals["Аргументы ({serial} {ip} {port})"]})
        self.reload_programs_buttons()
        self.log(f"Программа добавлена: {vals['Название кнопки']}")

    def program_run(self, prog):
        s = self.serial.get().strip()
        ip, port = split_target(s, "5555") if s else ("", "5555")
        args = prog.get("args", "")
        for k, v in {"serial": s, "ip": ip, "port": port}.items():
            args = args.replace("{" + k + "}", v)
        try:
            subprocess.Popen([P("programs", prog["file"])] + shlex.split(args))
            self.log(f"Запущено: {prog.get('name', prog['file'])}")
        except OSError as e:
            self.log(f"Не удалось запустить: {e}")

    def screenshot(self):
        s = self.dev()
        if not s:
            return
        path = P("screenshots", datetime.datetime.now().strftime("screen_%Y%m%d_%H%M%S.png"))
        api = ScriptAPI(s, "", threading.Event())
        self.bg(lambda: api.screenshot(path),
                lambda res: self.log(f"Скриншот: {res}" if isinstance(res, str) else f"Ошибка: {res}"))

    def reboot(self, mode):
        s = self.dev()
        if not s:
            return
        api = ScriptAPI(s, "", threading.Event())
        self.bg(lambda: api.reboot(mode), lambda res: self.log(
            f"Команда отправлена: reboot {mode}".strip() if not isinstance(res, Exception) else f"Ошибка: {res}"))

    def key(self, code):
        s = self.dev()
        if not s:
            return
        def done(res):
            if isinstance(res, tuple) and len(res) == 3:
                rc, out, err = res
                if rc != 0:
                    self.log(f"Ошибка клавиши {code}: {err or out}")
            elif isinstance(res, Exception):
                self.log(f"Ошибка клавиши {code}: {res}")
        self.bg(lambda: run([ADB, "-s", s, "shell", "input", "keyevent", str(code)], 15), done)
