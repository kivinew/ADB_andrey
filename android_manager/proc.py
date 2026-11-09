# -*- coding: utf-8 -*-
"""Запуск внешних процессов (adb и прочие)."""

import subprocess


NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run(args, timeout=30, data=None):
    kw = {"input": data} if data is not None else {"stdin": subprocess.DEVNULL}
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WIN, **kw)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except FileNotFoundError:
        return -1, "", f"Не найден файл: {args[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", "Превышено время ожидания"
