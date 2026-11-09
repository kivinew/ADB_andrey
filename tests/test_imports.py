# -*- coding: utf-8 -*-
"""Структурные тесты: все модули импортируются, пути и версия на месте.

Ловят ошибки переноса, которые не видны ни в GUI, ни в тестах логики:
неверная форма импорта (`import urllib` вместо `import urllib.request`),
сдвиг корня данных (`BASE` внутри пакета), рассинхрон версии.
"""
import importlib
import os
import pkgutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def all_modules():
    names = []
    for package in ("android_manager", "installer"):
        module = importlib.import_module(package)
        names.append(package)
        for info in pkgutil.walk_packages(module.__path__, package + "."):
            names.append(info.name)
    return names


class TestImports(unittest.TestCase):
    def test_every_module_imports(self):
        failures = []
        for name in all_modules():
            try:
                importlib.import_module(name)
            except Exception as exc:  # noqa: BLE001 - показываем все поломки сразу
                failures.append("%s: %r" % (name, exc))
        self.assertEqual(failures, [])

    def test_network_module_has_urllib_request(self):
        # регресс: при переносе потерялся `.request` и установка падала на скачивании
        import urllib.request

        from installer import net

        self.assertIs(net.urllib.request, urllib.request)
        self.assertTrue(callable(net.urllib.request.Request))


    def test_app_package_does_not_import_installer(self):
        """Приложение не должно зависеть от установщика: иначе exe тянет его целиком."""
        import ast

        bad = []
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "android_manager")):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
                rel = os.path.relpath(path, ROOT)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("installer"):
                        bad.append("%s: from %s" % (rel, node.module))
                    elif isinstance(node, ast.Import):
                        bad += ["%s: import %s" % (rel, alias.name) for alias in node.names
                                if alias.name.startswith("installer")]
        self.assertEqual(bad, [], "приложение не должно импортировать installer")


    def test_all_globals_resolve(self):
        """Каждое глобальное имя модуля должно быть импортировано (или быть builtin).

        Ловит класс ошибок переноса: код использует `sys`, а `import sys` остался
        только внутри вложенной функции (`run_script` во вкладке «Скрипты»).
        """
        import builtins
        import symtable

        bad = []
        for name in all_modules():
            module = importlib.import_module(name)
            path = getattr(module, "__file__", None)
            if not path or not path.endswith(".py"):
                continue
            with open(path, encoding="utf-8") as fh:
                table = symtable.symtable(fh.read(), path, "exec")
            known = set(vars(module)) | set(dir(builtins)) | {"__name__", "__file__"}

            def walk(node):
                for symbol in node.get_symbols():
                    if symbol.is_global() and symbol.is_referenced():
                        yield symbol.get_name()
                for child in node.get_children():
                    yield from walk(child)

            for global_name in set(walk(table)):
                if global_name not in known:
                    bad.append("%s: %s" % (os.path.relpath(path, ROOT), global_name))
        self.assertEqual(bad, [], "глобальные имена без импорта")


class TestPaths(unittest.TestCase):
    def test_base_is_project_root_in_source_mode(self):
        from android_manager import paths

        self.assertEqual(os.path.abspath(paths.BASE), ROOT)
        self.assertEqual(paths.SETTINGS_PATH, os.path.join(paths.BASE, "settings.json"))
        self.assertEqual(paths.SCRIPTS_DIR, os.path.join(paths.BASE, "scripts"))

    def test_app_src_root_contains_package(self):
        from installer.build import app_src_root

        root = app_src_root()
        self.assertTrue(os.path.isdir(os.path.join(root, "android_manager")))
        self.assertTrue(os.path.isdir(os.path.join(root, "installer")))


class TestPackageLayout(unittest.TestCase):
    """Пакет не должен зарастать файлами данных и пустыми файлами."""

    def test_no_user_data_dirs_inside_package(self):
        forbidden = {"apk", "files", "programs", "screenshots", "scripts"}
        present = forbidden & set(os.listdir(os.path.join(ROOT, "android_manager")))
        self.assertEqual(present, set(), "в пакете появились каталоги данных программы")

    def test_no_empty_python_files(self):
        empty = []
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "android_manager")):
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(dirpath, name)
                    if os.path.getsize(path) == 0:
                        empty.append(os.path.relpath(path, ROOT))
        self.assertEqual(empty, [])


class TestVersion(unittest.TestCase):
    def test_single_version_source(self):
        from android_manager import config

        self.assertRegex(config.VERSION, r"^\d+\.\d+$")
        self.assertEqual(config.APP_TITLE, "Android manager")


if __name__ == "__main__":
    unittest.main()
