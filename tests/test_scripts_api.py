# -*- coding: utf-8 -*-
"""Тесты модуля adb, который получают пользовательские скрипты.

Регресс, который здесь закреплён: во вкладку «Скрипты» подставлялся модуль
с одним `shell`, поэтому `adb.getprop(...)`, `adb.packages(...)` и штатные
демо-скрипты падали с AttributeError.
"""
import sys
import types
import unittest

from android_manager.scriptapi import AdbModule


class FakeAPI:
    serial = "192.0.2.1:5555"

    def shell(self, command, timeout=60):
        return "shell:%s:%s" % (command, timeout)

    def getprop(self, name):
        return "prop:%s" % name

    def packages(self, kind="all"):
        return ["com.a", "com.b"]

    def install(self, apk_path):
        return True, "Success"

    def _private(self):
        return "hidden"

    @property
    def stopped(self):
        return self._stopped

    def __init__(self):
        self._stopped = False


class TestAdbModule(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()
        self.adb = AdbModule(self.api)

    def test_is_module(self):
        self.assertIsInstance(self.adb, types.ModuleType)
        self.assertEqual(self.adb.__name__, "adb")

    def test_public_methods_delegate(self):
        self.assertEqual(self.adb.shell("uptime"), "shell:uptime:60")
        self.assertEqual(self.adb.getprop("ro.product.model"), "prop:ro.product.model")
        self.assertEqual(self.adb.packages("user"), ["com.a", "com.b"])
        self.assertEqual(self.adb.install("a.apk"), (True, "Success"))

    def test_attributes_delegate(self):
        self.assertEqual(self.adb.serial, "192.0.2.1:5555")
        self.assertFalse(self.adb.stopped)
        self.api._stopped = True
        self.assertTrue(self.adb.stopped)

    def test_unknown_attribute_raises(self):
        with self.assertRaises(AttributeError):
            self.adb.no_such_method()

    def test_import_adb_gets_same_object(self):
        previous = sys.modules.get("adb")
        sys.modules["adb"] = self.adb
        try:
            import adb as imported

            self.assertIs(imported, self.adb)
            self.assertEqual(imported.getprop("ro.x"), "prop:ro.x")
        finally:
            if previous is None:
                sys.modules.pop("adb", None)
            else:
                sys.modules["adb"] = previous


class TestShippedScripts(unittest.TestCase):
    """Демо-скрипты программы должны пользоваться только реально доступным API."""

    def test_default_scripts_use_supported_methods(self):
        from android_manager.defaults import DEFAULT_SCRIPT_FILES
        from android_manager.scriptapi import ScriptAPI

        allowed = {name for name in dir(ScriptAPI) if not name.startswith("_")}
        forbidden = ("shell", "call", "getprop", "packages", "force_stop", "clear", "disable",
                     "enable", "uninstall", "launch", "install", "push", "pull", "screenshot",
                     "reboot", "sleep", "check", "stopped")
        for _title, code in DEFAULT_SCRIPT_FILES:
            for name in forbidden:
                if "adb.%s(" % name in code:
                    self.assertIn(name, allowed, "демо-скрипт использует adb.%s" % name)


if __name__ == "__main__":
    unittest.main()
