# -*- coding: utf-8 -*-
"""Shim: provides adb.shell() for tvdiag_report.py when run standalone.

The real python-adb package (google/python-adb) is a libusb1 reimplementation
and does NOT expose adb.shell(). This shim wraps the adb.exe CLI and delegates
the exact same adb.shell(commands, timeout=...) interface used by
tvdiag_report.py.
"""

import os
import subprocess

_ADB_EXE = r"C:\Users\kivin\AppData\Local\Android-manager\tools\adb\adb.exe"


def shell(commands, timeout=180):
    """Run adb shell commands and return combined stdout+stderr as one string.

    `commands` is a multi-line string where each line is a separate remote shell
    command (as produced by the COMMANDS constant in tvdiag_report.py).
    Each line is executed independently via `adb.exe shell <cmd>`.
    """
    if not os.path.exists(_ADB_EXE):
        raise RuntimeError("adb.exe not found: %r" % _ADB_EXE)
    out_parts = []
    for raw in commands.strip("\n").split("\n"):
        cmd = raw.strip()
        if not cmd:
            continue
        proc = subprocess.run(
            [_ADB_EXE, "shell", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=timeout,
        )
        if proc.stdout:
            out_parts.append(proc.stdout)
        if proc.stderr:
            out_parts.append(proc.stderr)
    return "\n".join(out_parts)
