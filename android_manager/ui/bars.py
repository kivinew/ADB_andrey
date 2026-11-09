# -*- coding: utf-8 -*-
"""Раздел интерфейса: BarsTab."""

import functools
import os
import tkinter as tk
from tkinter import ttk

from ..config import C
from ..paths import P
from ..storage import save_settings
from ..widgets.tooltip import tooltip_btn


class BarsTab:
    """Mix-in для App: методы этого раздела окна."""

    # ------------------------------------------------ кнопки (общий механизм, адаптивный)
    def render_bar(self, bid):
        """Кнопки раскладываются по ширине окна и переносятся на новые строки (без полного пересоздания)."""
        fr = self.bar_frames.get(bid)
        if fr is None:
            return
        data_items = self.S["bars"].get(bid, [])
        # Сохраняем существующие виджеты и перерабатываем их
        existing = fr.items[:]
        # Очищаем только те, что не нужны, и обновляем существующие
        # Сначала удаляем лишние (если элементов стало меньше)
        keep_buttons = []
        add_btn = None
        for w in existing:
            if isinstance(w, ttk.Button) and w.cget("text") == "+ Добавить скрипт" or \
                    (w.cget("text") == "+ Добавить действие" if bid == "apps" else w.cget("text") == "+ Добавить кнопку"):
                add_btn = w
            else:
                # Обычная кнопка данных
                pass
        # Упрощённый подход: удаляем все, но только когда количество изменилось или текст изменился — нет.
        # Для простоты и надёжности сохраняем адаптивность: удаляем всё, но только при явном изменении; иначе реиспользуем.
        # Но полный пересоздание — медленно. Сделаем гибрид: удаляем только если количество элементов изменилось.
        current_data_count = len(data_items)
        current_btn_count = len([w for w in existing if isinstance(w, ttk.Button) and w != add_btn])
        if current_data_count != current_btn_count or any(not w.winfo_exists() for w in existing):
            # Пересоздаём всё при изменении количества или если виджеты уничтожены
            fr.clear()
            for i, it in enumerate(data_items):
                b = ttk.Button(fr, text=it["name"], command=functools.partial(self.bar_click, bid, i))
                b.bind("<Button-3>", functools.partial(self.bar_menu, bid, i))
                fr.add(b)
            if bid == "scripts":
                label, cmd = "+ Добавить скрипт", self.add_script_file
            elif bid == "apps":
                label, cmd = "+ Добавить действие", functools.partial(self.apps_action_edit, None)
            else:
                label, cmd = "+ Добавить кнопку", functools.partial(self.bar_edit, bid, None)
            fr.add(ttk.Button(fr, text=label, style="Accent.TButton", command=cmd))
        else:
            # Количество совпадает — просто обновляем данные у существующих кнопок
            btns = [w for w in existing if isinstance(w, ttk.Button) and w.cget("style") != "Accent.TButton"]
            for i in range(min(len(btns), len(data_items))):
                it = data_items[i]
                btns[i].configure(text=it["name"], command=functools.partial(self.bar_click, bid, i))
                # Перепривязываем ПКМ
                btns[i].bind("<Button-3>", functools.partial(self.bar_menu, bid, i), add="+")
        return

    def bar_menu(self, bid, idx, ev):
        items = [("Изменить", functools.partial(self.bar_edit_any, bid, idx)),
                 ("Удалить", functools.partial(self.bar_delete, bid, idx)),
                 ("Сдвинуть влево", functools.partial(self.bar_move, bid, idx, -1)),
                 ("Сдвинуть вправо", functools.partial(self.bar_move, bid, idx, 1))]
        self.popup(items, ev.x_root, ev.y_root)

    def bar_move(self, bid, idx, d):
        items = self.S["bars"][bid]
        j = idx + d
        if 0 <= j < len(items):
            items[idx], items[j] = items[j], items[idx]
            save_settings(self.S)
            self.render_bar(bid)

    def bar_delete(self, bid, idx):
        it = self.S["bars"][bid].pop(idx)
        if bid == "scripts" and it.get("file"):
            fn = it["file"]
            if not any(x.get("file") == fn for x in self.S["bars"]["scripts"]):
                path = P("scripts", fn)
                if os.path.isfile(path):
                    os.remove(path)
        save_settings(self.S)
        self.render_bar(bid)
        self.log(f"Кнопка удалена: {it.get('name')}")

    def bar_edit_any(self, bid, idx):
        if bid == "scripts":
            self.script_edit(idx)
        elif bid == "apps":
            self.apps_action_edit(idx)
        else:
            self.bar_edit(bid, idx)

    def bar_click(self, bid, idx):
        it = self.S["bars"][bid][idx]
        if bid == "scripts":
            self.run_script(it)
        elif bid == "apps":
            self.apps_run(it)
        elif bid == "console":
            self.nb.select(self.console_tab)
            cmd = it.get("cmd", "")
            typ = it.get("type", "shell")
            if typ == "pc":
                self._exec_pc_action(it.get("name", "PC"), cmd)
            else:
                # Подставляем {clipboard} и {serial} для shell-команд
                try:
                    clip = self.clipboard_get().strip()
                except tk.TclError:
                    clip = ""
                serial = self.serial.get().strip()
                cmd = cmd.replace("{clipboard}", clip).replace("{serial}", serial)
                self.console_exec(cmd)
        else:
            self.run_popup_cmd(it.get("name", "Команда"), it.get("cmd", ""))

    def bar_edit(self, bid, idx):
        it = dict(self.S["bars"][bid][idx]) if idx is not None else {"name": "Новая кнопка", "cmd": "", "type": "shell"}
        typ = it.get("type", "shell")
        if bid == "console":
            # Для консоли добавляем выбор типа
            win = tk.Toplevel(self)
            win.title("Кнопка консоли")
            win.geometry("600x320")
            win.configure(bg=C["bg"])
            win.transient(self)
            frm = ttk.Frame(win, padding=12)
            frm.pack(fill="both", expand=True)
            ttk.Label(frm, text="Название").grid(row=0, column=0, sticky="w", pady=3)
            name_var = tk.StringVar(value=it.get("name", ""))
            ttk.Entry(frm, textvariable=name_var, width=50).grid(row=0, column=1, padx=6, pady=3, sticky="we")
            ttk.Label(frm, text="Тип").grid(row=1, column=0, sticky="w", pady=3)
            type_var = tk.StringVar(value=typ)
            ttk.Combobox(frm, textvariable=type_var, values=["shell", "pc"], state="readonly", width=12).grid(row=1, column=1, padx=6, pady=3, sticky="w")
            ttk.Label(frm, text="Команда").grid(row=2, column=0, sticky="w", pady=3)
            cmd_var = tk.StringVar(value=it.get("cmd", ""))
            ttk.Entry(frm, textvariable=cmd_var, width=50).grid(row=2, column=1, padx=6, pady=3, sticky="we")
            hint_text = ("shell: команда в shell устройства (adb shell ...)\n"
                         "pc: команда на ПК, {clipboard} и {serial} подставятся из буфера и устройства\n"
                         "Пример pc: adb -s {serial} shell kill -9 {clipboard}")
            ttk.Label(frm, text=hint_text, foreground=C["muted"], wraplength=500, justify="left").grid(row=3, column=0, columnspan=2, sticky="w", pady=8)
            frm.columnconfigure(1, weight=1)

            def save():
                name = name_var.get().strip()
                cmd = cmd_var.get().strip()
                t = type_var.get()
                if not name or not cmd:
                    return
                new = {"name": name, "cmd": cmd, "type": t}
                if idx is None:
                    self.S["bars"][bid].append(new)
                else:
                    self.S["bars"][bid][idx] = new
                save_settings(self.S)
                self.render_bar(bid)
                win.destroy()

            def delete():
                self.bar_delete(bid, idx)
                win.destroy()

            btns = ttk.Frame(frm)
            btns.grid(row=4, column=0, columnspan=2, pady=12)
            tooltip_btn(ttk.Button(btns, text="Сохранить", command=save),
                           "Сохранить изменения").pack(side="left", padx=4)
            if idx is not None:
                tooltip_btn(ttk.Button(btns, text="Удалить", command=delete),
                           "Удалить кнопку").pack(side="left", padx=4)
            tooltip_btn(ttk.Button(btns, text="Отмена", command=win.destroy),
                           "Отменить без сохранения").pack(side="left", padx=4)
            win.wait_window()
            return

        # Для tools/apps — старый диалог
        vals = self.ask_multiline(
            "Кнопка", it.get("name", ""), it.get("cmd", ""),
            hint=("Команда выполняется в shell устройства. Результат откроется в окне."
                  if bid == "tools" else "Команда выполняется в shell устройства и выводится в консоль."),
            can_delete=idx is not None)
        if vals is None:
            return
        if vals == "delete":
            self.bar_delete(bid, idx)
            return
        name, cmd = vals
        new = {"name": name or "Кнопка", "cmd": cmd.strip()}
        if idx is None:
            self.S["bars"][bid].append(new)
        else:
            self.S["bars"][bid][idx] = new
        save_settings(self.S)
        self.render_bar(bid)
