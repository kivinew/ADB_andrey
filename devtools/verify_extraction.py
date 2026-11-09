# -*- coding: utf-8 -*-
"""Проверка, что перенос из Android_manager.pyw в пакеты ничего не потерял.

Сравнивает старый файл (из git или с диска) с пакетами android_manager/ и installer/:
  * каждый бывший символ верхнего уровня найден и совпадает по AST;
  * каждый метод App найден в одном из UI-модулей и совпадает по AST;
  * набор dir(App) совпадает с прежним (миксины не сломали интерфейс класса).

Запуск:
    python devtools/verify_extraction.py                 # базовая версия из git HEAD
    python devtools/verify_extraction.py --baseline a5a447e
    python devtools/verify_extraction.py --baseline old.pyw
"""
import argparse
import ast
import collections
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "android_manager")
INST_DIR = os.path.join(ROOT, "installer")

SKIP = {"main", "build_program", "App", "PROGRAM_SRC", "ADB_PY_PATH", "InstallError",
        # осознанные отличия после переноса: путь к данным считается от пакета,
        # а не от файла-скрипта (см. PLAN_MODULES.md, §8.1)
        "app_dir"}


def read_baseline(spec):
    if os.path.isfile(spec):
        with open(spec, encoding="utf-8") as fh:
            return fh.read()
    res = subprocess.run(["git", "show", "%s:Android_manager.pyw" % spec], cwd=ROOT,
                         capture_output=True)
    if res.returncode != 0:
        raise SystemExit("Не удалось получить базовую версию из git: %s" % spec)
    return res.stdout.decode("utf-8")


def default_baseline():
    """Последний коммит, где Android_manager.pyw ещё содержал PROGRAM_SRC."""
    log = subprocess.run(["git", "log", "--format=%H", "--", "Android_manager.pyw"],
                         cwd=ROOT, capture_output=True, text=True)
    for sha in log.stdout.split():
        blob = subprocess.run(["git", "show", "%s:Android_manager.pyw" % sha], cwd=ROOT,
                              capture_output=True)
        if blob.returncode == 0 and "PROGRAM_SRC = r" in blob.stdout.decode("utf-8", "replace"):
            return sha
    raise SystemExit("Не нашёл коммит с PROGRAM_SRC. Укажите --baseline <ref|путь>")


def split_sources(text):
    lines = text.splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.startswith("PROGRAM_SRC = r"))
    i1 = next(i for i in range(i0 + 1, len(lines)) if lines[i].rstrip() == "'''")
    return text, "\n".join(lines[i0 + 1:i1]) + "\n"


def symbols(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out[n.name] = n
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name):
                        out[sub.id] = n
    return out


def methods_of(tree, cls_name):
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == cls_name:
            return {m.name: m for m in n.body if isinstance(m, ast.FunctionDef)}
    return {}


def package_symbols():
    found = collections.defaultdict(list)
    for folder in (APP_DIR, INST_DIR):
        for dirpath, _dirs, files in os.walk(folder):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
                rel = os.path.relpath(path, ROOT)
                for n in tree.body:
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                        found[n.name].append((rel, ast.unparse(n)))
                    elif isinstance(n, ast.Assign):
                        for t in n.targets:
                            for sub in ast.walk(t):
                                if isinstance(sub, ast.Name):
                                    found[sub.id].append((rel, ast.unparse(n)))
    return found


def package_methods():
    found = collections.defaultdict(list)
    ui = os.path.join(APP_DIR, "ui")
    for name in sorted(os.listdir(ui)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(ui, name)
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, ast.FunctionDef):
                        found[m.name].append((name, ast.unparse(m)))
    return found


def interface_diff(old_App, new_App):
    old = set(dir(old_App))
    new = set(dir(new_App))
    return sorted(old - new), sorted(new - old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=None,
                    help="git-ссылка или путь к старому .pyw (по умолчанию — последний коммит с PROGRAM_SRC)")
    ap.add_argument("--strict", action="store_true",
                    help="считать отличия от исходного файла ошибкой (для приёмки переноса)")
    args = ap.parse_args()

    text = read_baseline(args.baseline or default_baseline())
    outer_text, app_text = split_sources(text)
    app_tree = ast.parse(app_text)
    outer_tree = ast.parse(outer_text)

    old = {}
    old.update(symbols(app_tree))
    old.update(symbols(outer_tree))
    new = package_symbols()
    old_methods = methods_of(app_tree, "App")
    new_methods = package_methods()

    problems = []
    changed = []
    for name, node in old.items():
        if name in SKIP:
            continue
        want = ast.unparse(node)
        if name not in new:
            problems.append("потерян символ: %s" % name)
        elif not any(src == want for _p, src in new[name]):
            changed.append("символ %s (%s)" % (name, new[name][0][0]))

    for name, node in old_methods.items():
        want = ast.unparse(node)
        if name not in new_methods:
            problems.append("потерян метод App.%s" % name)
        elif not any(src == want for _p, src in new_methods[name]):
            changed.append("метод App.%s (%s)" % (name, new_methods[name][0][0]))

    extra = set(new_methods) - set(old_methods)
    for name in sorted(extra):
        changed.append("новый метод App.%s (%s)" % (name, new_methods[name][0][0]))

    # интерфейс класса: старый App исполняем в отдельном пространстве имён
    # (__file__ указывает в корень проекта, чтобы модульные пути совпали с текущими)
    ns = {"__name__": "am_baseline", "__file__": os.path.join(ROOT, "Android_manager.pyw")}
    exec(compile(app_text, "<baseline>", "exec"), ns)
    old_app = ns["App"]
    sys.path.insert(0, ROOT)
    from android_manager.ui.app import App as new_app

    lost, gained = interface_diff(old_app, new_app)
    if lost:
        problems.append("App потерял атрибуты: %s" % ", ".join(lost[:20]))
    for name in gained:
        changed.append("новый атрибут App.%s" % name)

    print("символов в базе: %d, методов App: %d" % (len(old), len(old_methods)))
    print("модулей-пакетов: %d, классов UI: %d" % (
        len({p for v in new.values() for p, _s in v}), len({p for v in new_methods.values() for p, _s in v})))
    if changed:
        print("изменено после переноса: %d" % len(changed))
        for item in changed:
            print("  ~", item)
    if problems:
        print("ПРОБЛЕМЫ (%d):" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    if changed and args.strict:
        print("FAIL: есть отличия от исходного файла (--strict)")
        return 1
    print("OK: ничего не потеряно, интерфейс App совпадает")
    return 0


if __name__ == "__main__":
    sys.exit(main())
