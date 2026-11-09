# -*- coding: utf-8 -*-
"""Сборка Android-manager.exe через PyInstaller во временной папке."""

import os
import shutil
import subprocess

from .config import APP_EXE, NO_WIN, PYTHON, USER_DIRS
from .errors import InstallError


def app_src_root():
    """Папка с пакетом android_manager: корень проекта или распакованный установщик."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_program(log, work):
    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    root = app_src_root()
    if not os.path.isdir(os.path.join(root, "android_manager")):
        raise InstallError("Не найдены исходники программы (пакет android_manager)")
    entry = os.path.join(src_dir, APP_EXE + ".py")
    with open(entry, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("from android_manager.__main__ import main\n\nmain()\n")

    log("Установка PyInstaller (нужен для сборки exe)")
    rc = subprocess.run([PYTHON, "-m", "pip", "install", "--user", "--upgrade", "pyinstaller"],
                        capture_output=True, text=True,
                        stdin=subprocess.DEVNULL, creationflags=NO_WIN)
    if rc.returncode != 0:
        raise InstallError("Не удалось установить PyInstaller:\n" + (rc.stderr or rc.stdout)[-500:])

    log("Сборка Android-manager.exe (это займёт 1-3 минуты)")
    cmd = [PYTHON, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
           "--name", APP_EXE, "--paths", root,
           "--distpath", os.path.join(work, "dist"),
           "--workpath", os.path.join(work, "build"),
           "--specpath", src_dir, entry]
    rc = subprocess.run(cmd, capture_output=True, text=True, cwd=src_dir,
                        stdin=subprocess.DEVNULL, creationflags=NO_WIN)
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
