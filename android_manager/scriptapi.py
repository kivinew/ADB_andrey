# -*- coding: utf-8 -*-
"""API для пользовательских скриптов: adb.shell(), packages(), install() и другие."""

import subprocess
import time
import types

from .parsing import parse_pkgs, split_target
from .paths import ADB
from .proc import NO_WIN, run


# ---------------------------------------------------------------- API для скриптов
class ScriptStop(Exception):
    """Поднимается, когда пользователь нажал «Остановить»."""


class AdbModule(types.ModuleType):
    """Модуль `adb` для пользовательских скриптов.

    Скрипт обращается и как к объекту (`adb.getprop(...)`, `adb` уже лежит в его
    пространстве имён), и через `import adb` (модуль подставляется в sys.modules).
    Поэтому все атрибуты делегируются живому ScriptAPI: иначе в модуле был бы
    только `shell`, а `getprop`, `packages`, `install` и прочие — нет.
    """

    def __init__(self, api):
        super().__init__("adb")
        self.__dict__["_api"] = api

    def __getattr__(self, name):
        api = self.__dict__.get("_api")
        if api is None:
            raise AttributeError(name)
        try:
            return getattr(api, name)
        except AttributeError:
            raise AttributeError("module 'adb' has no attribute %r" % name) from None


class ScriptAPI:
    """Объект adb для скриптов. Программа отправляет команды на устройство и возвращает вывод."""

    PKG_FLAGS = {"all": [], "user": ["-3"], "system": ["-s"], "disabled": ["-d"]}

    def __init__(self, serial, pc_ip, stop_ev):
        self.serial = serial
        self.ip, self.port = split_target(serial, "5555") if serial else ("", "5555")
        self.pc_ip = pc_ip
        self._stop = stop_ev

    def check(self):
        """Вызывайте в своих циклах: при «Остановить» скрипт завершится."""
        if self._stop.is_set():
            raise ScriptStop()

    @property
    def stopped(self):
        return self._stop.is_set()

    def sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.check()
            time.sleep(min(0.2, max(0, end - time.time())))

    def call(self, *args, timeout=120):
        self.check()
        if not self.serial:
            raise RuntimeError("Устройство не подключено")
        return run([ADB, "-s", self.serial, *args], timeout)

    def shell(self, command, timeout=60):
        rc, out, err = self.call("shell", command, timeout=timeout)
        return (out + err).rstrip("\n")

    def getprop(self, name):
        return self.shell(f"getprop {name}").strip()

    def packages(self, kind="all"):
        flags = self.PKG_FLAGS.get(kind, [])
        out = self.shell("pm list packages " + " ".join(flags), timeout=90)
        return parse_pkgs(out)

    def force_stop(self, pkg):
        return self.shell(f"am force-stop {pkg}")

    def clear(self, pkg):
        return self.shell(f"pm clear {pkg}")

    def disable(self, pkg):
        return self.shell(f"pm disable-user --user 0 {pkg}")

    def enable(self, pkg):
        return self.shell(f"pm enable --user 0 {pkg}")

    def uninstall(self, pkg):
        return self.shell(f"pm uninstall -k --user 0 {pkg}")

    def launch(self, pkg):
        return self.shell(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1", timeout=30)

    def install(self, apk_path):
        rc, out, err = self.call("install", "-r", apk_path, timeout=600)
        text = (out + err).strip()
        return "Success" in text, text

    def push(self, local_path, remote_path):
        rc, out, err = self.call("push", local_path, remote_path, timeout=600)
        if rc != 0:
            raise RuntimeError((out + err).strip())
        return (out + err).strip()

    def pull(self, remote_path, local_path):
        rc, out, err = self.call("pull", remote_path, local_path, timeout=600)
        if rc != 0:
            raise RuntimeError((out + err).strip())
        return local_path

    def screenshot(self, path):
        self.check()
        p = subprocess.run([ADB, "-s", self.serial, "exec-out", "screencap", "-p"], capture_output=True,
                           timeout=60, stdin=subprocess.DEVNULL, creationflags=NO_WIN)
        if p.returncode != 0 or not p.stdout:
            raise RuntimeError("screencap не сработал")
        with open(path, "wb") as fh:
            fh.write(p.stdout)
        return path

    def reboot(self, mode=""):
        self.call(*(["reboot"] + ([mode] if mode else [])), timeout=15)
