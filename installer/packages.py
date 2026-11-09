# -*- coding: utf-8 -*-
"""Скачивание и распаковка adb и scrcpy."""

import os
import shutil
import subprocess
import tempfile
import zipfile

from .config import NO_WIN, PLATFORM_TOOLS_URL
from .net import download, scrcpy_download_url
from .service import InstallError


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


def check_adb(install_dir, log):
    adb = os.path.join(install_dir, "tools", "adb", "adb.exe")
    if not os.path.isfile(adb):
        log("ВНИМАНИЕ: adb.exe не найден, программа не сможет подключаться")
        return
    rc = subprocess.run([adb, "version"], capture_output=True, text=True,
                        stdin=subprocess.DEVNULL, creationflags=NO_WIN)
    first = (rc.stdout or "adb работает").strip().splitlines()[0]
    log(f"Проверка adb: {first}")
