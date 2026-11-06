# ADB — Android Manager / ADB diagnostics

Two standalone Python scripts for Android TV set-top box management via ADB. No package manager, no test suite, no build step.

## Dev environment
- Python 3 (scripts use only stdlib + tkinter). Run directly: `python install_kes_v9.py` or `python tvdiag_report.py`.
- No venv/requirements needed.

## Build & test
- None verified. No Makefile, tox, pytest, CI configs, package.json. Scripts are self-contained.
- `install_kes_v9.py`: runs a Tkinter GUI installer; `--cli` for headless.
- `tvdiag_report.py`: diagnostic script meant to be imported into Android Manager (tab "Скрипты"). Runs `adb shell` commands and parses `@@key=value` output.

## Conventions (observed in code)
- Encoding: `# -*- coding: utf-8 -*-` in both files.
- Russian docstrings and comments; UI strings in Russian.
- `install_kes_v9.py`: embeds full `PROGRAM_SRC` (the installed app's source) as a raw string inside the installer.
- `tvdiag_report.py`: commands assembled in a single `COMMANDS` multi-line string, executed as one `adb shell`; parsing splits on `@@`.
- Variables/constants: ALL_CAPS (`APP_EXE`, `COMMANDS`, `IP_RE`).

## Pitfalls
- Do not edit the `PROGRAM_SRC` embedded source inside `Android_manager.py` casually — it is rebuilt into the installed `Android-manager.exe` via PyInstaller at install time.
- `tvdiag_report.py` expects an `adb` binary reachable; it doesn't bundle one. It targets the Android Manager `scripts/` folder convention (`P("scripts")`).
- No tests exist; any change to parsing logic (`parse_output`, `num`, `mhz_from`) is unverified by automated checks.
