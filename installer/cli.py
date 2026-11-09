# -*- coding: utf-8 -*-
"""Командная строка: --cli, --run, --dir, --version."""

import argparse
import sys

from .config import DEFAULT_PARENT
from .service import install, resolve_install_dir


def main(argv=None):
    from android_manager.config import APP_TITLE, VERSION

    parser = argparse.ArgumentParser(description="Android manager — установка и запуск")
    parser.add_argument("--cli", action="store_true", help="установка без окна, в консоли")
    parser.add_argument("--run", action="store_true",
                        help="запустить приложение (GUI) из исходников")
    parser.add_argument("--dir", default=DEFAULT_PARENT,
                        help="папка, куда установить (внутри будет создана папка Android-manager)")
    parser.add_argument("--version", action="version", version="%s %s" % (APP_TITLE, VERSION))
    args = parser.parse_args(argv)

    if args.run:
        from android_manager.__main__ import main as run_app

        run_app()
        return
    if args.cli:
        try:
            install(print, resolve_install_dir(args.dir))
        except Exception as e:  # noqa: BLE001
            print("ОШИБКА:", e)
            input("Нажмите Enter для выхода...")
            sys.exit(1)
        input("Нажмите Enter для выхода...")
        return
    from .gui import InstallerWindow

    InstallerWindow().mainloop()


if __name__ == "__main__":
    main()
