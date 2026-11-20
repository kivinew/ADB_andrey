# -*- coding: utf-8 -*-
"""Точка входа приложения: python -m android_manager (или --run из установщика)."""

import traceback


def ensure_adb_server():
    """Проверяет и при необходимости перезапускает ADB сервер."""
    from .paths import ADB
    from .proc import run

    def is_adb_responsive():
        rc, out, _ = run([ADB, "version"], 5)
        return rc == 0 and "Android Debug Bridge" in out

    if is_adb_responsive():
        return

    # Пробуем убить и перезапустить
    run([ADB, "kill-server"], 10)
    run([ADB, "start-server"], 10)

    # Финальная проверка
    if not is_adb_responsive():
        run([ADB, "kill-server"], 5)
        run([ADB, "start-server"], 10)


def bootstrap():
    """Готовит папки данных, заглушку scripts/adb.py и проверяет ADB сервер."""
    from .paths import ensure_dirs, write_adb_shim

    ensure_dirs()
    write_adb_shim()
    ensure_adb_server()


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
