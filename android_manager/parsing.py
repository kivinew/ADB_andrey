# -*- coding: utf-8 -*-
"""Разбор вывода adb: показатели, процессы, память, пакеты, адреса."""

import re
import socket


IP_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
CYR_RE = re.compile(r"[а-яёА-ЯЁ]")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def cpu_totals(line):
    nums = [num(x) for x in line.split()[1:]]
    if len(nums) < 5:
        return 0, 0
    return sum(nums[:8]), nums[3] + nums[4]


def num(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def card_numbers(text):
    nums = [float(x) for x in NUM_RE.findall(text)]
    return nums


def parse_card(card, text, snap=None):
    """Разбор ответа показателя. Возвращает (процент для графика или None, текст для показа)."""
    unit = card.get("unit", "")
    div = card.get("div") or 1
    parse = card.get("parse", "number")
    if parse == "cpu":
        if not snap:
            return None, "н/д"
        s1, s2 = snap
        dt = s2[0] - s1[0]
        if dt <= 0:
            return None, "н/д"
        busy = (dt - (s2[1] - s1[1])) * 100.0 / dt
        return busy, f"{busy:.0f}%"
    nums = card_numbers(text)
    if not nums:
        return None, "н/д"
    if parse == "nums_pct":
        a_i, b_i = int(card.get("a", 0)), int(card.get("b", 1))
        if max(a_i, b_i) >= len(nums) or min(a_i, b_i) < 0:
            return None, "н/д"
        a, b = nums[a_i], nums[b_i]
        if b <= 0:
            return None, "н/д"
        pct = a * 100.0 / b
        return pct, f"{a / div:.0f} из {b / div:.0f} {unit} ({pct:.0f}%)"
    i = int(card.get("idx", 0))
    if i < 0 or i >= len(nums):
        return None, "н/д"
    v = nums[i] / div
    mx = card.get("max") or 0
    pct = (v * 100.0 / mx) if mx else None
    result = pct, (f"{v:.1f} {unit}").rstrip()
    return result


def build_state_batch(cards):
    """Одна команда для всех показателей. Каждый ответ печатается строкой @@c<id> ...."""
    parts = []
    for c in cards:
        if c.get("parse") == "cpu":
            continue
        cmd = (c.get("cmd") or "").strip()
        if not cmd:
            continue
        parts.append(f'echo "@@c{c["id"]} $({cmd} 2>/dev/null | tr "\\n" " ")"')
    parts += ['echo "@@S1 $(head -1 /proc/stat)"', "sleep 1", 'echo "@@S2 $(head -1 /proc/stat)"']
    return "; ".join(parts)


def parse_state_batch(raw):
    vals = {}
    s1 = s2 = None
    for line in raw.splitlines():
        if line.startswith("@@c"):
            head, _, rest = line[3:].partition(" ")
            # strip leading 'c' from head (format is @@c<id> value)
            if head.startswith("c"):
                head = head[1:]
            vals[head] = rest.strip()
        elif line.startswith("@@S1 "):
            s1 = cpu_totals(line[5:])
        elif line.startswith("@@S2 "):
            s2 = cpu_totals(line[5:])
    return vals, ((s1, s2) if (s1 and s2) else None)


PROC_LINES = [
    'echo "@@S1 $(head -1 /proc/stat)"',
    'for p in /proc/[0-9]*; do echo "@@P $(cat $p/stat 2>/dev/null)"; done',
    'sleep 1',
    'echo "@@S2 $(head -1 /proc/stat)"',
    'for p in /proc/[0-9]*; do echo "@@Q $(cat $p/stat 2>/dev/null)"; done',
]
PROC_CMD = "; ".join(PROC_LINES)


def parse_proc_stat(text):
    lp, rp = text.find("("), text.rfind(")")
    if lp < 0 or rp < 0:
        return None
    pid = text[:lp].strip()
    name = text[lp + 1:rp]
    rest = text[rp + 2:].split()
    if len(rest) < 22:
        return None
    return pid, name, rest[0], num(rest[11]) + num(rest[12]), num(rest[21])


def parse_proc_output(raw):
    s1 = s2 = None
    a, b = {}, {}
    for line in raw.splitlines():
        if line.startswith("@@S1 "):
            s1 = cpu_totals(line[5:])
        elif line.startswith("@@S2 "):
            s2 = cpu_totals(line[5:])
        elif line.startswith("@@P "):
            info = parse_proc_stat(line[4:])
            if info:
                a[info[0]] = info
        elif line.startswith("@@Q "):
            info = parse_proc_stat(line[4:])
            if info:
                b[info[0]] = info
    dtotal = (s2[0] - s1[0]) if (s1 and s2) else 0
    rows = []
    for pid, (_, name, state, ticks, rss) in b.items():
        old = a.get(pid)
        dp = ticks - old[3] if old else 0
        cpu = dp * 100.0 / dtotal if dtotal > 0 and dp >= 0 else 0.0
        rows.append({"pid": pid, "name": name, "state": state, "mem": rss * 4 / 1024.0, "cpu": cpu})
    return rows


def mem_from_meminfo(text):
    vals = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith(":"):
            vals[parts[0][:-1]] = num(parts[1])
    return vals.get("MemTotal", 0) // 1024, vals.get("MemAvailable", 0) // 1024


def parse_df_mb(line):
    f = line.split()
    if len(f) >= 4:
        return num(f[2]) // 1024, num(f[1]) // 1024
    return None


def split_target(host, port):
    host = host.strip().replace(" ", "")
    if ":" in host:
        h, _, p = host.rpartition(":")
        if p.isdigit():
            host, port = h, p
    return host, port


def parse_pkgs(text):
    return [l.strip()[len("package:"):] for l in text.splitlines() if l.strip().startswith("package:")]


def detect_pc_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"
