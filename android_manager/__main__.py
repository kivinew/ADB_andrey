# -*- coding: utf-8 -*-
"""Точка входа приложения: python -m android_manager (или --run из установщика)."""

import traceback


def bootstrap():
    """Готовит папки данных и заглушку scripts/adb.py. Вызывается один раз при старте."""
    from .paths import ensure_dirs, write_adb_shim

    ensure_dirs()
    write_adb_shim()


def main():
    bootstrap()
    from .ui.app import App

    try:
        App().mainloop()
    except Exception:  # noqa: BLE001 - окно могло не открыться
        traceback.print_exc()
        try:
            input("Ошибка запуска. Нажмите Enter для выхода...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
