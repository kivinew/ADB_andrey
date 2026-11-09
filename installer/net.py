# -*- coding: utf-8 -*-
"""Загрузка файлов из интернета."""

import json
import urllib

from .config import HEADERS, SCRCPY_API
from .service import InstallError


def download(url, dest, log):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        last_step = -1
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                step = done * 10 // total
                if step != last_step:
                    log(f"  загрузка {step * 10}%")
                    last_step = step
    log("  загрузка завершена")


def scrcpy_download_url(log):
    req = urllib.request.Request(SCRCPY_API, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if "win64" in name and name.endswith(".zip"):
            log(f"  релиз scrcpy: {data.get('tag_name', '?')} ({name})")
            return asset["browser_download_url"]
    raise InstallError("На странице релиза scrcpy не найден архив win64")
