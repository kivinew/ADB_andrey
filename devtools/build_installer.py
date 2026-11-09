# -*- coding: utf-8 -*-
"""Собирает dist/Android_manager.pyw — установщик одним файлом.

Внутри сгенерированного файла лежит zip-архив с пакетами android_manager/ и installer/;
при запуске он распаковывается во временную папку и импортируется оттуда. Поэтому
исходники в репозитории остаются обычными модулями, а пользователю уходит один файл.

    python devtools/build_installer.py
"""
import base64
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGES = ("android_manager", "installer")
TARGET = os.path.join(ROOT, "dist", "Android_manager.pyw")

LAUNCHER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android manager: установщик одним файлом (сгенерировано devtools/build_installer.py).

Внутри — архив с пакетами android_manager/ и installer/. При запуске он распаковывается
во временную папку, и дальше работает обычный код установщика.

    python Android_manager.pyw            — окно установки
    python Android_manager.pyw --cli      — установка без окна
    python Android_manager.pyw --run      — запустить приложение из этих исходников
    python Android_manager.pyw --version  — версия
"""
import atexit
import base64
import io
import shutil
import sys
import tempfile
import zipfile

_ARCHIVE = """%s"""


def _unpack():
    """Распаковывает исходники во временную папку и делает их доступными для импорта."""
    folder = tempfile.mkdtemp(prefix="android_manager_src_")
    atexit.register(shutil.rmtree, folder, True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(_ARCHIVE))) as archive:
        archive.extractall(folder)
    sys.path.insert(0, folder)
    return folder


def main():
    _unpack()
    from installer.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - показываем ошибку, а не падаем молча
        import traceback

        traceback.print_exc()
        input("Ошибка запуска. Нажмите Enter для выхода...")
'''


def collect():
    files = []
    for package in PACKAGES:
        base = os.path.join(ROOT, package)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                full = os.path.join(dirpath, name)
                files.append((full, os.path.relpath(full, ROOT).replace("\\", "/")))
    return files


def build_archive(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in files:
            with open(full, encoding="utf-8") as fh:
                zf.writestr(rel, fh.read())
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    files = collect()
    if not files:
        print("Не найдены исходники для упаковки")
        return 1
    encoded = build_archive(files)
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(LAUNCHER % encoded)
    size = os.path.getsize(TARGET)
    print("файлов в архиве: %d, модулей: %d" % (
        len(files), len({rel.split("/")[0] for _f, rel in files})))
    print("готово: %s (%.0f КБ)" % (TARGET, size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
