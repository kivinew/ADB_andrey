# -*- coding: utf-8 -*-
"""Раздел интерфейса: CardsTab."""

import functools
import tkinter as tk
from tkinter import ttk, scrolledtext

from ..config import C, PALETTE
from ..defaults import default_cards
from ..parsing import build_state_batch, parse_card, parse_state_batch
from ..paths import ADB
from ..proc import run
from ..storage import save_settings
from ..util import slug
from ..widgets.canvas import Spark
from ..widgets.frames import FlowFrame
from ..widgets.tooltip import tooltip_btn


class CardsTab:
    """Mix-in для App: методы этого раздела окна."""

    # --- показатели состояния (редактируемые, как в диспетчере задач)
    def _build_state(self, f):
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        self.model_lbl = top.add(ttk.Label(top, text="-", font=("Segoe UI", 11, "bold")))
        self.auto_state = tk.BooleanVar(value=True)
        top.add(ttk.Checkbutton(top, text="Обновлять каждые 3 с", variable=self.auto_state))
        top.add(tooltip_btn(ttk.Button(top, text="Обновить сейчас", command=self.refresh_state),
                           "Принудительно обновить значения показателей"))
        top.add(tooltip_btn(ttk.Button(top, text="+ Показатель", style="Accent.TButton", command=self.card_add),
                           "Добавить новый пользовательский показатель"))
        top.add(tooltip_btn(ttk.Button(top, text="Сбросить к стандартным", command=self.cards_reset),
                           "Вернуть стандартный набор показателей состояния"))
        self.cards_frame = FlowFrame(f, gap=10)
        self.cards_frame.pack(fill="x", pady=8)
        self.load_lbl = ttk.Label(f, text="")
        self.load_lbl.pack(anchor="w")

    def render_cards(self):
        self.cards_frame.clear()
        self.card_widgets = {}
        for i, card in enumerate(self.S["cards"]):
            color = PALETTE[i % len(PALETTE)]
            box = ttk.LabelFrame(self.cards_frame, text=card.get("title", "Показатель"), padding=8)
            val = ttk.Label(box, text="-", font=("Segoe UI", 10, "bold"))
            val.pack(anchor="w")
            spark = Spark(box, color)
            spark.pack(fill="x", pady=4)
            for w in (box, val, spark):
                w.bind("<Button-3>", functools.partial(self.card_menu, i))
            self.cards_frame.add(box)
            self.card_widgets[card["id"]] = (val, spark, color)
            self.card_hist.setdefault(card["id"], [])
            if card["id"] in self.card_hist:
                spark.draw(self.card_hist[card["id"]], "")

    def card_menu(self, i, ev):
        items = [("Изменить", functools.partial(self.card_edit, i)),
                 ("Удалить", functools.partial(self.card_delete, i)),
                 ("Сдвинуть влево", functools.partial(self.card_move, i, -1)),
                 ("Сдвинуть вправо", functools.partial(self.card_move, i, 1))]
        self.popup(items, ev.x_root, ev.y_root)

    def card_move(self, i, d):
        cards = self.S["cards"]
        j = i + d
        if 0 <= j < len(cards):
            cards[i], cards[j] = cards[j], cards[i]
            save_settings(self.S)
            self.render_cards()

    def card_delete(self, i):
        card = self.S["cards"].pop(i)
        self.card_hist.pop(card["id"], None)
        save_settings(self.S)
        self.render_cards()
        self.log(f"Показатель удалён: {card.get('title')}")

    def cards_reset(self):
        self.S["cards"] = default_cards()
        self.card_hist = {}
        save_settings(self.S)
        self.render_cards()
        self.log("Показатели возвращены к стандартным")

    def card_add(self):
        new = self.card_dialog({"title": "Новый показатель", "cmd": "", "parse": "number", "idx": 0,
                                "div": 1, "unit": "", "max": 0})
        if new is None:
            return
        base = slug(new["title"]) or "card"
        ids = {c["id"] for c in self.S["cards"]}
        cid, n = base, 2
        while cid in ids:
            cid = f"{base}{n}"
            n += 1
        new["id"] = cid
        self.S["cards"].append(new)
        save_settings(self.S)
        self.render_cards()

    def card_edit(self, i):
        card = self.S["cards"][i]
        new = self.card_dialog(dict(card))
        if new is None:
            return
        new["id"] = card["id"]
        self.S["cards"][i] = new
        save_settings(self.S)
        self.render_cards()

    def card_dialog(self, card):
        """Редактор показателя. Возвращает словарь или None."""
        win = tk.Toplevel(self)
        win.title("Показатель состояния")
        win.geometry("700x560")
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        vars_ = {k: tk.StringVar(value=str(card.get(k, ""))) for k in ("title", "idx", "a", "b", "div", "unit", "max")}
        parse = tk.StringVar(value=card.get("parse", "number"))
        labels = [("Название", "title"), ("Номер числа в ответе (для number)", "idx"),
                  ("Число «используется» (для nums_pct)", "a"), ("Число «всего» (для nums_pct)", "b"),
                  ("Делитель значения", "div"), ("Единица (%, МБ, °C, пусто)", "unit"),
                  ("Максимум для графика (0 = без графика)", "max")]
        for r, (text, key) in enumerate(labels):
            ttk.Label(frm, text=text).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=vars_[key], width=40).grid(row=r, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(frm, text="Способ разбора").grid(row=len(labels), column=0, sticky="w", pady=2)
        ttk.Combobox(frm, textvariable=parse, values=["number", "nums_pct", "cpu"], state="readonly",
                     width=14).grid(row=len(labels), column=1, sticky="w", padx=6, pady=2)
        ttk.Label(frm, text="Команда, которая читает значение (путь к файлу или любая shell-команда):").grid(
            row=len(labels) + 1, column=0, columnspan=2, sticky="w", pady=(8, 2))
        txt = scrolledtext.ScrolledText(frm, height=4, bg=C["term"], fg=C["text"], font=("Consolas", 10),
                                        relief="flat", insertbackground=C["text"])
        txt.grid(row=len(labels) + 2, column=0, columnspan=2, sticky="we")
        txt.insert("1.0", card.get("cmd", ""))
        hint = ("number: берётся число под номером «Номер числа» (нумерация с 0), делится на делитель. "
                "nums_pct: процент = число «используется» / число «всего» * 100. "
                "cpu: загрузка процессора из /proc/stat, команда не нужна.\n"
                "Пример: cat /sys/class/thermal/thermal_zone3/temp - путь можно поменять под вашу прошивку.")
        ttk.Label(frm, text=hint, foreground=C["muted"], wraplength=640, justify="left").grid(
            row=len(labels) + 3, column=0, columnspan=2, sticky="w", pady=8)
        result = {}

        def ok():
            def num_or(v, d):
                try:
                    return float(v.get().replace(",", "."))
                except ValueError:
                    return d
            title = vars_["title"].get().strip() or "Показатель"
            p = parse.get()
            cmd = txt.get("1.0", "end").strip()
            if p != "cpu" and not cmd:
                self.log("Введите команду, которая читает значение")
                return
            result["v"] = {"title": title, "cmd": cmd, "parse": p,
                           "idx": int(num_or(vars_["idx"], 0)), "a": int(num_or(vars_["a"], 0)),
                           "b": int(num_or(vars_["b"], 1)), "div": num_or(vars_["div"], 1) or 1,
                           "unit": vars_["unit"].get().strip(), "max": num_or(vars_["max"], 0)}
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=len(labels) + 4, column=0, columnspan=2, sticky="we")
        bar.add(tooltip_btn(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=ok),
                           "Сохранить изменения"))
        bar.add(tooltip_btn(ttk.Button(bar, text="Отмена", command=win.destroy),
                           "Отменить без сохранения"))
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.wait_window()
        return result.get("v")

    def refresh_state(self):
        s = self.serial.get().strip()
        if not s or self.state_busy:
            return
        self.state_busy = True
        cards = list(self.S["cards"])
        batch = build_state_batch(cards)
        self.log(f"[DEBUG] Refresh state batch: {batch[:200]}...")

        def job():
            _, out, _ = run([ADB, "-s", s, "shell", batch], 60)
            return parse_state_batch(out)

        def done(res):
            self.state_busy = False
            if isinstance(res, Exception):
                self.log(f"Состояние: {res}")
                return
            self.log(f"[DEBUG] State vals: {res[0]}, snap: {res[1]}")
            self._show_state(cards, *res)

        self.bg(job, done)

    def _show_state(self, cards, vals, snap):
        self.log(f"[DEBUG _show_state] vals={vals}, snap={snap}")
        for card in cards:
            cid = card["id"]
            if cid not in self.card_widgets:
                continue
            val_lbl, spark, color = self.card_widgets[cid]
            raw = vals.get(cid, "")
            self.log(f"[DEBUG card {cid}] raw='{raw}'")
            # Для температуры получаем значение напрямую через adb
            if cid == "temp" and raw == "":
                try:
                    import subprocess
                    result = subprocess.run(
                        ["adb", "-s", self.serial.get().strip(), "shell",
                         "dumpsys battery 2>/dev/null | grep temperature | cut -d: -f2 | tr -d ' '"],
                        capture_output=True, text=True, timeout=5
                    )
                    raw = result.stdout.strip()
                    self.log(f"[DEBUG temp direct] raw='{raw}'")
                except Exception as e:
                    self.log(f"[DEBUG temp direct error] {e}")
                    raw = "25"
            pct, text = parse_card(card, raw, snap)
            self.log(f"[DEBUG card {cid}] pct={pct}, text='{text}'")
            hist = self.card_hist.setdefault(cid, [])
            hist.append(pct)
            del hist[:-60]
            val_lbl.config(text=text)
            spark.draw(hist, (f"{pct:.0f}%" if pct is not None else ""))

    def on_sub_tab(self):
        cur = self.sub_tools.index("current")
        if cur == 1:
            self.refresh_state()
        elif cur == 2:
            self.refresh_procs()

    def on_main_tab(self):
        if self.nb.index("current") == self.nb.index(self.tools_tab):
            self.on_sub_tab()
