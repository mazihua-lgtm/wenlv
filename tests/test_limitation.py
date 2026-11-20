import unittest
from datetime import date

from wenlv.report.limitation import add_years, assess, parse_date


class ParseDateTest(unittest.TestCase):
    def test_common_formats(self):
        want = date(2026, 5, 1)
        for raw in ["2026-05-01", "2026/5/1", "2026.05.01", "2026年5月1日", "20260501"]:
            self.assertEqual(parse_date(raw), want, raw)

    def test_rejects_noise(self):
        for raw in ["", "昨天", "2026-13-01", "2026-02-30", "下个月"]:
            self.assertIsNone(parse_date(raw), raw)


class AddYearsTest(unittest.TestCase):
    def test_leap_day_falls_back_to_28th(self):
        self.assertEqual(add_years(date(2024, 2, 29), 3), date(2027, 2, 28))

    def test_plain_case(self):
        self.assertEqual(add_years(date(2023, 5, 1), 3), date(2026, 5, 1))


class AssessTest(unittest.TestCase):
    def test_expired(self):
        a = assess(date(2020, 1, 1), 3, today=date(2026, 11, 20))
        self.assertTrue(a.expired)
        self.assertLess(a.days_left, 0)
        self.assertIn("届满", a.describe())

    def test_urgent(self):
        a = assess(date(2024, 3, 1), 3, today=date(2026, 11, 20))
        self.assertFalse(a.expired)
        self.assertTrue(a.urgent)
        self.assertIn("告急", a.describe())

    def test_normal(self):
        a = assess(date(2026, 1, 1), 3, today=date(2026, 11, 20))
        self.assertFalse(a.expired)
        self.assertFalse(a.urgent)
        self.assertIn("充裕", a.describe())

    def test_one_year_for_labor(self):
        a = assess(date(2026, 1, 1), 1, today=date(2026, 11, 20))
        self.assertEqual(a.deadline, date(2027, 1, 1))


if __name__ == "__main__":
    unittest.main()
