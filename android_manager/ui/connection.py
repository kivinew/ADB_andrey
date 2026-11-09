# -*- coding: utf-8 -*-
"""Раздел интерфейса: ConnectionTab."""

import functools
import re
import socket

from ..config import C
from ..parsing import CYR_RE, IP_RE, num, split_target
from ..paths import ADB
from ..proc import run
from ..storage import save_settings
from ..util import to_latin


class ConnectionTab:
    """Mix-in для App: методы этого раздела окна."""

    def _fix_host(self, *a):
        v = self.host_var.get()
        if CYR_RE.search(v):
            self.host_var.set(to_latin(v))

    def _fix_port(self, *a):
        v = self.port_var.get()
        nv = re.sub(r"\D", "", v)[:5]
        if nv != v:
            self.port_var.set(nv)

    # ------------------------------------------------ подключение
    def history_menu(self):
        items = [(h, functools.partial(self.pick_host, h)) for h in self.S["history"]]
        self._popup_under(self.hist_btn, items)

    def favorites_menu(self):
        items = [(f["name"], functools.partial(self.pick_fav, f)) for f in self.S["favorites"]]
        items.append(("В избранное: текущее подключение", self.fav_add))
        self._popup_under(self.fav_btn, items)

    def _popup_under(self, widget, items):
        self.popup(items, widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def pick_host(self, target):
        host, port = split_target(target, "5555")
        self.host_var.set(host)
        self.port_var.set(port)

    def pick_fav(self, f):
        self.host_var.set(f["host"])
        self.port_var.set(f["port"])

    def fav_add(self):
        host, port = split_target(self.host_var.get(), self.port_var.get() or "5555")
        if not host:
            self.log("Введите адрес для избранного")
            return
        name = f"{host}:{port}"
        self.S["favorites"] = [f for f in self.S["favorites"] if f["name"] != name]
        self.S["favorites"].append({"name": name, "host": host, "port": port})
        save_settings(self.S)
        self.log(f"В избранное: {name}")

    def _remember(self, target):
        self.S["history"] = ([target] + [h for h in self.S["history"] if h != target])[:10]
        save_settings(self.S)

    def connect(self):
            host, port = split_target(self.host_var.get(), self.port_var.get() or "5555")
            if not host:
                self.log("Введите IP или URL, например example.com")
                return
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                self.log(f"Некорректный порт: «{port}». Введите число от 1 до 65535")
                return

            def job():
                self.log(f"[DEBUG] ADB path: {ADB}")
                self.log(f"[DEBUG] Resolving host: {host}")
                ip = host if IP_RE.fullmatch(host) else socket.gethostbyname(host)
                target = f"{ip}:{port}"
                self.log(f"[DEBUG] Running: adb connect {target}")
                _, o, e = run([ADB, "connect", target], 20)
                self.log(f"[DEBUG] adb connect result: rc={_}, out={o}, err={e}")
                return target, (o + e).strip()

            def done(res):
                if isinstance(res, Exception):
                    self.log(f"Не удалось подключиться: {res}")
                    return
                target, msg = res
                self.log(f"{target}: {msg}")
                self._remember(target)
                self.refresh_devices(select=target)

            self.log(f"Подключение к {host}:{port}...")
            self.bg(job, done)

    def disconnect(self):
        s = self.serial.get().strip()
        if ":" not in s:
            self.log("Отключать можно только сетевое подключение (IP:порт)")
            return
        self.bg(lambda: run([ADB, "disconnect", s], 15),
                lambda res: (self.log((res[1] + res[2]).strip() or "Отключено"), self.refresh_devices()))

    def toggle_connection(self):
        """Переключает состояние подключения: подключить/отключить."""
        s = self.serial.get().strip()
        if s and ":" in s:
            # Устройство подключено -> отключить
            self.disconnect()
        else:
            # Нет подключения -> подключить
            self.connect()

    def pair_dialog(self):
        vals = self.ask_fields("Сопряжение", ["Адрес", "Порт сопряжения", "Код"],
                               defaults={"Адрес": split_target(self.host_var.get(), "")[0]})
        if not vals:
            return
        target = f"{vals['Адрес'].strip()}:{vals['Порт сопряжения'].strip()}"
        code = vals["Код"].strip()
        self.bg(lambda: (lambda r: (r[1] + r[2]).strip())(run([ADB, "pair", target, code], 60)),
                lambda res: self.show_text("Сопряжение", str(res)))

    def refresh_devices(self, select=None):
        def job():
            return run([ADB, "devices", "-l"], 15)

        def done(res):
            rc, out, err = res
            devs, unauth = [], []
            for line in out.splitlines()[1:]:
                p = line.split()
                if len(p) >= 2:
                    if p[1] == "device":
                        devs.append(p[0])
                    elif p[1] == "unauthorized":
                        unauth.append(p[0])
            self.dev_box["values"] = devs
            if select and select in devs:
                self.serial.set(select)
            elif devs and self.serial.get() not in devs:
                self.serial.set(devs[0])
            elif not devs:
                self.serial.set("")
            if unauth:
                self.log("Подтвердите отладку на экране устройства (ключ RSA): " + ", ".join(unauth))
            if rc != 0:
                self.log((out + err).strip())
            self.device_info()
            self.load_caches()
            self._update_toggle_button()

        self.bg(job, done)

    def _update_toggle_button(self):
        """Обновляет текст и tooltip кнопки переключения подключения."""
        if hasattr(self, 'toggle_btn') and self.toggle_btn:
            s = self.serial.get().strip()
            if s and ":" in s:
                self.toggle_btn.config(text="Отключить")
                # Обновляем tooltip через Tooltip объект (если есть доступ)
                # Tooltip создается в tooltip_btn, но мы не сохраняем ссылку
                # Поэтому просто меняем текст кнопки
            else:
                self.toggle_btn.config(text="Подключить")

    def device_info(self):
        s = self.serial.get().strip()
        if not s:
            self.status.set("Не подключено")
            self.status_lbl.config(fg=C["err"])
            self.devinfo.set("")
            return

        def job():
            cmd = ("echo M=$(getprop ro.product.model); echo R=$(getprop ro.build.version.release); "
                   "echo S=$(getprop ro.build.version.sdk); echo T=$(grep MemTotal /proc/meminfo | tr -s ' ' | cut -d' ' -f2); "
                   "echo A=$(grep MemAvailable /proc/meminfo | tr -s ' ' | cut -d' ' -f2)")
            _, o, _ = run([ADB, "-s", s, "shell", cmd], 20)
            d = {}
            for line in o.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    d[k.strip()] = v.strip()
            return d

        def done(res):
            if isinstance(res, Exception) or not res:
                self.status.set(f"Подключено: {s} (Нет ответа от устройства)")
                self.status_lbl.config(fg=C["warn"])
                return
            t = num(res.get("T", "0")) // 1024
            a = num(res.get("A", "0")) // 1024
            self.status.set(f"Подключено: {s}")
            self.status_lbl.config(fg=C["ok"])
            self.devinfo.set(f"{res.get('M', '?')} · Android {res.get('R', '?')} (SDK {res.get('S', '?')}) · "
                             f"RAM {t - a} из {t} МБ")
            self.model_lbl.config(text=f"{res.get('M', '?')} · Android {res.get('R', '?')} (SDK {res.get('S', '?')})")

        self.bg(job, done)

    def check_connection(self):
        """Периодически проверяет доступность выбранного устройства и обновляет статус."""
        s = self.serial.get().strip()
        if not s:
            self.after(3000, self.check_connection)
            return
        try:
            rc, out, err = run([ADB, "-s", s, "shell", "echo OK"], 10)
            alive = (rc == 0 and out.strip() == "OK")
        except Exception:
            alive = False
        if alive:
            if "Нет ответа от устройства" in self.status.get():
                self.status.set(f"Подключено: {s}")
                self.status_lbl.config(fg=C["ok"])
                self.log(f"Устройство {s} восстановлено")
        else:
            if "Нет ответа от устройства" not in self.status.get():
                self.status.set(f"Подключено: {s} (Нет ответа от устройства)")
                self.status_lbl.config(fg=C["warn"])
                self.log(f"Устройство {s} отключено (нет ответа)")
        self.after(3000, self.check_connection)

    def load_caches(self):
        s = self.serial.get().strip()
        if not s:
            return

        def job():
            _, p, _ = run([ADB, "-s", s, "shell", 'getprop | cut -d "[" -f2 | cut -d "]" -f1'], 30)
            _, k, _ = run([ADB, "-s", s, "shell", 'pm list packages | cut -d ":" -f2'], 60)
            _, b, _ = run([ADB, "-s", s, "shell", "ls /system/bin /system/xbin"], 30)
            return (sorted({x for x in p.split() if x}), sorted({x for x in k.split() if x}),
                    sorted({x for x in b.split() if x and not x.endswith(":") and "/" not in x}))

        def done(res):
            if isinstance(res, tuple):
                self.cache["props"], self.cache["pkgs"], self.cache["bins"] = res
                self.cache["dirs"] = {}

        self.bg(job, done)
