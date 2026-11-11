# -*- coding: utf-8 -*-
"""Заглушка adb.shell() для запуска android_checkup.py без GUI.

Настоящий пакет python-adb (google/python-adb) не предоставляет adb.shell():
он работает через libusb. Здесь тот же интерфейс, что даёт Android manager,
но команды уходят в adb.exe.

adb.exe ищется так: переменная окружения ANDROID_ADB, затем папка установки
Android manager, затем PATH.
"""
import os
import shutil
import subprocess


def find_adb():
    """Путь к adb.exe: переменная окружения, папка установки или PATH."""
    env = os.environ.get("ANDROID_ADB")
    if env and os.path.isfile(env):
        return env
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local, "Android-manager", "tools", "adb", "adb.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "adb", "adb.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return shutil.which("adb") or "adb"


ADB_EXE = find_adb()


def shell(commands, timeout=180):
    """Выполняет команды из многострочного текста, возвращает объединённый вывод.

    Каждая строка выполняется отдельным `adb shell <cmd>`, как в COMMANDS
    из android_checkup.py.
    """
    if not (os.path.isfile(ADB_EXE) or shutil.which(ADB_EXE)):
        raise RuntimeError("adb не найден: %r. Укажите путь в ANDROID_ADB." % ADB_EXE)
    out_parts = []
    for raw in commands.strip("\n").split("\n"):
        cmd = raw.strip()
        if not cmd:
            continue
        proc = subprocess.run(
            [ADB_EXE, "shell", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        if proc.stdout:
            out_parts.append(proc.stdout)
        if proc.stderr:
            out_parts.append(proc.stderr)
    return "\n".join(out_parts)
