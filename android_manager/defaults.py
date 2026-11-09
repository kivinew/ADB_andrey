# -*- coding: utf-8 -*-
"""Значения по умолчанию: пульты, показатели состояния, кнопки, настройки."""

import json

from .config import KEY_COL


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
         "max": 100,
         "cmd": 'for f in /sys/class/mpgpu/utilization /sys/class/gpu/utilization /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage; do [ -r "$f" ] && cat "$f" && break; done 2>/dev/null || echo 0'},
        {"id": "temp", "title": "Температура", "parse": "number", "idx": 0, "div": 1, "unit": "°C",
         "max": 100,
         "cmd": "dumpsys battery 2>/dev/null | grep temperature | sed 's/temperature: //'"},
        {"id": "load", "title": "Нагрузка CPU (1 мин)", "parse": "number", "idx": 0, "div": 100, "unit": "",
         "max": 100, "cmd": "cat /proc/loadavg 2>/dev/null | awk '{print $1*100}' || echo 0"},
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
