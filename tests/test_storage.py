# -*- coding: utf-8 -*-
"""Тесты настроек, миграции и экспорта/импорта (во временной папке)."""
import json
import os
import tempfile
import unittest

from android_manager import storage
from android_manager.config import BUNDLE_FORMAT, VERSION
from android_manager.defaults import DEFAULT_SCRIPT_FILES


def empty_settings():
    return {"bars": {"scripts": []}, "remotes": {}, "cards": []}


class StorageCase(unittest.TestCase):
    """Подменяет пути настроек на временную папку: файлы проекта не трогаются."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="am_test_")
        self.folder = self.tmp.name
        self._saved = (storage.SETTINGS_PATH, storage.SCRIPTS_DIR)
        storage.SETTINGS_PATH = os.path.join(self.folder, "settings.json")
        storage.SCRIPTS_DIR = self.folder

    def tearDown(self):
        storage.SETTINGS_PATH, storage.SCRIPTS_DIR = self._saved
        self.tmp.cleanup()


class TestMigrate(StorageCase):
    def test_from_empty_settings(self):
        settings = {}
        changed = storage.migrate_settings(settings, self.folder)
        self.assertTrue(changed)
        self.assertTrue(settings["defaults_done"])
        self.assertIn("tools", settings["bars"])
        self.assertIn("apps", settings["bars"])
        self.assertEqual(len(settings["bars"]["scripts"]), len(DEFAULT_SCRIPT_FILES))
        for item in settings["bars"]["scripts"]:
            self.assertTrue(os.path.isfile(os.path.join(self.folder, item["file"])))
        self.assertIn(settings["remote_current"], settings["remotes"])
        self.assertTrue(settings["cards"])
        self.assertIn("cpu", [card["id"] for card in settings["cards"]])
        for card in settings["cards"]:
            for key in ("unit", "max", "div", "parse"):
                self.assertIn(key, card)

    def test_card_defaults_filled(self):
        settings = empty_settings()
        settings.update({"defaults_done": True, "remotes": {"r": {}}, "remote_current": "r",
                         "cards": [{"id": "x", "title": "X"}]})
        storage.migrate_settings(settings, self.folder)
        card = settings["cards"][0]
        self.assertEqual(card["unit"], "")
        self.assertEqual(card["max"], 0)
        self.assertEqual(card["div"], 1)
        self.assertEqual(card["parse"], "number")

    def test_second_run_changes_nothing(self):
        settings = {}
        storage.migrate_settings(settings, self.folder)
        self.assertFalse(storage.migrate_settings(settings, self.folder))

    def test_legacy_tool_buttons_removed(self):
        settings = {"bars": {"tools": [{"name": "Сводка устройства", "cmd": "x"},
                                       {"name": "ping", "cmd": "y"}]}}
        storage.migrate_settings(settings, self.folder)
        self.assertEqual([it["name"] for it in settings["bars"]["tools"]], ["ping"])

    def test_legacy_script_code_becomes_file(self):
        settings = empty_settings()
        settings["bars"]["scripts"] = [{"name": "Старый", "code": "print(1)"}]
        settings.update({"defaults_done": True, "remotes": {"r": {}}, "remote_current": "r"})
        storage.migrate_settings(settings, self.folder)
        item = settings["bars"]["scripts"][0]
        self.assertNotIn("code", item)
        self.assertEqual(item["kind"], "script")
        self.assertTrue(os.path.isfile(os.path.join(self.folder, item["file"])))


class TestBundle(StorageCase):
    def test_export_hides_private_fields(self):
        settings = empty_settings()
        settings.update({"pc_ip": "1.2.3.4", "vysor_path": "C:/vysor.exe", "history": ["10.0.0.1"]})
        settings["bars"]["scripts"] = [{"name": "s", "file": "s.py"}]
        with open(os.path.join(self.folder, "s.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("print(1)\n")

        bundle = storage.make_bundle(settings, self.folder, [{"name": "prog"}])
        self.assertEqual(bundle["format"], BUNDLE_FORMAT)
        self.assertEqual(bundle["version"], VERSION)
        for key in ("pc_ip", "vysor_path", "history"):
            self.assertNotIn(key, bundle["settings"])
        self.assertEqual(bundle["scripts"], {"s.py": "print(1)\n"})
        self.assertEqual(bundle["programs"], [{"name": "prog"}])

    def test_import_rejects_foreign_file(self):
        with self.assertRaises(ValueError):
            storage.apply_bundle({"format": "other"}, {}, self.folder)

    def test_import_adds_scripts_tools_remotes_cards(self):
        settings = empty_settings()
        bundle = {
            "format": BUNDLE_FORMAT,
            "version": VERSION,
            "settings": {
                "bars": {"scripts": [{"name": "Скрипт", "file": "s.py"}],
                         "tools": [{"name": "t", "cmd": "c"}]},
                "remotes": {"R": {"buttons": []}},
                "remote_current": "R",
                "cards": [{"id": "new-card", "title": "T"}],
            },
            "scripts": {"s.py": "print(2)\n"},
            "programs": [{"name": "P"}],
        }
        merged, count, programs = storage.apply_bundle(bundle, settings, self.folder)
        self.assertEqual(count, 1)
        self.assertEqual(programs, [{"name": "P"}])
        self.assertEqual([it["file"] for it in merged["bars"]["scripts"]], ["s.py"])
        self.assertEqual([it["name"] for it in merged["bars"]["tools"]], ["t"])
        self.assertIn("R", merged["remotes"])
        self.assertEqual(merged["remote_current"], "R")
        self.assertEqual([c["id"] for c in merged["cards"]], ["new-card"])
        self.assertTrue(os.path.isfile(os.path.join(self.folder, "s.py")))

    def test_import_does_not_duplicate_existing(self):
        settings = empty_settings()
        settings["bars"]["scripts"] = [{"name": "Скрипт", "kind": "script", "file": "s.py"}]
        settings["cards"] = [{"id": "new-card"}]
        bundle = {
            "format": BUNDLE_FORMAT,
            "version": VERSION,
            "settings": {"bars": {"scripts": [{"name": "Скрипт", "file": "s.py"}],
                                  "tools": []},
                         "cards": [{"id": "new-card"}]},
            "scripts": {"s.py": "print(2)\n"},
            "programs": [],
        }
        merged, _count, _programs = storage.apply_bundle(bundle, settings, self.folder)
        self.assertEqual(len(merged["bars"]["scripts"]), 1)
        self.assertEqual(len(merged["cards"]), 1)


class TestJson(StorageCase):
    def test_settings_roundtrip(self):
        settings = empty_settings()
        settings["pc_ip"] = "10.0.0.5"
        storage.save_settings(settings)
        self.assertTrue(os.path.isfile(storage.SETTINGS_PATH))
        loaded = storage.load_settings()
        self.assertEqual(loaded["pc_ip"], "10.0.0.5")
        self.assertTrue(loaded["defaults_done"])

    def test_broken_settings_file_falls_back_to_defaults(self):
        with open(storage.SETTINGS_PATH, "w", encoding="utf-8") as fh:
            fh.write("{ broken")
        loaded = storage.load_settings()
        self.assertTrue(loaded["bars"])
        self.assertTrue(loaded["remotes"])

    def test_load_json_folder_skips_broken(self):
        folder = os.path.join(self.folder, "programs")
        os.makedirs(folder)
        with open(os.path.join(folder, "a.json"), "w", encoding="utf-8") as fh:
            json.dump({"name": "a"}, fh)
        with open(os.path.join(folder, "bad.json"), "w", encoding="utf-8") as fh:
            fh.write("{")
        with open(os.path.join(folder, "note.txt"), "w", encoding="utf-8") as fh:
            fh.write("x")

        items = storage.load_json_folder(folder)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file"], "a.json")
        self.assertEqual(items[0]["name"], "a")

    def test_write_json_keeps_cyrillic(self):
        path = os.path.join(self.folder, "p.json")
        storage.write_json(path, {"name": "Привет"})
        with open(path, encoding="utf-8") as fh:
            self.assertIn("Привет", fh.read())


if __name__ == "__main__":
    unittest.main()
