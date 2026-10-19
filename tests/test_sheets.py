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
        ("Who heads Legal?", "org"),
        ("What are the office hours?", "org"),
        ("what's the system status in London?", "items"),
        ("any known outages?", "items"),
        ("is the whole menu gluten free?", None),
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


# --- get_org / get_items / find_org_rows / find_item_rows (mocked worksheet) ----

ORG_ROWS = [
    {"Type": "Office", "Name": "London", "Contact": "Fiona", "Notes": "Mon-Fri 8:30-4:30", "Is Active": "TRUE"},
    {"Type": "Office", "Name": "Austin", "Contact": "Travis", "Notes": "Mon-Fri 8-5", "Is Active": "TRUE"},
    {"Type": "Department", "Name": "Legal", "Contact": "Rachel (Head of Legal)", "Notes": "", "Is Active": "TRUE"},
    {"Type": "Department", "Name": "Old Team", "Contact": "Nobody", "Notes": "", "Is Active": "FALSE"},
]

ITEM_ROWS = [
    {"App": "it-assistant", "Tenant": "London", "Category": "System Status", "Name": "Email", "Is Active": "TRUE"},
    {"App": "it-assistant", "Tenant": "Austin", "Category": "System Status", "Name": "VPN", "Is Active": "TRUE"},
    {"App": "product-support", "Tenant": "Product A", "Category": "Known Outage", "Name": "SSO", "Is Active": "TRUE"},
    {"App": "hr-assistant", "Tenant": "Sales", "Category": "Announcement", "Name": "Expired", "Is Active": "FALSE"},
]


def test_get_org_skips_inactive_and_filters_case_insensitively(monkeypatch):
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ORG_ROWS))

    assert [r["Name"] for r in sheets.get_org()] == ["London", "Austin", "Legal"]
    assert [r["Name"] for r in sheets.get_org(org_type="office")] == ["London", "Austin"]
    assert [r["Name"] for r in sheets.get_org(name="LEGAL")] == ["Legal"]


def test_get_items_skips_inactive_and_filters_by_category_and_tenant(monkeypatch):
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ITEM_ROWS))

    assert len(sheets.get_items()) == 3
    assert [r["Name"] for r in sheets.get_items(category="system status", tenant="austin")] == ["VPN"]


def test_find_org_rows_matches_name_first(monkeypatch):
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ORG_ROWS))

    assert [r["Name"] for r in sheets.find_org_rows("Who heads Legal?")] == ["Legal"]


def test_find_org_rows_falls_back_to_type(monkeypatch):
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ORG_ROWS))

    assert [r["Name"] for r in sheets.find_org_rows("What are the office hours?")] == ["London", "Austin"]


def test_find_org_rows_empty_when_nothing_matches(monkeypatch):
    # e.g. a menu question that happens to say "who" - caller falls through to the engine
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ORG_ROWS))

    assert sheets.find_org_rows("who makes the dragon roll?") == []


def test_find_item_rows_matches_category_stem_and_narrows_by_tenant(monkeypatch):
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ITEM_ROWS))

    assert [r["Name"] for r in sheets.find_item_rows("any outages?")] == ["SSO"]
    assert [r["Name"] for r in sheets.find_item_rows("system status in London?")] == ["Email"]


def test_find_item_rows_ignores_partial_word_tenants(monkeypatch):
    # "Product A" must not match the article "a" in an unrelated question
    monkeypatch.setattr(sheets, "_open_tab", lambda tab: FakeWorksheet(ITEM_ROWS))

    assert [r["Name"] for r in sheets.find_item_rows("is there a known outage?")] == ["SSO"]


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
