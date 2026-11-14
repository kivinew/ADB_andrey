# -*- coding: utf-8 -*-
"""Константы: версия, название, оформление, размеры, цвета."""

VERSION = "1.7"
APP_TITLE = "Android manager"
BUNDLE_FORMAT = "android-tv-bundle"
REMOTE_W, REMOTE_H = 340, 600


# ---------------------------------------------------------------- темы
THEMES = {
    "dark": {
        "bg": "#14202e", "head": "#1e4170", "bar": "#1a2c42", "panel": "#1e2e42",
        "border": "#2f4661", "text": "#e6edf5", "muted": "#9fb4cc", "accent": "#5aa9f0",
        "ok": "#7fd68f", "warn": "#ffb347", "err": "#ff7b7b", "term": "#0b121b", "sel": "#2a4a6e",
        "key": "#243a55", "keyhot": "#2f6fb0", "body": "#0c1520", "red": "#8b2f36",
        "purple": "#c49bff",
    },
    "light": {
        "bg": "#f0f4f8", "head": "#2b6cb0", "bar": "#e2e8f0", "panel": "#ffffff",
        "border": "#cbd5e0", "text": "#1a202c", "muted": "#718096", "accent": "#3182ce",
        "ok": "#38a169", "warn": "#dd6b20", "err": "#e53e3e", "term": "#edf2f7", "sel": "#bee3f8",
        "key": "#2c5282", "keyhot": "#3182ce", "body": "#f7fafc", "red": "#c53030",
        "purple": "#9f7aea",
    },
}

# Текущая тема (заполняется при запуске)
C = THEMES["dark"].copy()

PALETTE = ["#5aa9f0", "#c49bff", "#7fd68f", "#ffb347", "#ff7b7b", "#7fd0ff", "#e6d26b", "#9fb4cc"]


def apply_theme(theme_name: str):
    """Применяет тему по имени (dark/light). Обновляет глобальный словарь C."""
    global C
    theme = THEMES.get(theme_name, THEMES["dark"])
    C.clear()
    C.update(theme.copy())


# ---------------------------------------------------------------- значения по умолчанию
KEY_COL = "#243a55"
ACC_COL = "#2f6fb0"
RED_COL = "#8b2f36"
