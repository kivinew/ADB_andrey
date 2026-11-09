# -*- coding: utf-8 -*-
"""Настройки settings.json, JSON-файлы, экспорт и импорт."""

import json
import os

from .config import BUNDLE_FORMAT, VERSION
from .defaults import DEFAULT_APPS_BAR, DEFAULT_SCRIPT_FILES, DEFAULT_SETTINGS, default_cards, default_remotes
from .paths import SCRIPTS_DIR, SETTINGS_PATH
from .util import merge, read_text, slug, unique_path


LEGACY_TOOL_NAMES = {"Сводка устройства", "Топ по памяти", "Закрыть пользовательские"}


def save_script_text(scripts_dir, name, text):
    dest = unique_path(scripts_dir, slug(name) + ".py")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.replace("\r\n", "\n"))
    return os.path.basename(dest)


def import_script_file(scripts_dir, src_path, name):
    """Копия внешнего .py в папку scripts, даже если выбран файл из другого места."""
    return save_script_text(scripts_dir, name, read_text(src_path))


def migrate_settings(S, scripts_dir):
    """Приводит старые настройки к версии 1.5. Возвращает True, если что-то изменилось."""
    changed = False
    bars = S.setdefault("bars", {})
    tools = bars.setdefault("tools", [])
    kept = [it for it in tools if it.get("name") not in LEGACY_TOOL_NAMES]
    if len(kept) != len(tools):
        bars["tools"] = kept
        changed = True
    if "apps" not in bars:
        bars["apps"] = json.loads(json.dumps(DEFAULT_APPS_BAR))
        changed = True
    scripts = bars.setdefault("scripts", [])
    for it in scripts:
        if "code" in it and "file" not in it:
            it["file"] = save_script_text(scripts_dir, it.get("name", "script"), it.pop("code"))
            changed = True
        it.setdefault("kind", "script")
    if not S.get("defaults_done"):
        for name, code in DEFAULT_SCRIPT_FILES:
            scripts.append({"name": name, "kind": "script", "file": save_script_text(scripts_dir, name, code)})
        S["defaults_done"] = True
        changed = True
    if not S.get("remotes"):
        S["remotes"] = default_remotes()
        changed = True
    if S.get("remote_current") not in S["remotes"]:
        S["remote_current"] = next(iter(S["remotes"]))
        changed = True
    if not S.get("cards"):
        S["cards"] = default_cards()
        changed = True
    for card in S["cards"]:
        card.setdefault("unit", "")
        card.setdefault("max", 0)
        card.setdefault("div", 1)
        card.setdefault("parse", "number")
    return changed


def make_bundle(S, scripts_dir, programs):
    """Один файл экспорта: настройки, кнопки, пульты, показатели, тексты всех скриптов, программы."""
    settings = json.loads(json.dumps(S))
    for key in ("history", "vysor_path", "pc_ip"):
        settings.pop(key, None)
    scripts = {}
    for it in S.get("bars", {}).get("scripts", []):
        fn = it.get("file")
        path = os.path.join(scripts_dir, fn) if fn else None
        if path and os.path.isfile(path):
            scripts[fn] = read_text(path)
    return {"format": BUNDLE_FORMAT, "version": VERSION, "settings": settings,
            "scripts": scripts, "programs": programs}


def apply_bundle(bundle, S, scripts_dir):
    """Загружает экспорт в текущие настройки. Возвращает (S, число скриптов, программы)."""
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError("Это не файл экспорта Android ТВ-Менеджера")
    mapping = {}
    for fn, text in bundle.get("scripts", {}).items():
        existing = os.path.join(scripts_dir, fn)
        if os.path.isfile(existing) and read_text(existing) == text:
            mapping[fn] = fn
        else:
            dest = unique_path(scripts_dir, fn)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            mapping[fn] = os.path.basename(dest)
    imported = bundle.get("settings", {})
    have_files = {it.get("file") for it in S["bars"].setdefault("scripts", [])}
    for it in imported.get("bars", {}).get("scripts", []):
        fn = it.get("file")
        if not fn:
            continue
        new_fn = mapping.get(fn, fn)
        if new_fn in have_files:
            continue
        S["bars"]["scripts"].append({"name": it.get("name", "script"), "kind": "script", "file": new_fn})
        have_files.add(new_fn)
    for bid in ("tools", "console", "apps"):
        have = {(i.get("name"), i.get("cmd")) for i in S["bars"].setdefault(bid, [])}
        for it in imported.get("bars", {}).get(bid, []):
            key = (it.get("name"), it.get("cmd"))
            if key not in have:
                S["bars"][bid].append(it)
                have.add(key)
    for name, rem in imported.get("remotes", {}).items():
        S.setdefault("remotes", {})[name] = rem
    if imported.get("remote_current") in S.get("remotes", {}):
        S["remote_current"] = imported["remote_current"]
    if imported.get("cards"):
        have_ids = {c["id"] for c in S.get("cards", [])}
        for card in imported["cards"]:
            if card.get("id") not in have_ids:
                S.setdefault("cards", []).append(card)
                have_ids.add(card.get("id"))
    for key in ("scrcpy", "app_presets"):
        if key in imported:
            S[key] = imported[key]
    return S, len(mapping), bundle.get("programs", [])


# ---------------------------------------------------------------- файлы и настройки
def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    S = merge(json.loads(json.dumps(DEFAULT_SETTINGS)), data)
    migrate_settings(S, SCRIPTS_DIR)
    return S


def save_settings(s):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(s, fh, ensure_ascii=False, indent=2)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def load_json_folder(folder):
    out = []
    for fn in sorted(os.listdir(folder)):
        if fn.lower().endswith(".json"):
            try:
                with open(os.path.join(folder, fn), encoding="utf-8") as fh:
                    d = json.load(fh)
                d["file"] = fn
                out.append(d)
            except (OSError, ValueError):
                pass
    return out
