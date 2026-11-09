#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Android manager: установщик и точка входа.

    python Android_manager.pyw            — окно установки
    python Android_manager.pyw --cli      — установка без окна
    python Android_manager.pyw --run      — запустить приложение из исходников
    python Android_manager.pyw --version  — версия

Единый файл для распространения собирается так:
    python devtools/build_installer.py
"""

import traceback

from installer.cli import main


def run():
    try:
        main()
    except Exception:  # noqa: BLE001 - показываем ошибку, а не падаем молча
        traceback.print_exc()
        input("Ошибка запуска. Нажмите Enter для выхода...")


if __name__ == "__main__":
    run()
