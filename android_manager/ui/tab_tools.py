# -*- coding: utf-8 -*-
"""Раздел интерфейса: ToolsTab."""

import json
import tkinter as tk
from tkinter import ttk

from ..config import C, KEY_COL
from ..proc import run
from ..storage import save_settings
from ..util import remote_window_rect, unique_name
from ..widgets.frames import FlowFrame, ScrollFrame
from ..widgets.remote import RemoteWindow
from ..widgets.tooltip import Tooltip, tooltip_btn


class ToolsTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ вкладка «Инструменты»
    def tab_tools(self, nb):
        f = ttk.Frame(nb, padding=4)
        nb.add(f, text="Инструменты")
        Tooltip(f, "Пульт управления, состояние (RAM/CPU/GPU/температура), инструменты")
        self.tools_tab = f
        sub = ttk.Notebook(f)
        sub.pack(fill="both", expand=True)
        self.sub_tools = sub
        ctrl_sf = ScrollFrame(sub)
        state_sf = ScrollFrame(sub)
        procs = ttk.Frame(sub, padding=6)
        sub.add(ctrl_sf, text="Управление")
        sub.add(state_sf, text="Состояние")
        sub.add(procs, text="Процессы")
        sub.bind("<<NotebookTabChanged>>", lambda e: self.on_sub_tab())
        self._build_control(ctrl_sf.inner)
        self._build_state(state_sf.inner)
        self._build_procs(procs)

    def _build_control(self, f):
        grid = FlowFrame(f, gap=10)
        grid.pack(fill="x", padx=4, pady=4)

        sc = ttk.LabelFrame(grid, text="Зеркало экрана (scrcpy)", padding=8)
        grid.add(sc)
        cfg = self.S["scrcpy"]
        self.sc_max = tk.StringVar(value=cfg["max_size"])
        self.sc_fps = tk.StringVar(value=cfg["fps"])
        self.sc_br = tk.StringVar(value=cfg["bitrate"])
        self.sc_codec = tk.StringVar(value=cfg["codec"])
        self.sc_touch = tk.BooleanVar(value=cfg["show_touches"])
        self.sc_awake = tk.BooleanVar(value=cfg["stay_awake"])
        self.sc_off = tk.BooleanVar(value=cfg["screen_off"])
        rows = [("Макс. размер (0 = без лимита)", ttk.Entry(sc, textvariable=self.sc_max, width=10)),
                ("FPS", ttk.Entry(sc, textvariable=self.sc_fps, width=10)),
                ("Битрейт (8M, 16M...)", ttk.Entry(sc, textvariable=self.sc_br, width=10)),
                ("Кодек", ttk.Combobox(sc, textvariable=self.sc_codec, values=["h264", "h265", "av1"],
                                       state="readonly", width=8))]
        for i, (label, w) in enumerate(rows):
            ttk.Label(sc, text=label).grid(row=i, column=0, sticky="w", pady=2)
            w.grid(row=i, column=1, padx=6, pady=2, sticky="w")
        row_touch = ttk.Frame(sc)
        row_touch.grid(row=4, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Checkbutton(row_touch, text="Показывать касания", variable=self.sc_touch).pack(side="left")
        tooltip_btn(ttk.Button(row_touch, text="Вкл. на устройстве", width=15,
                   command=lambda: self._set_show_touches(True)),
                   "Включить «Показывать касания» в настройках разработчика на устройстве").pack(side="left", padx=4)
        ttk.Checkbutton(sc, text="Выключить экран устройства", variable=self.sc_off).grid(row=5, column=0, columnspan=2, sticky="w")
        tooltip_btn(ttk.Button(sc, text="Запустить scrcpy", style="Accent.TButton", command=self.scrcpy_start),
                           "Запустить scrcpy — зеркалирование экрана устройства на ПК").grid(
            row=7, column=0, columnspan=2, sticky="we", pady=(8, 0))

        ext = ttk.LabelFrame(grid, text="Внешние программы и пульт", padding=8)
        grid.add(ext)
        tooltip_btn(ttk.Button(ext, text="Vysor", command=self.vysor_start),
                           "Запустить Vysor (альтернативное зеркалирование экрана)").pack(fill="x", pady=2)
        tooltip_btn(ttk.Button(ext, text="Открыть пульт", style="Accent.TButton", command=self.open_remote),
                           "Открыть окно пульта управления с настраиваемыми кнопками").pack(fill="x", pady=2)
        self.prog_frame = ttk.Frame(ext)
        self.prog_frame.pack(fill="x")
        tooltip_btn(ttk.Button(ext, text="Добавить программу...", command=self.add_program),
                           "Добавить внешнюю программу в меню быстрого запуска").pack(fill="x", pady=(6, 0))

        ctl = ttk.LabelFrame(grid, text="Управление", padding=8)
        grid.add(ctl)
        tooltip_btn(ttk.Button(ctl, text="Скриншот", command=self.screenshot),
                           "Сделать скриншот экрана устройства (adb shell screencap)").pack(fill="x", pady=2)
        tooltip_btn(ttk.Button(ctl, text="Перезагрузка", command=lambda: self.reboot("")),
                           "Перезагрузить устройство (adb reboot)").pack(fill="x", pady=2)
        btns = ttk.LabelFrame(f, text="Мои кнопки управления (ЛКМ - выполнить, ПКМ - изменить / удалить / двигать)",
                              padding=8)
        btns.pack(fill="x", padx=4, pady=6)
        self.bar_frames["tools"] = FlowFrame(btns, gap=6)
        self.bar_frames["tools"].pack(fill="x")

    # --- пульт (окно)
    def open_remote(self):
        """Открывает окно пульта у левого края экрана. Рядом с scrcpy и Vysor не привязывается."""
        if self.remote_win is None or not self.remote_win.winfo_exists():
            self.remote_win = RemoteWindow(self)
            self.remote_place(None)
        self.remote_win.deiconify()
        self.remote_win.lift()
        self.remote_refresh_list()
        self.remote_redraw()

    def remote_place(self, rect):
        if self.remote_win is None:
            return
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y, w, h = remote_window_rect(rect, sw, sh)
        self.remote_win.geometry(f"{w}x{h}+{x}+{y}")
        self._remote_placed = True

    def remote_refresh_list(self):
        names = list(self.S["remotes"].keys())
        if self.remote_win is not None and self.remote_win.winfo_exists():
            self.remote_win.box["values"] = names
        if self.remote_var.get() not in names and names:
            self.remote_var.set(names[0])

    def current_remote_name(self):
        name = self.remote_var.get()
        if name not in self.S["remotes"]:
            name = next(iter(self.S["remotes"]), "")
        return name

    def current_remote_buttons(self):
        name = self.current_remote_name()
        if not name:
            return []
        return self.S["remotes"][name].setdefault("buttons", [])

    def remote_redraw(self):
        if self.remote_win is not None and self.remote_win.winfo_exists():
            self.remote_win.draw()

    def remote_select(self, name):
        if name in self.S["remotes"]:
            self.S["remote_current"] = name
            save_settings(self.S)
            self.remote_var.set(name)
            self.remote_redraw()

    def remote_toggle_edit(self):
        self.remote_edit = not self.remote_edit
        if self.remote_win is not None and self.remote_win.winfo_exists():
            self.remote_win.edit_btn.config(text="Редактировать: " + ("вкл" if self.remote_edit else "выкл"))
        self.remote_redraw()

    def remote_press(self, b):
        s = self.dev()
        if not s and b.get("type") != "pc":
            return
        typ = b.get("type")
        if typ == "shell":
            self.log(f"Пульт: shell '{b.get('label', '')}'")
            self.run_popup_cmd(b.get("label", "Команда"), str(b.get("value", "")))
        elif typ == "pc":
            self._exec_pc_action(b.get("label", "PC"), str(b.get("value", "")))
        else:
            code = int(b.get("value", 0))
            self.log(f"Пульт: keyevent {code} ('{b.get('label', '')}')")
            self.key(code)

    def _exec_pc_action(self, label, cmd):
        """Выполняет команду на ПК с подстановкой {clipboard} и {serial}."""
        try:
            clip = self.clipboard_get().strip()
        except tk.TclError:
            clip = ""
        serial = self.serial.get().strip()
        cmd = cmd.replace("{clipboard}", clip).replace("{serial}", serial)
        if not cmd.strip():
            self.log(f"{label}: пустая команда")
            return
        self.log(f"PC: {cmd}")
        # Выполняем через shell (cmd.exe /c)
        self.bg(
            lambda: run(["cmd.exe", "/c", cmd], 30),
            lambda res: self.log(f"  код {res[0]}: {(res[1] + res[2]).strip()}" if res[0] != 0 else f"  OK: {(res[1] + res[2]).strip()}")
        )

    def remote_button_dialog(self, idx):
        buttons = self.current_remote_buttons()
        b = dict(buttons[idx]) if idx is not None else {
            "label": "Кнопка", "type": "keyevent", "value": 66, "x": 170, "y": 300, "r": 26, "color": KEY_COL}
        win = tk.Toplevel(self)
        win.title("Кнопка пульта")
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        lab = tk.StringVar(value=b["label"])
        typ = tk.StringVar(value=b["type"])
        val = tk.StringVar(value=str(b["value"]))
        ttk.Label(frm, text="Подпись на кнопке").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=lab, width=30).grid(row=0, column=1, padx=6, pady=3, sticky="w")
        ttk.Label(frm, text="Тип действия").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=typ, values=["keyevent", "shell", "pc"], state="readonly", width=12).grid(
            row=1, column=1, padx=6, pady=3, sticky="w")
        ttk.Label(frm, text="Код клавиши или команда").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=val, width=40).grid(row=2, column=1, padx=6, pady=3, sticky="w")
        hint = ("keyevent: число-код Android, например OK 66, Назад 4, Домой 3, Меню 82, Громкость+ 24, "
                "Громкость- 25, Без звука 164, Вкл 26, Пауза/Пуск 85, Канал+ 166, Канал- 167, "
                "цифры 0-9: 7-16, Инфо 165, Гид 172, Настройки 176.\n"
                "shell: любая команда для устройства, например am start -n пакет/активность.\n"
                "pc: команда на ПК, {clipboard} и {serial} подставятся из буфера и текущего устройства, "
                "например: adb -s {serial} shell kill -9 {clipboard}")
        ttk.Label(frm, text=hint, foreground=C["muted"], wraplength=480, justify="left").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=8)

        def save():
            label = lab.get().strip() or "Кнопка"
            t = typ.get()
            v = val.get().strip()
            if t == "keyevent":
                if not v.isdigit() or not 0 < int(v) < 400:
                    self.log("Код клавиши - число от 1 до 399")
                    return
                v = int(v)
            elif not v:
                self.log("Введите команду shell")
                return
            b.update({"label": label, "type": t, "value": v})
            if idx is None:
                buttons.append(b)
            else:
                buttons[idx] = b
            save_settings(self.S)
            self.remote_redraw()
            win.destroy()

        def delete():
            if idx is not None:
                del buttons[idx]
                save_settings(self.S)
                self.remote_redraw()
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=4, column=0, columnspan=2, sticky="we")
        if idx is not None:
            bar.add(tooltip_btn(ttk.Button(bar, text="Удалить кнопку", command=delete),
                           "Удалить эту кнопку с пульта"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=save),
                           "Сохранить кнопку"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Отмена", command=win.destroy),
                           "Отменить без сохранения"))
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()

    def remote_add_button(self):
        if not self.current_remote_name():
            self.log("Сначала создайте пульт")
            return
        self.remote_button_dialog(None)

    def remote_new(self):
        vals = self.ask_fields("Новый пульт", ["Название пульта"])
        if not vals or not vals["Название пульта"].strip():
            return
        name = vals["Название пульта"].strip()
        if name in self.S["remotes"]:
            self.log("Пульт с таким названием уже есть")
            return
        self.S["remotes"][name] = {"buttons": []}
        save_settings(self.S)
        self.remote_refresh_list()
        self.remote_select(name)

    def remote_copy(self):
        name = self.current_remote_name()
        if not name:
            return
        new = unique_name(name + " (копия)", self.S["remotes"])
        self.S["remotes"][new] = {"buttons": json.loads(json.dumps(self.current_remote_buttons()))}
        save_settings(self.S)
        self.remote_refresh_list()
        self.remote_select(new)

    def remote_rename(self):
        old = self.current_remote_name()
        if not old:
            return
        vals = self.ask_fields("Переименовать пульт", ["Название пульта"], defaults={"Название пульта": old})
        if not vals:
            return
        new = vals["Название пульта"].strip()
        if not new or new == old:
            return
        if new in self.S["remotes"]:
            self.log("Пульт с таким названием уже есть")
            return
        self.S["remotes"] = {(new if k == old else k): v for k, v in self.S["remotes"].items()}
        save_settings(self.S)
        self.remote_refresh_list()
        self.remote_select(new)

    def remote_delete(self):
        name = self.current_remote_name()
        if len(self.S["remotes"]) <= 1:
            self.log("Нельзя удалить последний пульт. Сначала создайте другой")
            return
        del self.S["remotes"][name]
        save_settings(self.S)
        self.remote_refresh_list()
        self.remote_select(self.current_remote_name())
