"""Parsing and comparison rules of the installed calendar parity driver."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from typing import cast

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from ..installed_parity import (
    COMPARED_FIELDS,
    CalendarParityError,
    CalendarWindow,
    compare_rows,
    fresh_cli_calendar,
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


@dataclass(frozen=True, slots=True)
class _Facts:
    """One late row worked from the support horizon: the prior year's second quarter, judged on a September day."""

    period_year: int
    evaluated: date
    opens: date
    cutoff: date
    closes: date
    adjusted: date

    @property
    def overdue(self) -> int:
        return (self.evaluated - self.adjusted).days

    @property
    def address(self) -> str:
        return f"303|{self.period_year}|2T"


@cache
def _facts() -> _Facts:
    horizon = filing_year_envelope().horizon
    closes = date(horizon - 1, 7, 20)
    return _Facts(
        period_year=horizon - 1,
        evaluated=date(horizon, 9, 23),
        opens=date(horizon - 1, 7, 1),
        cutoff=date(horizon - 1, 7, 15),
        closes=closes,
        adjusted=closes + timedelta(days=1),
    )


def _slashed(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def _entry() -> dict[str, object]:
    facts = _facts()
    return {
        "modelo": "303",
        "period": f"{facts.period_year} 2T",
        "evaluated_on": facts.evaluated.isoformat(),
        "closes_on": facts.closes.isoformat(),
        "adjusted_closes_on": facts.adjusted.isoformat(),
        "payment_cutoff_on": facts.cutoff.isoformat(),
        "days_overdue": facts.overdue,
        "local_filing_state": "ready_to_file",
        "aeat_submission_state": "not_observed",
        "justificante_verified": False,
    }


def _text() -> str:
    facts = _facts()
    return (
        f"303\t{facts.period_year} 2T\tlate\topens={facts.opens.isoformat()}\tcloses={facts.closes.isoformat()}"
        f"\tadjusted={facts.adjusted.isoformat()}\tshift={facts.closes.strftime('%A')}"
        "\tholidays=national holidays only; regional and local holidays not checked"
        f"\tpayment_cutoff={facts.cutoff.isoformat()}\tas_of={facts.evaluated.isoformat()}"
        f"\tdays_overdue={facts.overdue}\n"
    )


def _rendered() -> str:
    facts = _facts()
    shift = facts.closes.strftime("%A")
    return (
        f"Modelo 303 {facts.period_year} 2T\n"
        f"Opens: {_slashed(facts.opens)} · Payment: {_slashed(facts.cutoff)}"
        f" · Original close: {_slashed(facts.closes)} · Effective close: {_slashed(facts.adjusted)}"
        f" · Evaluated: {_slashed(facts.evaluated)} · Days overdue: {facts.overdue} · Shift: {shift}\n"
        "Holidays: national holidays only; regional and local holidays not checked\n"
        "Legal: Overdue · Local: Ready to file · AEAT: Not observed · Receipt: Not verified"
        " · Evidence consistency: Clear"
    )


def _cli_rows():
    return parse_cli_calendar({"result": {"entries": [_entry()]}}, _text())


@pytest.mark.parametrize("refused", [False, True])
def test_post_tui_cli_calendar_uses_fresh_proof_for_both_formats(refused: bool) -> None:
    calls: list[tuple[str, bool]] = []

    class ReadbackCli:
        def run(self, arguments, *, command: str, authenticated: bool):
            calls.append(("json", authenticated))
            assert command == "overview.calendar"
            assert "--allow-incomplete" in arguments
            if refused:
                raise InstalledCliError("synthetic fresh-proof refusal")
            return {"result": {"entries": [_entry()]}}

        def run_text(self, _arguments, *, command: str, authenticated: bool) -> str:
            calls.append(("text", authenticated))
            assert command == "overview.calendar"
            return _text()

    cli = cast("InstalledCli", ReadbackCli())
    window = CalendarWindow.for_evaluation(date(filing_year_envelope().horizon, 9, 23))
    if refused:
        with pytest.raises(CalendarParityError, match="fresh-proof refusal"):
            fresh_cli_calendar(cli, window)
        assert calls == [("json", True)]
    else:
        rows, authentication = fresh_cli_calendar(cli, window)
        assert rows == _cli_rows()
        assert authentication == "stdin_secret"
        assert calls == [("json", True), ("text", True)]


def test_window_covers_the_prior_and_current_calendar_years() -> None:
    current = filing_year_envelope().horizon
    window = CalendarWindow.for_evaluation(date(current, 9, 23))
    assert (window.from_date, window.to_date) == (date(current - 1, 1, 1), date(current, 12, 31))


def test_cli_rows_join_json_meaning_with_localized_text() -> None:
    row = _cli_rows()[_facts().address]
    assert row.shift_text == _facts().closes.strftime("%A")
    assert row.holidays_text.startswith("national holidays only")
    assert row.days_overdue == _facts().overdue


def test_json_row_without_a_text_statement_is_refused() -> None:
    with pytest.raises(CalendarParityError, match="text omitted"):
        parse_cli_calendar({"result": {"entries": [_entry()]}}, "")


def test_rendered_detail_is_split_into_every_compared_field() -> None:
    assert set(COMPARED_FIELDS) <= set(parse_tui_detail(_rendered()))


def test_matching_frontends_have_no_mismatch() -> None:
    comparison = compare_rows(_cli_rows(), {_facts().address: parse_tui_detail(_rendered())}, _LABELS)
    assert comparison == [{"row": _facts().address, "fields": len(COMPARED_FIELDS), "mismatched": []}]


def test_a_different_effective_close_is_detected() -> None:
    rendered = _rendered().replace(
        f"Effective close: {_slashed(_facts().adjusted)}", f"Effective close: {_slashed(_facts().closes)}"
    )
    comparison = compare_rows(_cli_rows(), {_facts().address: parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == ["effective_close"]


def test_a_hidden_holiday_uncertainty_is_detected() -> None:
    rendered = _rendered().replace("Holidays: national holidays only; regional and local holidays not checked\n", "")
    comparison = compare_rows(_cli_rows(), {_facts().address: parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == ["holidays"]


def test_different_natural_addresses_are_refused() -> None:
    with pytest.raises(CalendarParityError, match="different natural addresses"):
        compare_rows(_cli_rows(), {f"303|{_facts().period_year}|3T": parse_tui_detail(_rendered())}, _LABELS)


def test_never_captured_aeat_history_expects_unobservable_rows() -> None:
    document = {
        "result": {"entries": [_entry()]},
        "notices": [{"code": "overview.no_aeat_history", "severity": "info"}],
    }
    rows = parse_cli_calendar(document, _text())
    rendered = _rendered().replace(
        "AEAT: Not observed · Receipt: Not verified", "AEAT: Source unobservable · Receipt: Unknown"
    )
    comparison = compare_rows(rows, {_facts().address: parse_tui_detail(rendered)}, _LABELS)
    assert comparison[0]["mismatched"] == []
    stated_as_observed = compare_rows(rows, {_facts().address: parse_tui_detail(_rendered())}, _LABELS)
    assert stated_as_observed[0]["mismatched"] == ["aeat", "receipt"]
