# -*- coding: utf-8 -*-
"""Ярлыки на рабочем столе и в меню «Пуск»."""

import ctypes
import os
import subprocess

from android_manager.config import APP_TITLE
from .config import APP_EXE, CSIDL_DESKTOPDIRECTORY, CSIDL_PROGRAMS, NO_WIN
from .service import InstallError


def special_folder(csidl):
    """Путь к системной папке (рабочий стол, меню «Пуск») через Windows API."""
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return buf.value


def make_shortcut(lnk, target, workdir, desc):
    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    env = dict(os.environ, ANDROID_LNK=lnk, ANDROID_TARGET=target, ANDROID_WORK=workdir, ANDROID_DESC=desc)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ANDROID_LNK);"
          "$s.TargetPath=$env:ANDROID_TARGET;$s.WorkingDirectory=$env:ANDROID_WORK;"
          "$s.Description=$env:ANDROID_DESC;$s.IconLocation=$env:ANDROID_TARGET+',0';$s.Save()")
    rc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                        capture_output=True, env=env,
                        stdin=subprocess.DEVNULL, creationflags=NO_WIN)
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
