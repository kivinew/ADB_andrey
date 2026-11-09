# -*- coding: utf-8 -*-
"""Дымовой тест окна: создаёт App, обходит вкладки, закрывает.

    python devtools/smoke_gui.py            # открыть и закрыть через ~2 с
    python devtools/smoke_gui.py --keep 5   # держать окно 5 с

Ловит исключения при построении интерфейса и зацикливание after_idle/relayout.
"""
import argparse
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from android_manager.__main__ import bootstrap  # noqa: E402
from android_manager.ui.app import App  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=float, default=1.5)
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

    app.after(int(args.keep * 1000), app.destroy)
    app.mainloop()
    print("GUI smoke OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
