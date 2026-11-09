# -*- coding: utf-8 -*-
"""Тесты разбора вывода adb. Только stdlib: python -m unittest discover -s tests."""
import re
import unittest

from android_manager.parsing import (build_state_batch, card_numbers, cpu_totals,
                                     detect_pc_ip, mem_from_meminfo, num, parse_card,
                                     parse_df_mb, parse_pkgs, parse_proc_output,
                                     parse_proc_stat, parse_state_batch, split_target)


def stat_line(pid, name, utime=0, stime=0, rss=0):
    """Строка /proc/<pid>/stat нужной формы: rest[11]+rest[12] — тики, rest[21] — RSS."""
    fields = ["0"] * 22
    fields[0] = "S"
    fields[11] = str(utime)
    fields[12] = str(stime)
    fields[21] = str(rss)
    return "%s (%s) %s" % (pid, name, " ".join(fields))


class TestNumbers(unittest.TestCase):
    def test_num(self):
        self.assertEqual(num("42"), 42)
        self.assertEqual(num(" 7 "), 7)
        self.assertEqual(num("3.9"), 3)
        self.assertEqual(num("abc"), 0)
        self.assertEqual(num(None), 0)
        self.assertEqual(num("", 5), 5)
        self.assertEqual(num(None, default=5), 5)

    def test_card_numbers(self):
        self.assertEqual(card_numbers("1 2.5 -3"), [1.0, 2.5, -3.0])
        self.assertEqual(card_numbers("нет чисел"), [])

    def test_cpu_totals(self):
        total, idle = cpu_totals("cpu 100 200 300 400 500 600 700 800 900")
        self.assertEqual(total, 3600)          # сумма первых восьми
        self.assertEqual(idle, 900)            # nums[3] + nums[4]

    def test_cpu_totals_short_line(self):
        self.assertEqual(cpu_totals("cpu 1 2"), (0, 0))


class TestCards(unittest.TestCase):
    def test_number_card(self):
        pct, text = parse_card({"parse": "number", "idx": 1, "max": 100, "unit": "%"}, "a 42 b 84")
        self.assertAlmostEqual(pct, 84.0)
        self.assertEqual(text, "84.0 %")

    def test_number_card_without_max_has_no_pct(self):
        pct, text = parse_card({"parse": "number", "idx": 0, "unit": "МБ"}, "512")
        self.assertIsNone(pct)
        self.assertEqual(text, "512.0 МБ")

    def test_div_scales_value(self):
        pct, text = parse_card({"parse": "number", "idx": 0, "div": 1024, "unit": "МБ"}, "2048")
        self.assertEqual(text, "2.0 МБ")
        self.assertIsNone(pct)

    def test_missing_number(self):
        self.assertEqual(parse_card({"parse": "number"}, "нет данных"), (None, "н/д"))

    def test_nums_pct(self):
        pct, text = parse_card({"parse": "nums_pct", "a": 0, "b": 1, "div": 1024, "unit": "МБ"},
                               "2048 4096")
        self.assertAlmostEqual(pct, 50.0)
        self.assertEqual(text, "2 из 4 МБ (50%)")

    def test_nums_pct_bad_index(self):
        self.assertEqual(parse_card({"parse": "nums_pct", "a": 0, "b": 5}, "1 2"), (None, "н/д"))

    def test_nums_pct_zero_base(self):
        self.assertEqual(parse_card({"parse": "nums_pct", "a": 0, "b": 1}, "0 0"), (None, "н/д"))

    def test_cpu_card_needs_snapshot(self):
        self.assertEqual(parse_card({"parse": "cpu"}, ""), (None, "н/д"))

    def test_cpu_card_percent(self):
        pct, text = parse_card({"parse": "cpu"}, "", snap=((1000, 400), (2000, 600)))
        self.assertAlmostEqual(pct, 80.0)
        self.assertEqual(text, "80%")

    def test_cpu_card_zero_delta(self):
        self.assertEqual(parse_card({"parse": "cpu"}, "", snap=((1000, 400), (1000, 400))),
                         (None, "н/д"))


class TestBatch(unittest.TestCase):
    def test_build_state_batch_skips_cpu_and_empty(self):
        cards = [{"id": 1, "cmd": "cat /proc/loadavg"},
                 {"id": 2, "cmd": ""},
                 {"id": 3, "cmd": "cat /proc/uptime", "parse": "cpu"}]
        cmd = build_state_batch(cards)
        self.assertIn("@@c1", cmd)
        self.assertIn("loadavg", cmd)
        self.assertNotIn("@@c2", cmd)
        self.assertNotIn("@@c3", cmd)
        self.assertIn('echo "@@S1 $(head -1 /proc/stat)"', cmd)
        self.assertIn("sleep 1", cmd)

    def test_parse_state_batch_values_and_snapshot(self):
        raw = "\n".join(["@@c12 55", "@@c7 3.5", "@@S1 cpu 1 2 3 4 5", "@@S2 cpu 2 3 4 5 6"])
        vals, snap = parse_state_batch(raw)
        self.assertEqual(vals, {"12": "55", "7": "3.5"})
        self.assertEqual(snap, ((15, 9), (20, 11)))

    def test_parse_state_batch_without_snapshot(self):
        vals, snap = parse_state_batch("@@c1 1")
        self.assertIsNone(snap)


class TestProc(unittest.TestCase):
    def test_parse_proc_stat(self):
        info = parse_proc_stat(stat_line(1234, "my app", utime=11, stime=12, rss=22))
        self.assertEqual(info, ("1234", "my app", "S", 23, 22))

    def test_parse_proc_stat_garbage(self):
        self.assertIsNone(parse_proc_stat("мусор"))
        self.assertIsNone(parse_proc_stat("1234 (name) S 1 2"))

    def test_parse_proc_output_cpu_and_mem(self):
        s1 = "cpu 100 0 100 800 100"      # всего 1100, простой 900
        s2 = "cpu 200 0 200 900 100"      # всего 1400, простой 1000
        raw = "\n".join([
            "@@S1 " + s1,
            "@@P " + stat_line(77, "app", utime=10, stime=10, rss=256),
            "@@S2 " + s2,
            "@@Q " + stat_line(77, "app", utime=20, stime=20, rss=256),
        ])
        rows = parse_proc_output(raw)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["pid"], "77")
        self.assertEqual(row["name"], "app")
        self.assertEqual(row["state"], "S")
        self.assertAlmostEqual(row["mem"], 1.0)              # 256 * 4 / 1024
        self.assertAlmostEqual(row["cpu"], 20 * 100.0 / 300)

    def test_parse_proc_output_new_process_has_zero_cpu(self):
        raw = "@@Q " + stat_line(5, "new", rss=512)
        rows = parse_proc_output(raw)
        self.assertEqual(rows[0]["cpu"], 0.0)
        self.assertAlmostEqual(rows[0]["mem"], 2.0)


class TestSystem(unittest.TestCase):
    def test_mem_from_meminfo(self):
        text = "MemTotal:       2048000 kB\nMemFree: 10 kB\nMemAvailable: 1024000 kB\n"
        self.assertEqual(mem_from_meminfo(text), (2000, 1000))

    def test_mem_from_meminfo_empty(self):
        self.assertEqual(mem_from_meminfo(""), (0, 0))

    def test_parse_df_mb(self):
        self.assertEqual(parse_df_mb("/dev/block 40960 20480 20480 50% /data"), (20, 40))
        self.assertIsNone(parse_df_mb("мало полей"))

    def test_parse_pkgs(self):
        text = "package:com.a\n  package:com.b  \nnot a package\n"
        self.assertEqual(parse_pkgs(text), ["com.a", "com.b"])

    def test_split_target(self):
        self.assertEqual(split_target("192.168.1.5:5555", "5555"), ("192.168.1.5", "5555"))
        self.assertEqual(split_target(" 10.0.0.1:5556 ", "5555"), ("10.0.0.1", "5556"))
        self.assertEqual(split_target("192.168.1.5", "5555"), ("192.168.1.5", "5555"))
        self.assertEqual(split_target("host:abc", "1234"), ("host:abc", "1234"))
        self.assertEqual(split_target("", "5555"), ("", "5555"))

    def test_detect_pc_ip_is_ipv4(self):
        self.assertRegex(detect_pc_ip(), r"^\d{1,3}(\.\d{1,3}){3}$")


if __name__ == "__main__":
    unittest.main()
