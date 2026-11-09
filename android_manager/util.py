# -*- coding: utf-8 -*-
"""Мелкие утилиты: имена, файлы, раскладка кнопок, геометрия пульта."""

import os
import re

from .config import REMOTE_H, REMOTE_W


LAYOUT = {}
for _r, _e in zip("йцукенгшщзхъфывапролджэячсмитьбюё", "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"):
    LAYOUT[_r] = _e
    LAYOUT[_r.upper()] = _e.upper()


def to_latin(text):
    return "".join(LAYOUT.get(ch, ch) for ch in text)


# ---------------------------------------------------------------- чистая логика (без окна, проверяется отдельно)
def merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merge(base[k], v)
        else:
            base[k] = v
    return base


def slug(name):
    return re.sub(r"[^\w]+", "_", name, flags=re.UNICODE).strip("_").lower() or "item"


def unique_path(folder, filename):
    base, ext = os.path.splitext(filename)
    path = os.path.join(folder, filename)
    i = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{i}{ext}")
        i += 1
    return path


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().replace("\r\n", "\n")


def unique_name(base, existing):
    if base not in existing:
        return base
    n = 2
    while f"{base} ({n})" in existing:
        n += 1
    return f"{base} ({n})"


def hit_button(buttons, x, y):
    for i in range(len(buttons) - 1, -1, -1):
        b = buttons[i]
        if (x - b["x"]) ** 2 + (y - b["y"]) ** 2 <= (b["r"] + 2) ** 2:
            return i
    return None


def flow_layout(sizes, avail_w, gap=6):
    """Раскладка элементов по строкам под ширину. sizes: [(ширина, высота)]. Возвращает ([(x, y)], высота)."""
    pos = []
    x = y = row_h = 0
    avail_w = max(1, avail_w)
    for w, h in sizes:
        if x > 0 and x + w > avail_w:
            x = 0
            y += row_h + gap
            row_h = 0
        pos.append((x, y))
        x += w + gap
        row_h = max(row_h, h)
    total = (y + row_h) if sizes else 0
    return pos, total


def fit_scale(cw, ch):
    """Масштаб пульта, чтобы он целиком помещался в окно."""
    return max(0.2, min(cw / REMOTE_W, ch / REMOTE_H))


def remote_window_rect(target, screen_w, screen_h, aspect=REMOTE_W / REMOTE_H):
    """Окно пульта: рядом слева от окна scrcpy/Vysor с той же высотой, иначе у левого края экрана."""
    if target:
        x, y, w, h = target
        rw = int(h * aspect) + 16
        return max(0, x - rw - 6), y, rw, h
    h = int(screen_h * 0.9)
    rw = int(h * aspect) + 16
    return 0, int(screen_h * 0.05), rw, h
