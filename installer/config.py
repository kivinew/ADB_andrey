# -*- coding: utf-8 -*-
"""Константы установщика: имя файла, пути, URL, каталоги пользователя."""

import os
import subprocess
import sys


APP_EXE = "Android-manager"


DEFAULT_PARENT = os.path.expanduser("~")
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
SCRCPY_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
HEADERS = {"User-Agent": "Android-manager-Installer"}
NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _python_exe():
    exe = sys.executable
    if os.path.basename(exe).lower() == "pythonw.exe":
        cand = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(cand):
            return cand
    return exe


PYTHON = _python_exe()


USER_DIRS = ("apk", "programs", "scripts", "screenshots", "files")
CSIDL_DESKTOPDIRECTORY = 0x0010
CSIDL_PROGRAMS = 0x0002
