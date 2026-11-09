# -*- coding: utf-8 -*-
"""
adb-модуль для пользовательских скриптов.
Предоставляет функцию shell(command, timeout=60) -> str.
Использование:
    import adb
    output = adb.shell("logcat -d -t 100")
"""
import sys
import os

# Добавляем путь к основному приложению для доступа к ScriptAPI
# При запуске из Android-manager переменная __adb_api__ передаётся через exec namespace
if "__adb_api__" in globals():
    _api = globals()["__adb_api__"]
else:
    _api = None

def shell(command, timeout=60):
    """Выполняет shell-команду на подключённом устройстве."""
    if _api is None:
        raise RuntimeError("adb.shell: API недоступен. Запускайте скрипт через вкладку «Скрипты».")
    return _api.shell(command, timeout=timeout)

# Для совместимости с tvdiag_report.py
__all__ = ["shell"]
