# -*- coding: utf-8 -*-
"""Пути программы: папка установки, пользовательские каталоги, adb и scrcpy."""

import os
import shutil
import sys

from .script_shim import ADB_SHIM_SRC


# ---------------------------------------------------------------- пути
def app_dir():
    """Папка с данными программы: рядом с exe, из исходников — корень проекта."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = app_dir()


def P(*parts):
    return os.path.join(BASE, *parts)


SCRIPTS_DIR = P("scripts")


SETTINGS_PATH = P("settings.json")


def find_tool(rel_dir, exe, fallback):
    local = P("tools", rel_dir, exe)
    if os.path.isfile(local):
        return local
    return shutil.which(fallback) or fallback


ADB = find_tool("adb", "adb.exe", "adb")
SCRCPY = find_tool("scrcpy", "scrcpy.exe", "scrcpy")


def ensure_dirs():
    """Создаёт пользовательские папки рядом с программой (вызывается из bootstrap)."""
    for _d in ("apk", "programs", "scripts", "screenshots", "files"):
        os.makedirs(P(_d), exist_ok=True)


def write_adb_shim():
    """Кладёт scripts/adb.py, чтобы пользовательские скрипты могли делать import adb."""
    path = P("scripts", "adb.py")
    if os.path.isfile(path):
        return
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(ADB_SHIM_SRC)
    except OSError:
        pass
