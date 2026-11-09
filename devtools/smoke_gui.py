# -*- coding: utf-8 -*-
"""Дымовой тест окна: создаёт App, обходит вкладки, закрывает.

    python devtools/smoke_gui.py             # открыть и закрыть через ~2 с
    python devtools/smoke_gui.py --keep 5    # держать окно 5 с
    python devtools/smoke_gui.py --scripts   # ещё и запустить скрипт из вкладки «Скрипты»

Ловит исключения при построении интерфейса и зацикливание after_idle/relayout.
"""
import argparse
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from android_manager.__main__ import bootstrap  # noqa: E402
from android_manager.paths import SCRIPTS_DIR  # noqa: E402
from android_manager.ui.app import App  # noqa: E402

SMOKE_SCRIPT = "_smoke_script.py"


def check_scripts(app):
    """Запускает скрипт через вкладку и проверяет результат в окне."""
    path = os.path.join(SCRIPTS_DIR, SMOKE_SCRIPT)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("import adb\nprint('smoke', 2 + 2)\n"
                 "print('model:', adb.getprop('ro.product.model'))\n")
    app.serial.set("127.0.0.1:5555")
    try:
        app.run_script({"name": "smoke", "kind": "script", "file": SMOKE_SCRIPT})
        deadline = time.time() + 30
        while app.script_running and time.time() < deadline:
            app.update()
            time.sleep(0.05)
        app.update()
        text = app.script_out.get("1.0", "end")
    finally:
        if os.path.isfile(path):
            os.remove(path)
    ok = "smoke 4" in text and "model:" in text and "готово" in text
    print("вкладка «Скрипты»:", "OK" if ok else "ОШИБКА\n" + text)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=float, default=1.5)
    ap.add_argument("--scripts", action="store_true", help="проверить запуск скрипта")
    args = ap.parse_args()

    bootstrap()
    app = App()
    app.update()

    for index in range(len(app.nb.tabs())):
        app.nb.select(index)
        app.update()
        print("tab %d ok: %s" % (index, app.nb.tab(index, "text")))

    app.on_sub_tab()
    app.update()
    app.open_remote()
    app.update()
    if app.remote_win is not None:
        app.remote_win.close()
    app.update()

    ok = True
    if args.scripts:
        ok = check_scripts(app)

    app.after(int(args.keep * 1000), app.destroy)
    app.mainloop()
    if not ok:
        return 1
    print("GUI smoke OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
