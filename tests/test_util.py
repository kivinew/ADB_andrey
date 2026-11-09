# -*- coding: utf-8 -*-
"""Тесты утилит и геометрии: имена, файлы, раскладка кнопок, пульт."""
import os
import tempfile
import unittest

from android_manager.config import REMOTE_H, REMOTE_W
from android_manager.util import (fit_scale, flow_layout, hit_button, merge,
                                  remote_window_rect, slug, to_latin, unique_name,
                                  unique_path)


class TestText(unittest.TestCase):
    def test_to_latin(self):
        self.assertEqual(to_latin("привет"), "ghbdtn")
        self.assertEqual(to_latin("Привет"), "Ghbdtn")
        self.assertEqual(to_latin("abc"), "abc")
        self.assertEqual(to_latin(""), "")

    def test_slug(self):
        self.assertEqual(slug("Сводка устройства"), "сводка_устройства")
        self.assertEqual(slug("a-b c"), "a_b_c")
        self.assertEqual(slug("!!!"), "item")


class TestNames(unittest.TestCase):
    def test_unique_name(self):
        self.assertEqual(unique_name("A", []), "A")
        self.assertEqual(unique_name("A", ["A"]), "A (2)")
        self.assertEqual(unique_name("A", ["A", "A (2)"]), "A (3)")

    def test_unique_path(self):
        with tempfile.TemporaryDirectory() as folder:
            first = unique_path(folder, "s.py")
            self.assertEqual(os.path.basename(first), "s.py")
            open(first, "w", encoding="utf-8").close()
            second = unique_path(folder, "s.py")
            self.assertEqual(os.path.basename(second), "s_2.py")
            open(second, "w", encoding="utf-8").close()
            self.assertEqual(os.path.basename(unique_path(folder, "s.py")), "s_3.py")


class TestMerge(unittest.TestCase):
    def test_deep_merge(self):
        base = {"a": 1, "d": {"x": 1, "z": 0}}
        extra = {"b": 2, "d": {"y": 2, "z": 9}}
        merged = merge(base, extra)
        self.assertEqual(merged, {"a": 1, "b": 2, "d": {"x": 1, "y": 2, "z": 9}})
        self.assertIs(merged, base)

    def test_type_mismatch_replaces(self):
        self.assertEqual(merge({"d": 1}, {"d": {"x": 2}}), {"d": {"x": 2}})


class TestLayout(unittest.TestCase):
    def test_flow_layout_wraps(self):
        pos, total = flow_layout([(100, 20), (100, 20), (100, 20)], 250, gap=6)
        self.assertEqual(pos, [(0, 0), (106, 0), (0, 26)])
        self.assertEqual(total, 46)

    def test_flow_layout_empty(self):
        self.assertEqual(flow_layout([], 100), ([], 0))

    def test_flow_layout_zero_width_does_not_crash(self):
        pos, _total = flow_layout([(10, 5)], 0)
        self.assertEqual(pos, [(0, 0)])

    def test_hit_button(self):
        buttons = [{"x": 10, "y": 10, "r": 5}, {"x": 40, "y": 10, "r": 5}]
        self.assertEqual(hit_button(buttons, 10, 10), 0)
        self.assertEqual(hit_button(buttons, 40, 12), 1)
        self.assertIsNone(hit_button(buttons, 25, 25))

    def test_hit_button_prefers_topmost(self):
        buttons = [{"x": 10, "y": 10, "r": 20}, {"x": 10, "y": 10, "r": 5}]
        self.assertEqual(hit_button(buttons, 10, 10), 1)


class TestRemoteGeometry(unittest.TestCase):
    def test_fit_scale_full_size(self):
        self.assertAlmostEqual(fit_scale(REMOTE_W, REMOTE_H), 1.0)
        self.assertAlmostEqual(fit_scale(REMOTE_W * 2, REMOTE_H * 2), 2.0)

    def test_fit_scale_floor(self):
        self.assertAlmostEqual(fit_scale(0, 0), 0.2)

    def test_fit_scale_uses_smaller_side(self):
        self.assertAlmostEqual(fit_scale(REMOTE_W, REMOTE_H / 2), 0.5)

    def test_rect_without_target(self):
        x, y, w, h = remote_window_rect(None, 1920, 1080, aspect=0.5)
        self.assertEqual((x, y, h), (0, 54, 972))
        self.assertEqual(w, int(972 * 0.5) + 16)

    def test_rect_left_of_target(self):
        x, y, w, h = remote_window_rect((800, 100, 600, 600), 1920, 1080, aspect=0.5)
        self.assertEqual((x, y, w, h), (800 - (300 + 16) - 6, 100, 316, 600))

    def test_rect_clamped_to_screen(self):
        x, _y, w, _h = remote_window_rect((100, 0, 600, 600), 1920, 1080, aspect=0.5)
        self.assertEqual(x, 0)
        self.assertEqual(w, 316)


if __name__ == "__main__":
    unittest.main()
