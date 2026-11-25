"""Offline tests (no network). Run: python3 -m unittest discover tests"""

import os
import subprocess
import sys
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from clockify_utils import client as client_mod  # noqa: E402
from clockify_utils.client import ClockifyClient, match_by_name, parse_api_time, parse_duration  # noqa: E402
from clockify_utils.dates import days_between, preset_range, resolve_range  # noqa: E402
from clockify_utils.scheduler import calculate_time_slots, get_week_dates  # noqa: E402


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code, self.ok = data, status, status < 400
        self.reason, self.text, self.headers = "OK", "", {}

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


def load_original_client():
    """The pre-refactor clockify_client.py, straight from git (initial commit)."""
    src = subprocess.run(["git", "show", "1350059:clockify_client.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    mod = types.ModuleType("original_clockify_client")
    exec(compile(src, "original_clockify_client.py", "exec"), mod.__dict__)
    return mod


class TestBackwardsCompatibility(unittest.TestCase):
    def test_create_payload_matches_original_client(self):
        original = load_original_client()
        start, end = datetime(2026, 12, 7, 9, 0), datetime(2026, 12, 7, 11, 0)
        sent = {}
        for name, cls in (("old", original.ClockifyClient), ("new", ClockifyClient)):
            c = cls("k", "ws")
            calls = []
            c.session.post = lambda url, json=None, **kw: calls.append((url, json)) or FakeResponse({"id": "x"})
            c.session.request = lambda method, url, json=None, **kw: calls.append((url, json)) or FakeResponse({"id": "x"})
            c.create_time_entry(start, end, "pid", "desc")
            sent[name] = calls[0]
        self.assertEqual(sent["old"], sent["new"])

    def test_legacy_imports_still_work(self):
        from clockify_client import ClockifyClient as A  # noqa: F401
        from description_generator import DescriptionGenerator  # noqa: F401
        import weekly_scheduler
        self.assertTrue(callable(weekly_scheduler.main))
        self.assertIs(A, ClockifyClient)

    def test_naive_datetimes_unchanged_aware_converted(self):
        self.assertEqual(client_mod.format_time(datetime(2026, 1, 1, 9)), "2026-01-01T09:00:00Z")
        art = timezone(timedelta(hours=-3))
        self.assertEqual(client_mod.format_time(datetime(2026, 1, 1, 9, tzinfo=art)), "2026-01-01T12:00:00Z")

    def test_scheduler_slots(self):
        schedule = [{"project_id": "a", "daily_minutes": 120}, {"project_id": "b", "daily_minutes": 64}]
        slots = calculate_time_slots(datetime(2026, 12, 7), schedule, 9)
        self.assertEqual([s["start"].strftime("%H:%M") for s in slots], ["09:00", "11:00"])
        self.assertEqual(slots[-1]["end"].strftime("%H:%M"), "12:04")
        self.assertEqual(len(get_week_dates(datetime(2026, 12, 5), datetime(2026, 12, 13))), 5)


class TestClient(unittest.TestCase):
    def test_pagination(self):
        c = ClockifyClient("k", "ws")
        pages = {1: [{"id": i} for i in range(500)], 2: [{"id": 500}]}
        c.session.request = lambda m, url, params=None, **kw: FakeResponse(pages.get(params["page"], []))
        c._user_id = "u"
        self.assertEqual(len(c.get_time_entries(datetime(2026, 1, 1), datetime(2026, 1, 2))), 501)

    def test_error_includes_body(self):
        c = ClockifyClient("k", "ws")
        r = FakeResponse({}, 400)
        r.text, r.reason = '{"message":"bad project"}', "Bad Request"
        c.session.request = lambda *a, **kw: r
        with self.assertRaises(client_mod.ClockifyAPIError) as ctx:
            c.get_user()
        self.assertIn("bad project", str(ctx.exception))

    def test_parse_api_time_formats(self):
        a = parse_api_time("2026-11-17T09:00:00Z")
        b = parse_api_time("2026-11-17T06:00:00-03:00")
        self.assertEqual(a, b)

    def test_parse_duration(self):
        self.assertEqual(parse_duration("PT2H56M"), 10560)
        self.assertEqual(parse_duration(7200), 7200)
        self.assertEqual(parse_duration(None), 0)

    def test_match_by_name(self):
        items = [{"id": "a" * 24, "name": "Acme Mobile"}, {"id": "b" * 24, "name": "Acme Mobile QA"}]
        self.assertEqual(match_by_name(items, "acme mobile", "project")["id"], "a" * 24)
        self.assertEqual(match_by_name(items, "qa", "project")["id"], "b" * 24)
        with self.assertRaises(client_mod.AmbiguousMatchError):
            match_by_name(items, "acme", "project")
        with self.assertRaises(LookupError):
            match_by_name(items, "nope", "project")


class TestDates(unittest.TestCase):
    def test_presets_match_menu(self):
        tue = date(2026, 11, 24)
        self.assertEqual(preset_range("this-week", tue), (date(2026, 11, 23), date(2026, 11, 27)))
        self.assertEqual(preset_range("this-week-until-today", tue), (date(2026, 11, 23), tue))
        self.assertEqual(preset_range("last-week", tue), (date(2026, 11, 16), date(2026, 11, 20)))
        self.assertEqual(preset_range("this-month", tue), (date(2026, 11, 1), date(2026, 11, 30)))
        self.assertEqual(preset_range("last-month", tue), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_resolve_range(self):
        self.assertEqual(resolve_range(None, "2026-01-05", None), (date(2026, 1, 5), date(2026, 1, 5)))
        with self.assertRaises(ValueError):
            resolve_range(None, "2026-01-05", "2026-01-01")
        self.assertEqual(len(days_between(date(2026, 11, 16), date(2026, 11, 22), weekdays_only=True)), 5)


class TestSettings(unittest.TestCase):
    def test_key_precedence(self):
        from clockify_utils import settings
        with mock.patch.object(settings, "load_env_files"), \
             mock.patch.dict(os.environ, {"CLOCKIFY_API_KEY": "envkey"}, clear=True):
            self.assertEqual(settings.resolve_api_key("argkey", {})[0], "argkey")
            self.assertEqual(settings.resolve_api_key(None, {"api_key": "pk"})[0], "envkey")
        with mock.patch.object(settings, "load_env_files"), mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings.resolve_api_key(None, {"api_key": "pk"})[0], "pk")
            self.assertEqual(settings.resolve_api_key(None, {})[0], "")


if __name__ == "__main__":
    unittest.main()
