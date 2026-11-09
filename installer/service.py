# -*- coding: utf-8 -*-
"""Сценарий установки: проверки, порядок шагов, ошибки."""

import os
import shutil
import sys
import tempfile

from .build import build_program, copy_program
from .config import APP_EXE
from .errors import InstallError
from .packages import check_adb, install_tools
from .shortcuts import create_shortcuts


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


def check_environment(log):
    if os.name != "nt":
        raise InstallError("Установщик рассчитан на Windows.")
    if sys.version_info < (3, 8):
        raise InstallError("Нужен Python 3.8 или новее. Сейчас: " + sys.version.split()[0])
    log(f"Windows, Python {sys.version.split()[0]}")


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
