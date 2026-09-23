"""Parsing and comparison rules of the installed calendar parity driver."""

from __future__ import annotations

from datetime import date

import pytest

from ..installed_parity import (
    COMPARED_FIELDS,
    CalendarParityError,
    CalendarWindow,
    compare_rows,
    parse_cli_calendar,
    parse_tui_detail,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LABELS = {
    "none": "None",
    "receipt.verified": "Verified",
    "receipt.not_verified": "Not verified",
    "local.ready_to_file": "Ready to file",
    "local.not_started": "Not started",
    "aeat.not_observed": "Not observed",
    "aeat.unknown": "Source unobservable",
    "receipt.unknown": "Unknown",
}

_ENTRY = {
    "modelo": "303",
    "period": "2025 2T",
    "evaluated_on": "2026-09-23",
    "closes_on": "2025-07-20",
    "adjusted_closes_on": "2025-07-21",
    "payment_cutoff_on": "2025-07-15",
    "days_overdue": 429,
    "local_filing_state": "ready_to_file",
    "aeat_submission_state": "not_observed",
    "justificante_verified": False,
}

_TEXT = (
    "303\t2025 2T\tlate\topens=2025-07-01\tcloses=2025-07-20\tadjusted=2025-07-21\tshift=Sunday"
    "\tholidays=national holidays only; regional and local holidays not checked"
    "\tpayment_cutoff=2025-07-15\tas_of=2026-09-23\tdays_overdue=429\n"
)

_RENDERED = (
    "Modelo 303 2025 2T\n"
    "Opens: 01/07/2025 · Payment: 15/07/2025 · Original close: 20/07/2025 · Effective close: 21/07/2025"
    " · Evaluated: 23/09/2026 · Days overdue: 429 · Shift: Sunday\n"
    "Holidays: national holidays only; regional and local holidays not checked\n"
    "Legal: Overdue · Local: Ready to file · AEAT: Not observed · Receipt: Not verified · Evidence consistency: Clear"
)


def _cli_rows():
    return parse_cli_calendar({"result": {"entries": [_ENTRY]}}, _TEXT)


def test_window_covers_the_prior_and_current_calendar_years() -> None:
    window = CalendarWindow.for_evaluation(date(2026, 9, 23))
    assert (window.from_date, window.to_date) == (date(2025, 1, 1), date(2026, 12, 31))


def test_cli_rows_join_json_meaning_with_localized_text() -> None:
    row = _cli_rows()["303|2025|2T"]
    assert row.shift_text == "Sunday"
    assert row.holidays_text.startswith("national holidays only")
    assert row.days_overdue == 429


def test_json_row_without_a_text_statement_is_refused() -> None:
    with pytest.raises(CalendarParityError, match="text omitted"):
        parse_cli_calendar({"result": {"entries": [_ENTRY]}}, "")


def test_rendered_detail_is_split_into_every_compared_field() -> None:
    assert set(COMPARED_FIELDS) <= set(parse_tui_detail(_RENDERED))


def test_matching_frontends_have_no_mismatch() -> None:
    comparison = compare_rows(_cli_rows(), {"303|2025|2T": parse_tui_detail(_RENDERED)}, _LABELS)
    assert comparison == [{"row": "303|2025|2T", "fields": len(COMPARED_FIELDS), "mismatched": []}]


def test_a_different_effective_close_is_detected() -> None:
    rendered = _RENDERED.replace("Effective close: 21/07/2025", "Effective close: 20/07/2025")
    comparison = compare_rows(_cli_rows(), {"303|2025|2T": parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == ["effective_close"]


def test_a_hidden_holiday_uncertainty_is_detected() -> None:
    rendered = _RENDERED.replace("Holidays: national holidays only; regional and local holidays not checked\n", "")
    comparison = compare_rows(_cli_rows(), {"303|2025|2T": parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == ["holidays"]


def test_different_natural_addresses_are_refused() -> None:
    with pytest.raises(CalendarParityError, match="different natural addresses"):
        compare_rows(_cli_rows(), {"303|2025|3T": parse_tui_detail(_RENDERED)}, _LABELS)


def test_never_captured_aeat_history_expects_unobservable_rows() -> None:
    document = {
        "result": {"entries": [_ENTRY]},
        "notices": [{"code": "overview.no_aeat_history", "severity": "info"}],
    }
    rows = parse_cli_calendar(document, _TEXT)
    rendered = _RENDERED.replace(
        "AEAT: Not observed · Receipt: Not verified", "AEAT: Source unobservable · Receipt: Unknown"
    )
    comparison = compare_rows(rows, {"303|2025|2T": parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == []
    stated_as_observed = compare_rows(rows, {"303|2025|2T": parse_tui_detail(_RENDERED)}, _LABELS)
    assert stated_as_observed[0]["mismatched"] == ["aeat", "receipt"]
