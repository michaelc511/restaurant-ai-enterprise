"""F23: unit tests for core/sheets.py - date resolution, intent routing, and the
Google Sheets lookups, with the live gspread client mocked out so tests run
offline and fast.
"""
import datetime as dt

import pytest
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

import core.sheets as sheets


class FixedDate(dt.date):
    """Freezes date.today() to a known Thursday (2026-09-03) for deterministic tests."""

    @classmethod
    def today(cls):
        return cls(2026, 9, 3)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(sheets, "date", FixedDate)


# --- resolve_target_days -----------------------------------------------------

def test_resolve_target_days_defaults_to_today_when_nothing_matches():
    assert sheets.resolve_target_days("what's on the menu?") == [dt.date(2026, 9, 3)]


def test_resolve_target_days_tomorrow():
    assert sheets.resolve_target_days("what's the special tomorrow?") == [dt.date(2026, 9, 4)]


def test_resolve_target_days_day_after_tomorrow_before_tomorrow():
    # "day after tomorrow" contains "tomorrow" as a substring - must be checked first.
    assert sheets.resolve_target_days("the day after tomorrow") == [dt.date(2026, 9, 5)]


def test_resolve_target_days_in_n_days():
    assert sheets.resolve_target_days("what's happening in 3 days") == [dt.date(2026, 9, 6)]


def test_resolve_target_days_n_days_from_now():
    assert sheets.resolve_target_days("5 days from now") == [dt.date(2026, 9, 8)]


def test_resolve_target_days_weekend_returns_saturday_and_sunday():
    assert sheets.resolve_target_days("any specials this weekend?") == [
        dt.date(2026, 9, 5),
        dt.date(2026, 9, 6),
    ]


def test_resolve_target_days_named_weekday_ahead():
    assert sheets.resolve_target_days("what about friday?") == [dt.date(2026, 9, 4)]


def test_resolve_target_days_named_weekday_matching_today():
    # today (frozen) is Thursday, so "thursday" should resolve to today, not +7 days.
    assert sheets.resolve_target_days("open thursday?") == [dt.date(2026, 9, 3)]


def test_resolve_target_days_weekday_abbreviation():
    assert sheets.resolve_target_days("hours on fri") == [dt.date(2026, 9, 4)]


# --- detect_ops_intent --------------------------------------------------------

@pytest.mark.parametrize(
    "question,expected",
    [
        ("what are today's specials?", "specials"),
        ("are you open on sunday?", "hours"),
        ("what time do you close?", "hours"),
        ("is it a holiday?", "hours"),
        ("what's good on the menu?", None),
    ],
)
def test_detect_ops_intent(question, expected):
    assert sheets.detect_ops_intent(question) == expected


def test_detect_ops_intent_specials_takes_priority_over_hours():
    assert sheets.detect_ops_intent("any specials during holiday hours?") == "specials"


# --- _is_active ----------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("True", True),
        ("YES", True),
        ("y", True),
        ("1", True),
        (" active ", True),
        ("False", False),
        ("no", False),
        ("", False),
    ],
)
def test_is_active(value, expected):
    assert sheets._is_active(value) is expected


# --- get_daily_specials / get_hours_and_events (mocked worksheet) -------------

class FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_records(self):
        return self._rows


def test_get_daily_specials_filters_inactive_rows(monkeypatch):
    rows = [
        {"Day": "Mon", "Dish Name": "Soup", "Is Active": "true"},
        {"Day": "Mon", "Dish Name": "Old Special", "Is Active": "false"},
    ]
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(rows))

    specials = sheets.get_daily_specials()

    assert [s["Dish Name"] for s in specials] == ["Soup"]


def test_get_daily_specials_filters_by_day_including_all_week(monkeypatch):
    rows = [
        {"Day": "Mon", "Dish Name": "Monday Only", "Is Active": "true"},
        {"Day": "All Week", "Dish Name": "Always On", "Is Active": "true"},
        {"Day": "Tue", "Dish Name": "Tuesday Only", "Is Active": "true"},
    ]
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(rows))

    specials = sheets.get_daily_specials(day="Mon")

    assert {s["Dish Name"] for s in specials} == {"Monday Only", "Always On"}


def test_get_hours_and_events_filters_by_target_date(monkeypatch):
    rows = [
        {"Date": "2026-09-03", "Status": "Open"},
        {"Date": "2026-09-04", "Status": "Closed"},
    ]
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(rows))

    result = sheets.get_hours_and_events(target_date="2026-09-04")

    assert result == [{"Date": "2026-09-04", "Status": "Closed"}]


def test_get_hours_and_events_returns_all_rows_when_no_target_date(monkeypatch):
    rows = [{"Date": "2026-09-03"}, {"Date": "2026-09-04"}]
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(rows))

    assert sheets.get_hours_and_events() == rows


# --- _open_tab error handling ---------------------------------------------------

class FakeSpreadsheet:
    def __init__(self, exc):
        self._exc = exc

    def worksheet(self, tab_name):
        raise self._exc


class FakeClient:
    def __init__(self, exc):
        self._exc = exc

    def open(self, name):
        if isinstance(self._exc, SpreadsheetNotFound):
            raise self._exc
        return FakeSpreadsheet(self._exc)


class FakeErrorResponse:
    text = "rate limited"

    def json(self):
        raise ValueError("no JSON body")


@pytest.mark.parametrize(
    "exc",
    [
        SpreadsheetNotFound("not found"),
        WorksheetNotFound("not found"),
        APIError(response=FakeErrorResponse()),
    ],
)
def test_open_tab_wraps_gspread_errors_as_runtime_error(monkeypatch, exc):
    monkeypatch.setattr(sheets, "_get_client", lambda: FakeClient(exc))

    with pytest.raises(RuntimeError):
        sheets._open_tab("specials")
