#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Установщик Android ТВ-Менеджера v1.5 для Windows 8.1 / 10 / 11 (один файл).

Запуск: двойной клик по файлу или  python Android_manager.py
Нажмите «Установить». Ничего копировать и готовить заранее не нужно.

Что делает:
  1. Скачивает Android platform-tools (adb) с сайта Google.
  2. Скачивает scrcpy (последний релиз win64) с GitHub.
  3. Собирает Android-manager.exe через PyInstaller (во временной папке).
  4. Устанавливает программу в %LOCALAPPDATA%\\Android-manager вместе с adb и scrcpy.
  5. Создаёт ярлыки на рабочем столе и в меню «Пуск».

Ключ --cli запускает установку без окна (в консоли).
Пользовательские данные (настройки, кнопки, пульты, показатели, скрипты, APK) сохраняются при переустановке.
"""

import os
import sys
import json
import queue
import ctypes
import shutil
import zipfile
import tempfile
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import argparse

APP_EXE = "Android-manager"
APP_TITLE = "Android manager"
VERSION = "1.7"
DEFAULT_PARENT = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
SCRCPY_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
HEADERS = {"User-Agent": "Android-manager-Installer"}
USER_DIRS = ("apk", "programs", "scripts", "screenshots", "files")
CSIDL_DESKTOPDIRECTORY = 0x0010
CSIDL_PROGRAMS = 0x0002

# Исходный код программы. Установщик записывает его во временную папку и собирает exe.
# Внутри программы нет тройных одинарных кавычек: они закрыли бы эту строку.
# ------------------------------------------------ tooltip-подсказки
class Tooltip:
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwin = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, ev=None):
        self.id = self.widget.after(self.delay, self.show)

    def on_leave(self, ev=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self.hide()

    def show(self):
        if self.tipwin:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipwin = tk.Toplevel(self.widget)
        self.tipwin.wm_overrideredirect(True)
        self.tipwin.wm_geometry(f"+{x}+{y}")
        self.tipwin.configure(bg="#243a55", bd=1, relief="solid")
        lbl = tk.Label(self.tipwin, text=self.text, justify="left", bg="#243a55",
                       fg="#e6edf5", font=("Segoe UI", 9), padx=6, pady=3)
        lbl.pack()
        self.tipwin.update_idletasks()

    def hide(self):
        if self.tipwin:
            self.tipwin.destroy()
            self.tipwin = None


def tooltip_btn(btn, text):
    return Tooltip(btn, text)



PROGRAM_SRC = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android ТВ-Менеджер v1.5: управление Android ТВ-устройствами через ADB.

Вкладки: Приложения, Инструменты (управление, состояние, процессы), Консоль,
Скрипты, Настройки, О программе. Почти всё в программе можно добавлять,
менять и удалять: кнопки, пульты, показатели состояния, действия над приложениями,
скрипты Python.

Папка рядом с exe:
  Android-manager.exe, tools\\adb\\adb.exe, tools\\scrcpy\\scrcpy.exe
  scripts\\ (все скрипты Python), apk\\, programs\\, screenshots\\, files\\, settings.json
"""

import os
import re
import sys
import csv
import json
import time
import queue
import shlex
import shutil
import socket
import datetime
import functools
import traceback
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

VERSION = "1.7"
APP_TITLE = "Android manager"
BUNDLE_FORMAT = "android-tv-bundle"
REMOTE_W, REMOTE_H = 340, 600

C = {
    "bg": "#14202e", "head": "#1e4170", "bar": "#1a2c42", "panel": "#1e2e42",
    "border": "#2f4661", "text": "#e6edf5", "muted": "#9fb4cc", "accent": "#5aa9f0",
    "ok": "#7fd68f", "warn": "#ffb347", "err": "#ff7b7b", "term": "#0b121b", "sel": "#2a4a6e",
    "key": "#243a55", "keyhot": "#2f6fb0", "body": "#0c1520", "red": "#8b2f36",
    "purple": "#c49bff",
}


# ------------------------------------------------ tooltip-подсказки
class Tooltip:
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwin = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, ev=None):
        self.id = self.widget.after(self.delay, self.show)

    def on_leave(self, ev=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self.hide()

    def show(self):
        if self.tipwin:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipwin = tk.Toplevel(self.widget)
        self.tipwin.wm_overrideredirect(True)
        self.tipwin.wm_geometry(f"+{x}+{y}")
        self.tipwin.configure(bg="#243a55", bd=1, relief="solid")
        lbl = tk.Label(self.tipwin, text=self.text, justify="left", bg="#243a55",
                       fg="#e6edf5", font=("Segoe UI", 9), padx=6, pady=3)
        lbl.pack()
        self.tipwin.update_idletasks()

    def hide(self):
        if self.tipwin:
            self.tipwin.destroy()
            self.tipwin = None


def tooltip_btn(btn, text):
    return Tooltip(btn, text)

PALETTE = ["#5aa9f0", "#c49bff", "#7fd68f", "#ffb347", "#ff7b7b", "#7fd0ff", "#e6d26b", "#9fb4cc"]

NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IP_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
CYR_RE = re.compile(r"[а-яёА-ЯЁ]")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

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

LEGACY_TOOL_NAMES = {"Сводка устройства", "Топ по памяти", "Закрыть пользовательские"}

LAYOUT = {}
for _r, _e in zip("йцукенгшщзхъфывапролджэячсмитьбюё", "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"):
    LAYOUT[_r] = _e
    LAYOUT[_r.upper()] = _e.upper()


def to_latin(text):
    return "".join(LAYOUT.get(ch, ch) for ch in text)


# ---------------------------------------------------------------- пути
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE = app_dir()


def P(*parts):
    return os.path.join(BASE, *parts)


SCRIPTS_DIR = P("scripts")
for _d in ("apk", "programs", "scripts", "screenshots", "files"):
    os.makedirs(P(_d), exist_ok=True)

# Создаём adb.py в папке скриптов для импорта пользовательскими скриптами
ADB_PY_PATH = P("scripts", "adb.py")
if not os.path.isfile(ADB_PY_PATH):
    try:
        with open(ADB_PY_PATH, "w", encoding="utf-8") as _f:
            _f.write('# -*- coding: utf-8 -*-\n"""\nadb-модуль для пользовательских скриптов.\nПредоставляет функцию shell(command, timeout=60) -> str.\nИспользование:\n    import adb\n    output = adb.shell("logcat -d -t 100")\n"""\nimport sys\nimport os\n\n# Добавляем путь к основному приложению для доступа к ScriptAPI\n# При запуске из Android-manager переменная __adb_api__ передаётся через exec namespace\nif "__adb_api__" in globals():\n    _api = globals()["__adb_api__"]\nelse:\n    _api = None\n\ndef shell(command, timeout=60):\n    """Выполняет shell-команду на подключённом устройстве."""\n    if _api is None:\n        raise RuntimeError("adb.shell: API недоступен. Запускайте скрипт через вкладку «Скрипты».")\n    return _api.shell(command, timeout=timeout)\n\n# Для совместимости с tvdiag_report.py\n__all__ = ["shell"]\n')
    except Exception:
        pass

SETTINGS_PATH = P("settings.json")


def find_tool(rel_dir, exe, fallback):
    local = P("tools", rel_dir, exe)
    if os.path.isfile(local):
        return local
    return shutil.which(fallback) or fallback


ADB = find_tool("adb", "adb.exe", "adb")
SCRCPY = find_tool("scrcpy", "scrcpy.exe", "scrcpy")


# ---------------------------------------------------------------- значения по умолчанию
KEY_COL = "#243a55"
ACC_COL = "#2f6fb0"
RED_COL = "#8b2f36"


def _btn(label, value, x, y, r=24, color=KEY_COL, kind="keyevent"):
    return {"label": label, "type": kind, "value": value, "x": x, "y": y, "r": r, "color": color}


def standard_layout():
    """Compact layout: 2-row nav, thumbstick vertical pair, OK center, bottom cluster."""
    return [
        _btn("◀◀", 82, 60, 17),
        _btn("▶▶", 258, 60, 17),
        _btn("◀", 96, 130, 17),
        _btn("▶", 244, 130, 17),
        _btn("↑", 170, 210, 30),
        _btn("↓", 170, 285, 30),
        _btn("OK", 170, 360, 38),
        _btn("menu", 55, 440, 18),
        _btn("back", 128, 440, 18),
        _btn("home", 205, 440, 18),
        _btn("info", 282, 440, 18),
        _btn("ch+", 108, 520, 17),
        _btn("ch-", 182, 520, 17),
        _btn("vol+", 64, 565, 16),
        _btn("vol-", 270, 565, 16),
    ]


def tanix_layout():
    items = standard_layout()
    for it in items:
        if it["label"] == "▶▶":
            it["label"], it["value"] = "Настр.", 176
    return items


def eltex_layout():
    """Compact layout mirroring standard: 2-row nav, center OK, bottom cluster."""
    return [
        _btn("◀◀", 82, 60, 17),
        _btn("▶▶", 258, 60, 17),
        _btn("◀", 96, 130, 17),
        _btn("▶", 244, 130, 17),
        _btn("↑", 170, 210, 30),
        _btn("↓", 170, 285, 30),
        _btn("OK", 170, 360, 38),
        _btn("menu", 55, 440, 18),
        _btn("back", 128, 440, 18),
        _btn("home", 205, 440, 18),
        _btn("info", 282, 440, 18),
        _btn("ch+", 108, 520, 17),
        _btn("ch-", 182, 520, 17),
        _btn("vol+", 64, 565, 16),
        _btn("vol-", 270, 565, 16),
    ]


def default_remotes():
    return {
        "Android TV (стандартный)": {"buttons": standard_layout()},
        "Tanix W2 (Android-устройство)": {"buttons": tanix_layout()},
        "Eltex NV-731 (ТВ-пульт)": {"buttons": eltex_layout()},
    }


def default_cards():
    """Показатели состояния. Команду, путь чтения и разбор можно менять в программе."""
    return [
        {"id": "ram", "title": "Оперативная память", "parse": "nums_pct", "a": 1, "b": 0, "div": 1024,
         "unit": "МБ", "max": 100,
         "cmd": "awk '/^MemTotal/{t=$2}/^MemAvailable/{a=$2}END{print t, t-a}' /proc/meminfo"},
        {"id": "disk", "title": "Внутренняя память (/data)", "parse": "nums_pct", "a": 0, "b": 1, "div": 1024,
         "unit": "МБ", "max": 100,
         "cmd": "df -k /data | tail -1 | awk '{print $3, $2}'"},
        {"id": "cpu", "title": "Процессор (CPU)", "parse": "cpu", "unit": "%", "max": 100, "cmd": ""},
        {"id": "gpu", "title": "Видеопроцессор (GPU)", "parse": "number", "idx": 0, "div": 1, "unit": "%",
         "max": 100, "cmd": "cat /sys/class/mpgpu/utilization"},
        {"id": "temp", "title": "Температура SoC", "parse": "number", "idx": 0, "div": 1000, "unit": "°C",
         "max": 100, "cmd": "cat /sys/class/thermal/thermal_zone0/temp"},
        {"id": "load", "title": "Нагрузка CPU (1 мин)", "parse": "number", "idx": 0, "div": 1, "unit": "",
         "max": 0, "cmd": "cat /proc/loadavg"},
    ]


DEFAULT_APPS_BAR = [
    {"name": "Запустить", "cmd": "monkey -p {pkg} -c android.intent.category.LAUNCHER 1", "per_pkg": True},
    {"name": "Закрыть (force-stop)", "cmd": "am force-stop {pkg}", "per_pkg": True},
    {"name": "Очистить данные и кэш", "cmd": "pm clear {pkg}", "per_pkg": True},
    {"name": "Удалить (user 0)", "cmd": "pm uninstall -k --user 0 {pkg}", "per_pkg": True},
    {"name": "Отключить", "cmd": "pm disable-user --user 0 {pkg}", "per_pkg": True},
    {"name": "Включить", "cmd": "pm enable --user 0 {pkg}", "per_pkg": True},
    {"name": "Информация", "cmd": 'dumpsys package {pkg} | grep -E "versionName|codePath|firstInstallTime"',
     "per_pkg": True},
    {"name": "Закрыть все пользовательские", "per_pkg": False,
     "cmd": 'for p in $(pm list packages -3 | cut -d ":" -f2); do am force-stop $p; done; echo готово'},
]

DEFAULT_CONSOLE_BAR = [
    {"name": "logcat (300)", "cmd": "logcat -d -t 300", "type": "shell"},
    {"name": "dmesg (хвост)", "cmd": "dmesg | tail -200", "type": "shell"},
    {"name": "Процессы", "cmd": "ps -A", "type": "shell"},
    {"name": "Сеть", "cmd": "ip addr", "type": "shell"},
    {"name": "Диск", "cmd": "df", "type": "shell"},
]

DEFAULT_SCRIPT_FILES = [
    ("Сводка устройства (Python)",
     'print("Модель:", adb.getprop("ro.product.model"))\n'
     'print("Android:", adb.getprop("ro.build.version.release"))\n'
     'print(adb.shell("grep -E \'MemTotal|MemAvailable\' /proc/meminfo"))\n'),
    ("Закрыть пользовательские (Python)",
     'apps = adb.packages("user")\n'
     'print("Пользовательских приложений:", len(apps))\n'
     'for pkg in apps:\n'
     '    adb.force_stop(pkg)\n'
     '    print("закрыто:", pkg)\n'),
]

DEFAULT_SETTINGS = {
    "pc_ip": "",
    "vysor_path": "",
    "history": [],
    "favorites": [],
    "app_presets": {},
    "defaults_done": False,
    "bars": {"tools": [], "console": json.loads(json.dumps(DEFAULT_CONSOLE_BAR)), "scripts": [],
             "apps": json.loads(json.dumps(DEFAULT_APPS_BAR))},
    "remotes": {},
    "remote_current": "",
    "cards": default_cards(),
    "scrcpy": {"max_size": "1920", "fps": "60", "bitrate": "8M", "codec": "h264",
               "show_touches": False, "stay_awake": True, "screen_off": False},
}


# ---------------------------------------------------------------- чистая логика (без окна, проверяется отдельно)
def merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merge(base[k], v)
        else:
            base[k] = v
    return base


def slug(name):
    return re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_").lower() or "item"


def unique_path(folder, filename):
    base, ext = os.path.splitext(filename)
    path = os.path.join(folder, filename)
    i = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{i}{ext}")
        i += 1
    return path


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().replace("\r\n", "\n")


def save_script_text(scripts_dir, name, text):
    dest = unique_path(scripts_dir, slug(name) + ".py")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.replace("\r\n", "\n"))
    return os.path.basename(dest)


def import_script_file(scripts_dir, src_path, name):
    """Копия внешнего .py в папку scripts, даже если выбран файл из другого места."""
    return save_script_text(scripts_dir, name, read_text(src_path))


def migrate_settings(S, scripts_dir):
    """Приводит старые настройки к версии 1.5. Возвращает True, если что-то изменилось."""
    changed = False
    bars = S.setdefault("bars", {})
    tools = bars.setdefault("tools", [])
    kept = [it for it in tools if it.get("name") not in LEGACY_TOOL_NAMES]
    if len(kept) != len(tools):
        bars["tools"] = kept
        changed = True
    if "apps" not in bars:
        bars["apps"] = json.loads(json.dumps(DEFAULT_APPS_BAR))
        changed = True
    scripts = bars.setdefault("scripts", [])
    for it in scripts:
        if "code" in it and "file" not in it:
            it["file"] = save_script_text(scripts_dir, it.get("name", "script"), it.pop("code"))
            changed = True
        it.setdefault("kind", "script")
    if not S.get("defaults_done"):
        for name, code in DEFAULT_SCRIPT_FILES:
            scripts.append({"name": name, "kind": "script", "file": save_script_text(scripts_dir, name, code)})
        S["defaults_done"] = True
        changed = True
    if not S.get("remotes"):
        S["remotes"] = default_remotes()
        changed = True
    if S.get("remote_current") not in S["remotes"]:
        S["remote_current"] = next(iter(S["remotes"]))
        changed = True
    if not S.get("cards"):
        S["cards"] = default_cards()
        changed = True
    for card in S["cards"]:
        card.setdefault("unit", "")
        card.setdefault("max", 0)
        card.setdefault("div", 1)
        card.setdefault("parse", "number")
    return changed


def make_bundle(S, scripts_dir, programs):
    """Один файл экспорта: настройки, кнопки, пульты, показатели, тексты всех скриптов, программы."""
    settings = json.loads(json.dumps(S))
    for key in ("history", "vysor_path", "pc_ip"):
        settings.pop(key, None)
    scripts = {}
    for it in S.get("bars", {}).get("scripts", []):
        fn = it.get("file")
        path = os.path.join(scripts_dir, fn) if fn else None
        if path and os.path.isfile(path):
            scripts[fn] = read_text(path)
    return {"format": BUNDLE_FORMAT, "version": VERSION, "settings": settings,
            "scripts": scripts, "programs": programs}


def apply_bundle(bundle, S, scripts_dir):
    """Загружает экспорт в текущие настройки. Возвращает (S, число скриптов, программы)."""
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError("Это не файл экспорта Android ТВ-Менеджера")
    mapping = {}
    for fn, text in bundle.get("scripts", {}).items():
        existing = os.path.join(scripts_dir, fn)
        if os.path.isfile(existing) and read_text(existing) == text:
            mapping[fn] = fn
        else:
            dest = unique_path(scripts_dir, fn)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            mapping[fn] = os.path.basename(dest)
    imported = bundle.get("settings", {})
    have_files = {it.get("file") for it in S["bars"].setdefault("scripts", [])}
    for it in imported.get("bars", {}).get("scripts", []):
        fn = it.get("file")
        if not fn:
            continue
        new_fn = mapping.get(fn, fn)
        if new_fn in have_files:
            continue
        S["bars"]["scripts"].append({"name": it.get("name", "script"), "kind": "script", "file": new_fn})
        have_files.add(new_fn)
    for bid in ("tools", "console", "apps"):
        have = {(i.get("name"), i.get("cmd")) for i in S["bars"].setdefault(bid, [])}
        for it in imported.get("bars", {}).get(bid, []):
            key = (it.get("name"), it.get("cmd"))
            if key not in have:
                S["bars"][bid].append(it)
                have.add(key)
    for name, rem in imported.get("remotes", {}).items():
        S.setdefault("remotes", {})[name] = rem
    if imported.get("remote_current") in S.get("remotes", {}):
        S["remote_current"] = imported["remote_current"]
    if imported.get("cards"):
        have_ids = {c["id"] for c in S.get("cards", [])}
        for card in imported["cards"]:
            if card.get("id") not in have_ids:
                S.setdefault("cards", []).append(card)
                have_ids.add(card.get("id"))
    for key in ("scrcpy", "app_presets"):
        if key in imported:
            S[key] = imported[key]
    return S, len(mapping), bundle.get("programs", [])


def hit_button(buttons, x, y):
    for i in range(len(buttons) - 1, -1, -1):
        b = buttons[i]
        if (x - b["x"]) ** 2 + (y - b["y"]) ** 2 <= (b["r"] + 2) ** 2:
            return i
    return None


def flow_layout(sizes, avail_w, gap=6):
    """Раскладка элементов по строкам под ширину. sizes: [(ширина, высота)]. Возвращает ([(x, y)], высота)."""
    pos = []
    x = y = row_h = 0
    avail_w = max(1, avail_w)
    for w, h in sizes:
        if x > 0 and x + w > avail_w:
            x = 0
            y += row_h + gap
            row_h = 0
        pos.append((x, y))
        x += w + gap
        row_h = max(row_h, h)
    total = (y + row_h) if sizes else 0
    return pos, total


def fit_scale(cw, ch):
    """Масштаб пульта, чтобы он целиком помещался в окно."""
    return max(0.2, min(cw / REMOTE_W, ch / REMOTE_H))


def remote_window_rect(target, screen_w, screen_h, aspect=REMOTE_W / REMOTE_H):
    """Окно пульта: рядом слева от окна scrcpy/Vysor с той же высотой, иначе у левого края экрана."""
    if target:
        x, y, w, h = target
        rw = int(h * aspect) + 16
        return max(0, x - rw - 6), y, rw, h
    h = int(screen_h * 0.9)
    rw = int(h * aspect) + 16
    return 0, int(screen_h * 0.05), rw, h


def cpu_totals(line):
    nums = [num(x) for x in line.split()[1:]]
    if len(nums) < 5:
        return 0, 0
    return sum(nums[:8]), nums[3] + nums[4]


def num(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def card_numbers(text):
    return [float(x) for x in NUM_RE.findall(text)]


def parse_card(card, text, snap=None):
    """Разбор ответа показателя. Возвращает (процент для графика или None, текст для показа)."""
    unit = card.get("unit", "")
    div = card.get("div") or 1
    parse = card.get("parse", "number")
    if parse == "cpu":
        if not snap:
            return None, "н/д"
        s1, s2 = snap
        dt = s2[0] - s1[0]
        if dt <= 0:
            return None, "н/д"
        busy = (dt - (s2[1] - s1[1])) * 100.0 / dt
        return busy, f"{busy:.0f}%"
    nums = card_numbers(text)
    if parse == "nums_pct":
        a_i, b_i = int(card.get("a", 0)), int(card.get("b", 1))
        if max(a_i, b_i) >= len(nums) or min(a_i, b_i) < 0:
            return None, "н/д"
        a, b = nums[a_i], nums[b_i]
        if b <= 0:
            return None, "н/д"
        pct = a * 100.0 / b
        return pct, f"{a / div:.0f} из {b / div:.0f} {unit} ({pct:.0f}%)"
    i = int(card.get("idx", 0))
    if i < 0 or i >= len(nums):
        return None, "н/д"
    v = nums[i] / div
    mx = card.get("max") or 0
    pct = (v * 100.0 / mx) if mx else None
    return pct, (f"{v:.1f} {unit}").rstrip()


def build_state_batch(cards):
    """Одна команда для всех показателей. Каждый ответ печатается строкой @@c<id> ...."""
    parts = []
    for c in cards:
        if c.get("parse") == "cpu":
            continue
        cmd = (c.get("cmd") or "").strip()
        if not cmd:
            continue
        parts.append(f'echo "@@c{c["id"]} $({cmd} 2>/dev/null | tr "\\n" " ")"')
    parts += ['echo "@@S1 $(head -1 /proc/stat)"', "sleep 1", 'echo "@@S2 $(head -1 /proc/stat)"']
    return "; ".join(parts)


def parse_state_batch(raw):
    vals = {}
    s1 = s2 = None
    for line in raw.splitlines():
        if line.startswith("@@c"):
            head, _, rest = line[3:].partition(" ")
            vals[head] = rest.strip()
        elif line.startswith("@@S1 "):
            s1 = cpu_totals(line[5:])
        elif line.startswith("@@S2 "):
            s2 = cpu_totals(line[5:])
    return vals, ((s1, s2) if (s1 and s2) else None)


PROC_LINES = [
    'echo "@@S1 $(head -1 /proc/stat)"',
    'for p in /proc/[0-9]*; do echo "@@P $(cat $p/stat 2>/dev/null)"; done',
    'sleep 1',
    'echo "@@S2 $(head -1 /proc/stat)"',
    'for p in /proc/[0-9]*; do echo "@@Q $(cat $p/stat 2>/dev/null)"; done',
]
PROC_CMD = "; ".join(PROC_LINES)


def parse_proc_stat(text):
    lp, rp = text.find("("), text.rfind(")")
    if lp < 0 or rp < 0:
        return None
    pid = text[:lp].strip()
    name = text[lp + 1:rp]
    rest = text[rp + 2:].split()
    if len(rest) < 22:
        return None
    return pid, name, rest[0], num(rest[11]) + num(rest[12]), num(rest[21])


def parse_proc_output(raw):
    s1 = s2 = None
    a, b = {}, {}
    for line in raw.splitlines():
        if line.startswith("@@S1 "):
            s1 = cpu_totals(line[5:])
        elif line.startswith("@@S2 "):
            s2 = cpu_totals(line[5:])
        elif line.startswith("@@P "):
            info = parse_proc_stat(line[4:])
            if info:
                a[info[0]] = info
        elif line.startswith("@@Q "):
            info = parse_proc_stat(line[4:])
            if info:
                b[info[0]] = info
    dtotal = (s2[0] - s1[0]) if (s1 and s2) else 0
    rows = []
    for pid, (_, name, state, ticks, rss) in b.items():
        old = a.get(pid)
        dp = ticks - old[3] if old else 0
        cpu = dp * 100.0 / dtotal if dtotal > 0 and dp >= 0 else 0.0
        rows.append({"pid": pid, "name": name, "state": state, "mem": rss * 4 / 1024.0, "cpu": cpu})
    return rows


def mem_from_meminfo(text):
    vals = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            vals[parts[0][:-1]] = num(parts[1])
    return vals.get("MemTotal", 0) // 1024, vals.get("MemAvailable", 0) // 1024


def parse_df_mb(line):
    f = line.split()
    if len(f) >= 4:
        return num(f[2]) // 1024, num(f[1]) // 1024
    return None


def split_target(host, port):
    host = host.strip().replace(" ", "")
    if ":" in host:
        h, _, p = host.rpartition(":")
        if p.isdigit():
            host, port = h, p
    return host, port


def parse_pkgs(text):
    return [l.strip()[len("package:"):] for l in text.splitlines() if l.strip().startswith("package:")]


def unique_name(base, existing):
    if base not in existing:
        return base
    n = 2
    while f"{base} ({n})" in existing:
        n += 1
    return f"{base} ({n})"


def detect_pc_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# ---------------------------------------------------------------- файлы и настройки
def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    S = merge(json.loads(json.dumps(DEFAULT_SETTINGS)), data)
    migrate_settings(S, SCRIPTS_DIR)
    return S


def save_settings(s):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(s, fh, ensure_ascii=False, indent=2)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def load_json_folder(folder):
    out = []
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(".json"):
            try:
                with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                    d = json.load(fh)
                d["file"] = fn
                out.append(d)
            except (OSError, ValueError):
                pass
    return out


def run(args, timeout=30, data=None):
    kw = {"input": data} if data is not None else {"stdin": subprocess.DEVNULL}
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WIN, **kw)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except FileNotFoundError:
        return -1, "", f"Не найден файл: {args[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", "Превышено время ожидания"


# ---------------------------------------------------------------- API для скриптов
class ScriptStop(Exception):
    """Поднимается, когда пользователь нажал «Остановить»."""


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


# ---------------------------------------------------------------- виджеты
def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class FlowFrame(ttk.Frame):
    """Контейнер: дочерние элементы переносятся на новую строку, когда не хватает ширины."""

    def __init__(self, master, gap=6, **kw):
        super().__init__(master, **kw)
        self.gap = gap
        self.items = []
        self.bind("<Configure>", lambda e: self.after_idle(self.relayout))

    def add(self, widget):
        self.items.append(widget)
        self.after_idle(self.relayout)
        return widget

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []
        self.configure(height=1)

    def relayout(self):
        self.items = [w for w in self.items if w.winfo_exists()]
        sizes = [(w.winfo_reqwidth(), w.winfo_reqheight()) for w in self.items]
        pos, total = flow_layout(sizes, self.winfo_width(), self.gap)
        for w, (x, y) in zip(self.items, pos):
            w.place(x=x, y=y)
        self.configure(height=max(total, 1))

class ButtonPanel(ttk.Frame):
    """Панель кнопок в виде равномерной сетки: 2 колонки, одинаковая ширина кнопок."""
    def __init__(self, master, columns=2, gap=8, **kw):
        super().__init__(master, **kw)
        self.columns = columns
        self.gap = gap
        self.items = []
        for c in range(columns):
            self.grid_columnconfigure(c, weight=1, uniform="btn")

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []

    def add(self, widget):
        row = len(self.items) // self.columns
        col = len(self.items) % self.columns
        widget.grid(row=row, column=col, sticky="we", padx=self.gap // 2, pady=self.gap // 2)
        self.items.append(widget)
        return widget


class ScrollFrame(ttk.Frame):
    """Прокручиваемая область: если окно маленькое, всё остаётся доступным."""

    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, ev):
        self.canvas.yview_scroll(int(-ev.delta / 120), "units")


class Spark(tk.Canvas):
    """График последних значений в процентах."""

    def __init__(self, master, color, w=280, h=64):
        super().__init__(master, width=w, height=h, bg=C["term"], highlightthickness=0)
        self.color, self.w, self.h = color, w, h

    def draw(self, values, label=""):
        self.delete("all")
        for pct in (25, 50, 75):
            y = self.h - (pct / 100) * (self.h - 6) - 3
            self.create_line(0, y, self.w, y, fill="#1d3247")
        vals = [v for v in values if v is not None]
        if len(vals) >= 2:
            step = self.w / max(1, len(values) - 1)
            pts = []
            for i, v in enumerate(values):
                v = 0 if v is None else v
                pts += [i * step, self.h - (max(0, min(100, v)) / 100) * (self.h - 6) - 3]
            self.create_line(*pts, fill=self.color, width=2, smooth=True)
        if label:
            self.create_text(self.w - 6, 4, anchor="ne", fill=C["text"], text=label, font=("Segoe UI", 9, "bold"))


class Gauge(tk.Canvas):
    """Шкала занятости памяти: цвет меняется от зелёного к красному."""

    def __init__(self, master, title):
        super().__init__(master, width=330, height=58, bg=C["bg"], highlightthickness=0)
        self.title = title

    def draw(self, used, total):
        self.delete("all")
        if not total:
            self.create_text(4, 4, anchor="nw", fill=C["muted"], text=f"{self.title}: нет данных",
                             font=("Segoe UI", 9))
            return
        pct = min(100.0, used * 100.0 / total)
        color = C["ok"] if pct < 70 else (C["warn"] if pct < 90 else C["err"])
        self.create_text(4, 2, anchor="nw", fill=C["text"], font=("Segoe UI", 9, "bold"),
                         text=f"{self.title}: {used} из {total} МБ  ({pct:.0f}%)")
        self.create_rectangle(4, 28, 326, 50, fill=C["panel"], outline=C["border"])
        self.create_rectangle(4, 28, 4 + 322 * pct / 100, 50, fill=color, outline="")


class RemoteWindow(tk.Toplevel):
    """Окно пульта. Масштаб подстраивается под размер окна: пульт всегда весь виден."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Пульт")
        self.configure(bg=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.drag = None
        self.moved = False
        self.scale, self.ox, self.oy = 1.0, 0, 0
        head = FlowFrame(self, gap=4)
        head.pack(fill="x", padx=6, pady=6)
        self.box = ttk.Combobox(head, textvariable=app.remote_var, state="readonly", width=28)
        head.add(self.box)
        self.box.bind("<<ComboboxSelected>>", lambda e: app.remote_select(app.remote_var.get()))
        self.edit_btn = ttk.Button(head, text="Редактировать: " + ("вкл" if app.remote_edit else "выкл"),
                                   command=app.remote_toggle_edit)
        head.add(self.edit_btn)
        head.add(ttk.Button(head, text="+ Кнопка", command=app.remote_add_button))
        head.add(ttk.Button(head, text="Новый пульт", command=app.remote_new))
        head.add(ttk.Button(head, text="Копия", command=app.remote_copy))
        head.add(ttk.Button(head, text="Переименовать", command=app.remote_rename))
        head.add(ttk.Button(head, text="Удалить пульт", command=app.remote_delete))
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self.close())
        # Ensure initial draw after window is laid out
        self.after(50, self._initial_draw)

    def _initial_draw(self):
        """Принудительная перерисовка после того, как окно получило размер."""
        self.update_idletasks()
        self.draw()

    def close(self):
        self.app.remote_win = None
        self.destroy()

    def to_logical(self, x, y):
        return (x - self.ox) / self.scale, (y - self.oy) / self.scale

    def draw(self):
        cw, ch = max(self.canvas.winfo_width(), 50), max(self.canvas.winfo_height(), 50)
        self.scale = fit_scale(cw, ch)
        self.ox = (cw - REMOTE_W * self.scale) / 2
        self.oy = (ch - REMOTE_H * self.scale) / 2
        s, ox, oy = self.scale, self.ox, self.oy
        self.canvas.delete("all")
        round_rect(self.canvas, ox + 10 * s, oy + 10 * s, ox + (REMOTE_W - 10) * s, oy + (REMOTE_H - 10) * s,
                   34 * s, fill=C["body"], outline=C["border"], width=2)
        if self.app.remote_edit:
            self.canvas.create_text(ox + REMOTE_W * s / 2, oy + 22 * s,
                                    text="РЕДАКТИРОВАНИЕ: тяните кнопку, нажмите для настройки",
                                    fill=C["warn"], font=("Segoe UI", max(7, int(8 * s))))
        for b in self.app.current_remote_buttons():
            r = b["r"] * s
            cx, cy = ox + b["x"] * s, oy + b["y"] * s
            outline = C["warn"] if self.app.remote_edit else "#3c5a7d"
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=b.get("color", KEY_COL),
                                    outline=outline, width=2)
            self.canvas.create_text(cx, cy, text=b["label"], fill=C["text"],
                                    font=("Segoe UI", max(6, int(9 * s)), "bold"))

    def _press(self, ev):
        # Ensure canvas has focus for click events
        self.canvas.focus_set()
        lx, ly = self.to_logical(ev.x, ev.y)
        buttons = self.app.current_remote_buttons()
        if not buttons:
            return
        idx = hit_button(buttons, lx, ly)
        self.drag = idx
        self.moved = False
        if idx is not None and not self.app.remote_edit:
            self.app.remote_press(buttons[idx])

    def _motion(self, ev):
        if self.drag is None or not self.app.remote_edit:
            return
        lx, ly = self.to_logical(ev.x, ev.y)
        b = self.app.current_remote_buttons()[self.drag]
        b["x"] = min(max(lx, 20), REMOTE_W - 20)
        b["y"] = min(max(ly, 30), REMOTE_H - 20)
        self.moved = True
        self.draw()

    def _release(self, ev):
        if self.drag is None:
            return
        idx = self.drag
        self.drag = None
        if self.app.remote_edit:
            if self.moved:
                save_settings(self.app.S)
            elif idx is not None:
                self.app.remote_button_dialog(idx)
        self.draw()


# ---------------------------------------------------------------- приложение
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} {VERSION}")
        self.geometry("1280x880")
        self.minsize(900, 600)
        self.configure(bg=C["bg"])
        self.S = load_settings()
        save_settings(self.S)
        self.jobs = queue.Queue()
        self.script_q = queue.Queue()
        self.stop_ev = threading.Event()
        self.script_running = False
        self.script_buf = []
        self.app_rows = []
        self.sort_key, self.sort_rev = "mem", True
        self.serial = tk.StringVar()
        self.status = tk.StringVar(value="Не подключено")
        self.devinfo = tk.StringVar(value="")
        self.hist_list, self.hist_i = [], 0
        self.cache = {"props": [], "pkgs": [], "bins": [], "dirs": {}, "pending": set()}
        self.sug_visible = False
        self.bar_frames = {}
        self.card_hist = {}
        self.state_busy = False
        self.proc_busy = False
        self.proc_rows = []
        self.proc_sort = ("cpu", True)
        self.remote_edit = False
        self.remote_win = None
        self.remote_var = tk.StringVar(value=self.S["remote_current"])

        self._style()
        self._build()
        self.render_bar("tools")
        self.render_bar("console")
        self.render_bar("scripts")
        self.render_bar("apps")
        self.render_cards()
        self.reload_programs_buttons()
        self.reload_apks()
        if not os.path.isfile(ADB) and not shutil.which("adb"):
            self.after(200, lambda: self.log("adb не найден. Переустановите программу через установщик."))
        self.refresh_devices()
        self.after(80, self._poll)
        self.after(1000, self._auto_tick)
        self.after(3000, self.check_connection)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------ фон и журнал
    def bg(self, job, done):
        def worker():
            try:
                res = job()
            except Exception as e:  # noqa: BLE001
                res = e
            self.jobs.put((done, res))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        self._drain_script()
        try:
            while True:
                done, res = self.jobs.get_nowait()
                try:
                    done(res)
                except Exception as e:  # noqa: BLE001
                    self.log(f"Ошибка интерфейса: {e}")
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _drain_script(self):
        try:
            while True:
                text = self.script_q.get_nowait()
                self.script_buf.append(text)
                self.script_out.insert("end", text)
                self.script_out.see("end")
        except queue.Empty:
            pass

    def log(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.out.insert("end", f"[{stamp}] {text}\n")
        self.out.see("end")

    def dev(self):
        s = self.serial.get().strip()
        if not s:
            self.log("Сначала подключите устройство")
            return None
        return s

    def show_text(self, title, text):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("820x520")
        win.configure(bg=C["bg"])
        win.transient(self)
        box = scrolledtext.ScrolledText(win, bg=C["term"], fg=C["text"], font=("Consolas", 10), wrap="word")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        box.insert("1.0", text if text.strip() else "(пустой ответ)")
        bar = FlowFrame(win, gap=6)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        bar.add(ttk.Button(bar, text="Копировать", command=lambda: self.copy_text(text)))
        bar.add(ttk.Button(bar, text="Закрыть", style="Accent.TButton", command=win.destroy))
        win.bind("<Escape>", lambda e: win.destroy())

    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("Скопировано в буфер обмена")

    def popup(self, items, x, y):
        m = tk.Menu(self, tearoff=0, bg=C["panel"], fg=C["text"], activebackground=C["sel"])
        if not items:
            m.add_command(label="(пусто)", state="disabled")
        for label, cmd in items:
            m.add_command(label=label, command=cmd)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    # ------------------------------------------------ стиль и горячие клавиши
    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        # Глубокий тёмный фон, приглушённые акценты
        st.configure(".", background=C["bg"], foreground=C["text"],
                     fieldbackground=C["panel"], bordercolor=C["border"],
                     lightcolor=C["border"], darkcolor=C["border"])
        st.configure("TFrame", background=C["bg"])
        st.configure("TLabel", background=C["bg"], foreground=C["text"])
        st.configure("TButton", background=C["panel"], foreground=C["text"], padding=(12, 8),
                     borderwidth=1, relief="flat")
        st.map("TButton", background=[("active", C["sel"]), ("pressed", C["accent"])],
               foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
        st.configure("Accent.TButton", background=C["accent"], foreground="#0b1a2b",
                     padding=(12, 8), borderwidth=0, relief="flat")
        st.map("Accent.TButton", background=[("active", "#7bbcf5"), ("pressed", C["accent"])])
        st.configure("TEntry", fieldbackground=C["panel"], foreground=C["text"],
                     insertcolor=C["text"], borderwidth=1, relief="flat")
        st.configure("TCombobox", fieldbackground=C["panel"], foreground=C["text"],
                     background=C["panel"], arrowcolor=C["text"], borderwidth=1, relief="flat")
        st.map("TCombobox", fieldbackground=[("readonly", C["panel"])],
               foreground=[("readonly", C["text"])])
        st.configure("TNotebook", background=C["bar"], borderwidth=0)
        st.configure("TNotebook.Tab", background=C["bar"], foreground=C["muted"],
                     padding=(16, 10), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", C["bg"])],
               foreground=[("selected", "#ffffff")])
        st.configure("Treeview", background=C["panel"], fieldbackground=C["panel"],
                     foreground=C["text"], rowheight=26, borderwidth=0)
        st.map("Treeview", background=[("selected", C["sel"])],
               foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=C["bar"], foreground=C["text"],
                     font=("Segoe UI", 9, "bold"), borderwidth=0, relief="flat")
        st.map("Treeview.Heading", background=[("active", C["sel"])])
        st.configure("TCheckbutton", background=C["bg"], foreground=C["text"])
        st.map("TCheckbutton", background=[("active", C["bg"])])
        st.configure("TLabelframe", background=C["bg"], bordercolor=C["border"],
                     borderwidth=1, relief="solid")
        st.configure("TLabelframe.Label", background=C["bg"], foreground=C["muted"],
                     font=("Segoe UI", 9, "bold"))
        self.bind_class("TEntry", "<Control-KeyPress>", self._ctrl_keys)
        self.bind_class("TCombobox", "<Control-KeyPress>", self._ctrl_keys)
        self.bind_class("Text", "<Control-KeyPress>", self._ctrl_keys)

    def _ctrl_keys(self, ev):
        if ev.keysym.lower() in ("v", "c", "x", "a"):
            return None
        w = ev.widget
        if ev.keycode == 86:
            w.event_generate("<<Paste>>")
        elif ev.keycode == 67:
            w.event_generate("<<Copy>>")
        elif ev.keycode == 88:
            w.event_generate("<<Cut>>")
        elif ev.keycode == 65:
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.selection_range(0, "end")
        else:
            return None
        return "break"

    # ------------------------------------------------ интерфейс
    def _build(self):
        head = tk.Frame(self, bg=C["head"])
        head.pack(fill="x")
        tk.Label(head, text=APP_TITLE, bg=C["head"], fg="#ffffff",
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        row = tk.Frame(head, bg=C["head"])
        row.pack(fill="x", padx=12, pady=(0, 8))
        self.status_lbl = tk.Label(row, textvariable=self.status, bg=C["head"], fg=C["err"],
                                   font=("Segoe UI", 10, "bold"))
        self.status_lbl.pack(side="left")
        tk.Label(row, textvariable=self.devinfo, bg=C["head"], fg=C["muted"], font=("Segoe UI", 10)).pack(side="right")

        bar = FlowFrame(self, gap=6)
        bar.pack(fill="x", padx=8, pady=6)
        bar.add(ttk.Label(bar, text="IP или URL:"))
        self.host_var = tk.StringVar()
        self.host_var.trace_add("write", self._fix_host)
        bar.add(ttk.Entry(bar, textvariable=self.host_var, width=28))
        bar.add(ttk.Label(bar, text="Порт:"))
        self.port_var = tk.StringVar(value="5555")
        self.port_var.trace_add("write", self._fix_port)
        bar.add(ttk.Entry(bar, textvariable=self.port_var, width=7))
        bar.add(ttk.Button(bar, text="Подключить", style="Accent.TButton", command=self.connect))
        bar.add(ttk.Button(bar, text="Отключить", command=self.disconnect))
        bar.add(ttk.Button(bar, text="Сопрячь", command=self.pair_dialog))
        self.hist_btn = bar.add(ttk.Button(bar, text="История ▾", command=self.history_menu))
        self.fav_btn = bar.add(ttk.Button(bar, text="Избранное ▾", command=self.favorites_menu))
        bar.add(ttk.Label(bar, text="Устройство:"))
        self.dev_box = ttk.Combobox(bar, textvariable=self.serial, width=26, state="readonly")
        bar.add(self.dev_box)
        self.dev_box.bind("<<ComboboxSelected>>", lambda e: self.device_info())
        bar.add(ttk.Button(bar, text="Обновить", command=self.refresh_devices))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        self.nb = nb
        self.tab_apps(nb)
        self.tab_tools(nb)
        self.tab_console(nb)
        self.tab_scripts(nb)
        self.tab_settings(nb)
        self.tab_logs(nb)
        self.tab_about(nb)
        nb.bind("<<NotebookTabChanged>>", lambda e: self.on_main_tab())

    def tab_logs(self, nb):
        """Журнал программы: все сообщения о действиях. Можно копировать и очистить."""
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="Логи")
        Tooltip(f, "Журнал действий программы: копировать или очистить")
        row = FlowFrame(f, gap=6)
        row.pack(fill="x")
        row.add(ttk.Button(row, text="Копировать всё", command=lambda: self.copy_text(self.out.get("1.0", "end").rstrip())))
        row.add(ttk.Button(row, text="Очистить", command=lambda: self.out.delete("1.0", "end")))
        self.out = scrolledtext.ScrolledText(f, bg=C["term"], fg=C["text"], insertbackground=C["text"],
                                             font=("Consolas", 10), relief="flat", wrap="word")
        self.out.pack(fill="both", expand=True, pady=(6, 0))

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

        self.bg(job, done)

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
            ttk.Button(btns, text="Сохранить", command=save).pack(side="left", padx=4)
            if idx is not None:
                ttk.Button(btns, text="Удалить", command=delete).pack(side="left", padx=4)
            ttk.Button(btns, text="Отмена", command=win.destroy).pack(side="left", padx=4)
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

    def ask_multiline(self, title, name, text, hint="", can_delete=False):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("660x480")
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)
        nv = tk.StringVar(value=name)
        ttk.Label(frm, text="Название кнопки").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=nv, width=48).grid(row=0, column=1, sticky="we", padx=6, pady=3)
        ttk.Label(frm, text="Команда / код").grid(row=1, column=0, sticky="nw")
        txt = scrolledtext.ScrolledText(frm, height=12, bg=C["term"], fg=C["text"], font=("Consolas", 10),
                                        relief="flat", insertbackground=C["text"], undo=True)
        txt.grid(row=1, column=1, sticky="nsew", padx=6, pady=3)
        txt.insert("1.0", text)
        ttk.Label(frm, text=hint, foreground=C["muted"], wraplength=520).grid(row=2, column=0, columnspan=2,
                                                                              sticky="w", pady=6)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(1, weight=1)
        result = {}

        def ok():
            result["v"] = (nv.get().strip(), txt.get("1.0", "end").rstrip("\n"))
            win.destroy()

        def delete():
            result["v"] = "delete"
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=3, column=0, columnspan=2, sticky="we")
        if can_delete:
            bar.add(ttk.Button(bar, text="Удалить", command=delete))
        bar.add(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=ok))
        bar.add(ttk.Button(bar, text="Отмена", command=win.destroy))
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.wait_window()
        return result.get("v")

    def run_popup_cmd(self, label, cmd):
        s = self.dev()
        if not s or not cmd.strip():
            return
        self.log(f"Выполняется: {label}...")
        self.bg(lambda: run([ADB, "-s", s, "shell", cmd], 120), lambda res: self.show_result(label, res))

    def show_result(self, label, res):
        if isinstance(res, Exception):
            self.show_text(label, f"Ошибка: {res}")
            return
        rc, out, err = res
        text = (out + err).rstrip()
        self.log(f"{label}: код {rc}")
        self.show_text(f"{label} (код {rc})", text if text else "(команда выполнилась, вывода нет)")

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
        top.add(ttk.Button(top, text="Обновить список", command=self.load_apps))
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
        ttk.Button(pres_row, text="Загрузить пресет", command=self.preset_load).pack(side="left", padx=(0, 6))
        ttk.Button(pres_row, text="Сохранить выбранные как пресет", command=self.preset_save).pack(side="left")

        # --- строка 2: установка APK
        apk_row = ttk.Frame(pres)
        apk_row.pack(fill="x", pady=(0, 8))
        ttk.Label(apk_row, text="APK из папки apk:").pack(side="left", padx=(0, 6))
        self.apk_var = tk.StringVar()
        self.apk_box = ttk.Combobox(apk_row, textvariable=self.apk_var, state="readonly", width=28)
        self.apk_box.pack(side="left", padx=(0, 6))
        ttk.Button(apk_row, text="Установить", style="Accent.TButton", command=self.install_apk).pack(side="left", padx=(0, 6))
        ttk.Button(apk_row, text="Добавить APK в папку", command=self.add_apk).pack(side="left")

        # --- строка 3: экспорт
        exp_row = ttk.Frame(pres)
        exp_row.pack(fill="x")
        ttk.Button(exp_row, text="Экспорт списка (CSV)", command=self.export_csv).pack(side="left")

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
            if isinstance(res, Exception):
                self.show_text(name, f"Ошибка: {res}")
            else:
                self.show_text(name, res)
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
        bar.add(ttk.Button(bar, text="Удалить", command=delete))
        bar.add(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=ok))
        bar.add(ttk.Button(bar, text="Отмена", command=win.destroy))
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
        ttk.Button(row_touch, text="Вкл. на устройстве", width=15,
                   command=lambda: self._set_show_touches(True)).pack(side="left", padx=4)
        ttk.Checkbutton(sc, text="Выключить экран устройства", variable=self.sc_off).grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Button(sc, text="Запустить scrcpy", style="Accent.TButton", command=self.scrcpy_start).grid(
            row=7, column=0, columnspan=2, sticky="we", pady=(8, 0))

        ext = ttk.LabelFrame(grid, text="Внешние программы и пульт", padding=8)
        grid.add(ext)
        ttk.Button(ext, text="Vysor", command=self.vysor_start).pack(fill="x", pady=2)
        ttk.Button(ext, text="Открыть пульт", style="Accent.TButton", command=self.open_remote).pack(fill="x", pady=2)
        self.prog_frame = ttk.Frame(ext)
        self.prog_frame.pack(fill="x")
        ttk.Button(ext, text="Добавить программу...", command=self.add_program).pack(fill="x", pady=(6, 0))

        ctl = ttk.LabelFrame(grid, text="Управление", padding=8)
        grid.add(ctl)
        ttk.Button(ctl, text="Скриншот", command=self.screenshot).pack(fill="x", pady=2)
        ttk.Button(ctl, text="Перезагрузка", command=lambda: self.reboot("")).pack(fill="x", pady=2)
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
            bar.add(ttk.Button(bar, text="Удалить кнопку", command=delete))
        bar.add(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=save))
        bar.add(ttk.Button(bar, text="Отмена", command=win.destroy))
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

    # --- показатели состояния (редактируемые, как в диспетчере задач)
    def _build_state(self, f):
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        self.model_lbl = top.add(ttk.Label(top, text="-", font=("Segoe UI", 11, "bold")))
        self.auto_state = tk.BooleanVar(value=True)
        top.add(ttk.Checkbutton(top, text="Обновлять каждые 3 с", variable=self.auto_state))
        top.add(ttk.Button(top, text="Обновить сейчас", command=self.refresh_state))
        top.add(ttk.Button(top, text="+ Показатель", style="Accent.TButton", command=self.card_add))
        top.add(ttk.Button(top, text="Сбросить к стандартным", command=self.cards_reset))
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
        bar.add(ttk.Button(bar, text="Сохранить", style="Accent.TButton", command=ok))
        bar.add(ttk.Button(bar, text="Отмена", command=win.destroy))
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

        def job():
            _, out, _ = run([ADB, "-s", s, "shell", batch], 60)
            return parse_state_batch(out)

        def done(res):
            self.state_busy = False
            if isinstance(res, Exception):
                self.log(f"Состояние: {res}")
                return
            self._show_state(cards, *res)

        self.bg(job, done)

    def _show_state(self, cards, vals, snap):
        for card in cards:
            cid = card["id"]
            if cid not in self.card_widgets:
                continue
            val_lbl, spark, color = self.card_widgets[cid]
            pct, text = parse_card(card, vals.get(cid, ""), snap)
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

    def _build_procs(self, f):
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        top.add(ttk.Label(top, text="Сортировка:"))
        for label, key in [("по нагрузке CPU", "cpu"), ("по памяти", "mem"), ("по имени", "name"), ("по PID", "pid")]:
            top.add(ttk.Button(top, text=label, command=functools.partial(self.proc_sort_by, key)))
        self.proc_filter = tk.StringVar()
        self.proc_filter.trace_add("write", lambda *a: self.fill_procs())
        top.add(ttk.Entry(top, textvariable=self.proc_filter, width=22))
        top.add(ttk.Label(top, text="фильтр по имени"))
        self.auto_proc = tk.BooleanVar(value=False)
        top.add(ttk.Checkbutton(top, text="авто (каждые 3 с)", variable=self.auto_proc))
        top.add(ttk.Button(top, text="Обновить", command=self.refresh_procs))
        top.add(ttk.Button(top, text="Копировать выбранные", command=self.proc_copy))
        top.add(ttk.Button(top, text="Завершить выбранный", command=self.kill_selected))
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
            ttk.Button(self.prog_frame, text=prog.get("name", prog["file"]),
                       command=functools.partial(self.program_run, prog)).pack(fill="x", pady=1)

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
        ttk.Button(row, text="Выполнить", style="Accent.TButton", command=self.shell_run).pack(side="left")
        ttk.Button(row, text="Очистить", command=lambda: self.console.delete("1.0", "end")).pack(side="left", padx=4)
        ttk.Button(row, text="Открыть окно", command=self.open_console_window).pack(side="left", padx=4)
        ttk.Button(row, text="Kill PID", command=self.kill_clipboard_pid).pack(side="left", padx=4)
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
        self._stream_stop_btn = ttk.Button(
            self.cmd_entry.master, text="■ Стоп",
            command=stop_streaming, style="Accent.TButton"
        )
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

    # ------------------------------------------------ вкладка «Скрипты» (Python)
    def tab_scripts(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="Скрипты")
        Tooltip(f, "Запуск Python-скриптов, результат в окне, остановка")
        top = FlowFrame(f, gap=6)
        top.pack(fill="x")
        top.add(ttk.Button(top, text="■ Остановить", command=self.stop_script))
        top.add(ttk.Button(top, text="Открыть папку скриптов", command=self.open_scripts_folder))
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
        rb.add(ttk.Button(rb, text="Копировать результат",
                          command=lambda: self.copy_text(self.script_out.get("1.0", "end").rstrip())))
        rb.add(ttk.Button(rb, text="Очистить результат", command=lambda: self.script_out.delete("1.0", "end")))
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

    def run_script(self, item):
        name = item.get("name", "Скрипт")
        if self.script_running:
            self.log("Скрипт уже выполняется. Дождитесь окончания или нажмите «Остановить»")
            return
        s = self.serial.get().strip()
        if not s:
            self.log("Сначала подключите устройство: скрипты работают с выбранным устройством")
            return
        path = P("scripts", item.get("file", ""))
        if not os.path.isfile(path):
            self.log(f"Файл скрипта не найден: {path}")
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

        # Создаём модуль adb с привязанной shell функцией
        import types
        adb_module = types.ModuleType("adb")
        adb_module.shell = api.shell
        # Кладем в namespace и sys.modules, чтобы import adb работал
        namespace = {"adb": adb_module, "print": script_print, "sleep": api.sleep,
                     "time": time, "json": json, "re": re, "os": os}
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

    # ------------------------------------------------ вкладка «Настройки»
    def tab_settings(self, nb):
        sf = ScrollFrame(nb)
        nb.add(sf, text="Настройки")
        Tooltip(sf, "IP ПК, путь Vysor, экспорт/импорт настроек и кнопок")
        f = sf.inner
        f.configure(padding=12)
        self.set_pc_ip = tk.StringVar(value=self.S.get("pc_ip", ""))
        ttk.Label(f, text="IP этого ПК (пусто = автоопределение)").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.set_pc_ip, width=24).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Текущий адрес: " + self.pc_ip()).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        ttk.Label(f, text="Путь к Vysor").grid(row=2, column=0, sticky="w")
        self.set_vysor = tk.StringVar(value=self.S.get("vysor_path", ""))
        ttk.Entry(f, textvariable=self.set_vysor, width=60).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Button(f, text="Сохранить настройки", style="Accent.TButton", command=self.save_settings_ui).grid(
            row=3, column=0, sticky="w", pady=12)
        ttk.Button(f, text="Экспорт всего в один файл...", command=self.export_bundle).grid(row=4, column=0, sticky="w", pady=4)
        ttk.Button(f, text="Импорт из файла...", command=self.import_bundle).grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(f, text="В экспорт входят: кнопки, действия над приложениями, пульты, показатели состояния, "
                          "тексты всех скриптов из папки scripts, настройки scrcpy и программы-кнопки. "
                          "Адрес ПК, путь к Vysor и история не экспортируются.",
                  foreground=C["muted"], wraplength=760).grid(row=5, column=0, columnspan=2, sticky="w", pady=8)

    def save_settings_ui(self):
        self.S["pc_ip"] = self.set_pc_ip.get().strip()
        self.S["vysor_path"] = self.set_vysor.get().strip()
        save_settings(self.S)
        self.log("Настройки сохранены")

    def export_bundle(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="android_tv_export.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        bundle = make_bundle(self.S, SCRIPTS_DIR, load_json_folder(P("programs")))
        write_json(path, bundle)
        self.log(f"Экспортировано: {path} (скриптов: {len(bundle['scripts'])})")

    def import_bundle(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                bundle = json.load(fh)
            self.S, n, programs = apply_bundle(bundle, self.S, SCRIPTS_DIR)
        except (OSError, ValueError) as e:
            self.log(f"Не удалось импортировать: {e}")
            return
        for prog in programs:
            fn = prog.pop("file", slug(prog.get("name", "program")) + ".json")
            write_json(P("programs", fn), prog)
        save_settings(self.S)
        for bid in ("tools", "console", "scripts", "apps"):
            self.render_bar(bid)
        self.render_cards()
        self.remote_refresh_list()
        self.remote_var.set(self.S.get("remote_current", ""))
        self.remote_redraw()
        self.reload_programs_buttons()
        self.log(f"Импорт выполнен: скриптов в файле {n}")

    # ------------------------------------------------ вкладка «О программе»
    def tab_about(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="О программе")
        Tooltip(f, "Версия, пути к adb/scrcpy, папка программы")
        ttk.Label(f, text=f"{APP_TITLE} {VERSION}", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Папка программы: {BASE}").pack(anchor="w", pady=4)
        ttk.Label(f, text=f"ADB: {ADB}").pack(anchor="w")
        ttk.Label(f, text=f"scrcpy: {SCRCPY}").pack(anchor="w")
        btn = ttk.Button(f, text="Открыть папку программы", command=lambda: os.startfile(BASE) if os.name == "nt" else None)
        Tooltip(btn, "Открыть папку с программой в проводнике")
        btn.pack(anchor="w", pady=12)

    # ------------------------------------------------ общие диалоги
    def ask_fields(self, title, names, defaults=None):
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=C["bg"])
        win.transient(self)
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both")
        vars_ = {}
        for i, n in enumerate(names):
            ttk.Label(frm, text=n).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=(defaults or {}).get(n, ""))
            ttk.Entry(frm, textvariable=v, width=44).grid(row=i, column=1, padx=6, pady=3)
            vars_[n] = v
        result = {}

        def ok():
            result.update({k: v.get() for k, v in vars_.items()})
            win.destroy()

        bar = FlowFrame(frm, gap=6)
        bar.grid(row=len(names), column=0, columnspan=2, sticky="we", pady=(10, 0))
        bar.add(ttk.Button(bar, text="Отмена", command=win.destroy))
        bar.add(ttk.Button(bar, text="OK", style="Accent.TButton", command=ok))
        win.bind("<Return>", lambda e: ok())
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.wait_window()
        return result or None

    # ------------------------------------------------ выход
    def on_close(self):
        self.stop_ev.set()
        save_settings(self.S)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
'''


# ================================================================ установщик
class InstallError(Exception):
    pass


def resolve_install_dir(chosen):
    """Выбранная папка. Если это не папка Android-manager, программа ставится внутрь неё."""
    chosen = os.path.abspath(chosen)
    if os.path.basename(chosen).lower() == APP_EXE.lower():
        return chosen
    return os.path.join(chosen, APP_EXE)


def check_writable(folder):
    """Программа пишет settings.json рядом с exe, поэтому папка должна быть доступна для записи."""
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".android_write_test")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
    except OSError as e:
        raise InstallError(f"Нет прав на запись в папку {folder} ({e}). "
                           "Выберите другую папку, например в профиле пользователя.")


def special_folder(csidl):
    """Путь к системной папке (рабочий стол, меню «Пуск») через Windows API."""
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def check_environment(log):
    if os.name != "nt":
        raise InstallError("Установщик рассчитан на Windows.")
    if sys.version_info < (3, 8):
        raise InstallError("Нужен Python 3.8 или новее. Сейчас: " + sys.version.split()[0])
    log(f"Windows, Python {sys.version.split()[0]}")


def download(url, dest, log):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        last_step = -1
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                step = done * 10 // total
                if step != last_step:
                    log(f"  загрузка {step * 10}%")
                    last_step = step
    log("  загрузка завершена")


def find_dir_with(root, filename):
    for dirpath, _, files in os.walk(root):
        if filename in files:
            return dirpath
    raise InstallError(f"В архиве нет файла {filename}")


def install_archive(url, exe_name, target, log):
    tmp = tempfile.mkdtemp(prefix="android_")
    try:
        zip_path = os.path.join(tmp, "pkg.zip")
        download(url, zip_path, log)
        extract = os.path.join(tmp, "x")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract)
        src = find_dir_with(extract, exe_name)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copytree(src, target)
        log(f"  установлено: {target}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scrcpy_download_url(log):
    req = urllib.request.Request(SCRCPY_API, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if "win64" in name and name.endswith(".zip"):
            log(f"  релиз scrcpy: {data.get('tag_name', '?')} ({name})")
            return asset["browser_download_url"]
    raise InstallError("На странице релиза scrcpy не найден архив win64")


def install_tools(install_dir, log):
    """adb и scrcpy ставятся в папку установки. Если уже есть - пропускаются."""
    tools = os.path.join(install_dir, "tools")
    adb_dir = os.path.join(tools, "adb")
    scr_dir = os.path.join(tools, "scrcpy")

    log("Скачивание adb (Android platform-tools)")
    if os.path.isfile(os.path.join(adb_dir, "adb.exe")):
        log("  уже установлен, пропуск")
    else:
        install_archive(PLATFORM_TOOLS_URL, "adb.exe", adb_dir, log)

    log("Скачивание scrcpy")
    if os.path.isfile(os.path.join(scr_dir, "scrcpy.exe")):
        log("  уже установлен, пропуск")
    else:
        install_archive(scrcpy_download_url(log), "scrcpy.exe", scr_dir, log)


def build_program(log, work):
    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    src = os.path.join(src_dir, APP_EXE + ".py")
    with open(src, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(PROGRAM_SRC.lstrip("\n"))

    log("Установка PyInstaller (нужен для сборки exe)")
    rc = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "pyinstaller"],
                        capture_output=True, text=True)
    if rc.returncode != 0:
        raise InstallError("Не удалось установить PyInstaller:\n" + (rc.stderr or rc.stdout)[-500:])

    log("Сборка Android-manager.exe (это займёт 1-3 минуты)")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
           "--name", APP_EXE,
           "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "build"),
           "--specpath", src_dir,
           src]
    rc = subprocess.run(cmd, capture_output=True, text=True, cwd=src_dir)
    if rc.returncode != 0:
        raise InstallError("Сборка exe не удалась:\n" + (rc.stderr or rc.stdout)[-800:])
    dist = os.path.join(work, "dist", APP_EXE)
    if not os.path.isfile(os.path.join(dist, APP_EXE + ".exe")):
        raise InstallError("Сборка не создала exe-файл")
    log("  exe собран")
    return dist


def copy_program(dist, install_dir, log):
    log(f"Копирование программы в папку: {install_dir}")
    try:
        shutil.copytree(dist, install_dir, dirs_exist_ok=True)
    except PermissionError:
        raise InstallError("Не удалось заменить файлы: программа сейчас запущена. "
                           "Закройте Android ТВ-Менеджер и повторите.")
    for folder in USER_DIRS:
        os.makedirs(os.path.join(install_dir, folder), exist_ok=True)
    log("  готово")


def make_shortcut(lnk, target, workdir, desc):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    env = dict(os.environ, ANDROID_LNK=lnk, ANDROID_TARGET=target, ANDROID_WORK=workdir, ANDROID_DESC=desc)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ANDROID_LNK);"
          "$s.TargetPath=$env:ANDROID_TARGET;$s.WorkingDirectory=$env:ANDROID_WORK;"
          "$s.Description=$env:ANDROID_DESC;$s.IconLocation=$env:ANDROID_TARGET+',0';$s.Save()")
    rc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                        capture_output=True, env=env)
    if rc.returncode != 0:
        raise InstallError(rc.stderr.decode("utf-8", "replace")[:300] or "ошибка PowerShell")


def create_shortcuts(install_dir, log):
    log("Создание ярлыков")
    target = os.path.join(install_dir, APP_EXE + ".exe")
    places = {
        "рабочий стол": special_folder(CSIDL_DESKTOPDIRECTORY),
        "меню «Пуск»": special_folder(CSIDL_PROGRAMS),
    }
    for where, folder in places.items():
        lnk = os.path.join(folder, APP_TITLE + ".lnk")
        try:
            make_shortcut(lnk, target, install_dir, APP_TITLE)
            log(f"  ярлык ({where}): {lnk}")
        except (InstallError, OSError) as e:
            log(f"  не удалось создать ярлык ({where}): {e}")


def check_adb(install_dir, log):
    adb = os.path.join(install_dir, "tools", "adb", "adb.exe")
    if not os.path.isfile(adb):
        log("ВНИМАНИЕ: adb.exe не найден, программа не сможет подключаться")
        return
    rc = subprocess.run([adb, "version"], capture_output=True, text=True)
    first = (rc.stdout or "adb работает").strip().splitlines()[0]
    log(f"Проверка adb: {first}")


def install(log, install_dir):
    """Полная установка в install_dir. Бросает InstallError при ошибке."""
    check_environment(log)
    log(f"Папка установки: {install_dir}")
    check_writable(install_dir)
    work = tempfile.mkdtemp(prefix="android_build_")
    try:
        log("== Инструменты (adb, scrcpy)")
        install_tools(install_dir, log)
        log("== Программа")
        dist = build_program(log, work)
        copy_program(dist, install_dir, log)
        log("== Ярлыки")
        create_shortcuts(install_dir, log)
        check_adb(install_dir, log)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log("")
    log(f"Установка завершена: {install_dir}")
    log("Запускайте «Android ТВ-Менеджер» с рабочего стола или из меню «Пуск».")


# ================================================================ окно установщика
class InstallerWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Установка: {APP_TITLE} {VERSION}")
        self.geometry("760x560")
        self.configure(bg="#14202e")
        self.q = queue.Queue()
        self.parent_dir = DEFAULT_PARENT
        ttk.Style(self).theme_use("clam")

        tk.Label(self, text=APP_TITLE, bg="#1e4170", fg="#ffffff", font=("Segoe UI", 16, "bold"),
                 anchor="w", padx=14, pady=10).pack(fill="x")
        pick = tk.Frame(self, bg="#14202e")
        pick.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(pick, text="Куда установить:", bg="#14202e", fg="#e6edf5",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = tk.Frame(pick, bg="#14202e")
        row.pack(fill="x", pady=4)
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(row, textvariable=self.path_var, font=("Segoe UI", 10),
                                   bg="#1e2e42", fg="#e6edf5", insertbackground="#e6edf5", relief="flat")
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.browse_btn = tk.Button(row, text="Выбрать папку...", command=self.browse, bg="#243a55",
                                    fg="#e6edf5", relief="flat", padx=12, pady=4)
        tooltip_btn(self.browse_btn, "Выбрать папку установки программы")
        self.browse_btn.pack(side="left", padx=(8, 0))
        self.path_var.trace_add("write", lambda *a: self._update_hint())
        self.hint = tk.Label(pick, text="", bg="#14202e", fg="#9fb4cc", font=("Segoe UI", 9), anchor="w",
                             justify="left", wraplength=700)
        self.hint.pack(fill="x")
        self.path_var.set(resolve_install_dir(self.parent_dir))

        self.log_box = scrolledtext.ScrolledText(self, bg="#0b121b", fg="#e6edf5", font=("Consolas", 10),
                                                 relief="flat", wrap="word", height=18)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        # Контекстное меню для копирования
        self.log_menu = tk.Menu(self, tearoff=0)
        self.log_menu.add_command(label="Копировать", command=self._copy_log_selection)
        self.log_menu.add_command(label="Копировать всё", command=self._copy_all_log)
        self.log_box.bind("<Button-3>", self._show_log_menu)
        self.btn = tk.Button(self, text="Установить",
                             font=("Segoe UI", 11, "bold"), bg="#5aa9f0",
                             fg="#0b1a2b", relief="flat", padx=24, pady=8, command=self.start)
        tooltip_btn(self.btn, "Запустить установку в выбранную папку (нужен интернет)")
        self.btn.pack(pady=(0, 12))
        self.write("Выберите папку установки (по умолчанию - профиль пользователя) и нажмите «Установить».")
        self.write("Нужен интернет. Установка занимает несколько минут.")

    def _update_hint(self):
        self.hint.config(text=f"Программа будет установлена в: {self.path_var.get().strip()}")

    def browse(self):
        chosen = filedialog.askdirectory(parent=self, initialdir=self.parent_dir,
                                         title="Выберите папку, куда установить Android ТВ-Менеджер")
        if chosen:
            self.parent_dir = chosen
            self.path_var.set(resolve_install_dir(chosen))

    def write(self, text):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def start(self):
        install_dir = self.path_var.get().strip()
        if not install_dir:
            self.write("ОШИБКА: укажите папку установки")
            return
        self.btn.config(state="disabled", text="Идёт установка...")
        self.browse_btn.config(state="disabled")
        self.path_entry.config(state="disabled")
        threading.Thread(target=self._worker, args=(os.path.abspath(install_dir),), daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, install_dir):
        try:
            install(lambda m: self.q.put(("log", m)), install_dir)
            self.q.put(("done", "ok"))
        except InstallError as e:
            self.q.put(("log", "ОШИБКА: " + str(e)))
            self.q.put(("done", "fail"))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"ОШИБКА: {e!r}"))
            self.q.put(("done", "fail"))

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.write(val)
                elif kind == "done":
                    if val == "ok":
                        self.btn.config(text="Готово", bg="#7fd68f", state="normal", command=self.destroy)
                    else:
                        self.btn.config(text="Закрыть", bg="#ff7b7b", state="normal", command=self.destroy)
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _show_log_menu(self, ev):
        try:
            self.log_menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            self.log_menu.grab_release()

    def _copy_log_selection(self):
        try:
            text = self.log_box.get("sel.first", "sel.last")
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
        except tk.TclError:
            pass

    def _copy_all_log(self):
        text = self.log_box.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)


def main():
    parser = argparse.ArgumentParser(description="Установка Android ТВ-Менеджера")
    parser.add_argument("--cli", action="store_true", help="установка без окна, в консоли")
    parser.add_argument("--dir", default=DEFAULT_PARENT,
                        help="папка, куда установить (внутри будет создана папка Android-manager)")
    args = parser.parse_args()
    if args.cli:
        try:
            install(print, resolve_install_dir(args.dir))
        except Exception as e:  # noqa: BLE001
            print("ОШИБКА:", e)
            input("Нажмите Enter для выхода...")
            sys.exit(1)
        input("Нажмите Enter для выхода...")
        return
    InstallerWindow().mainloop()


if __name__ == "__main__":
    main()

