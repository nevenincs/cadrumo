"""Expectations become the same assertions the in-process persona test makes, here over CLI results."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Literal

import pytest

from cadrumo.tests.personas import ExpectedObligation, ExpectedValue, YearToken

from ...persona_table.roles import edition_identities, resolve
from ..assessment import (
    CalculationObservation,
    CalendarView,
    CalendarWindow,
    Explanation,
    asserted_obligations,
    asserted_values,
    assess_obligations,
    assess_value,
    calculated_periods,
    calendar_view,
    expected_verdict,
    explanation,
    next_business_day,
)
from ..receipt import CheckStatus
from .catalogue_support import deadline, envelope, obligation, persona, value_with_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REFUSAL = "ERROR_MODELO_WORK_INPUT_REQUIRED"


def _observed(value: ExpectedValue, *, shift: Decimal = Decimal()) -> CalculationObservation:
    return CalculationObservation(
        casillas={casilla: str(Decimal(amount) + shift) for casilla, amount in value.casillas}
    )


def test_unverified_and_concept_only_values_are_not_asserted() -> None:
    fontanero = persona("autonomo-fontanero")
    stated = [value for _year, value in asserted_values(fontanero, envelope())]
    assert stated
    assert all(value.grounding != "unverified" for value in stated)
    assert all(value.casillas or value.not_sourced or value.refusal for value in stated)
    unverified = replace(value_with_casillas(), grounding="unverified")
    concepts_only = replace(value_with_casillas(), casillas=(), concepts=(("cuota", "1.00"),))
    widened = replace(fontanero, expectations=replace(fontanero.expectations, values=(unverified, concepts_only)))
    assert asserted_values(widened, envelope()) == ()
    assert calculated_periods(widened, envelope()) == ()


def test_unverified_obligations_are_not_asserted() -> None:
    fontanero = persona("autonomo-fontanero")
    hidden = replace(obligation(True), grounding="unverified")
    widened = replace(fontanero, expectations=replace(fontanero.expectations, obligations=(hidden,)))
    assert asserted_obligations(widened, envelope()) == ()


def test_matching_casillas_pass_and_a_differing_or_missing_one_fails() -> None:
    value = value_with_casillas()
    year = value.year.resolve(envelope())
    assert {check.status for check in assess_value(year, value, _observed(value))} == {CheckStatus.PASSED}
    differing = assess_value(year, value, _observed(value, shift=Decimal("0.01")))
    assert {check.status for check in differing} == {CheckStatus.FAIL}
    missing = assess_value(year, value, CalculationObservation(casillas={}))
    assert all(check.status is CheckStatus.FAIL and check.actual is None for check in missing)


def test_an_equal_figure_in_another_scale_passes() -> None:
    value = replace(value_with_casillas(), casillas=(("01", "10.00"),))
    checks = assess_value(2, value, CalculationObservation(casillas={"01": "10"}))
    assert [check.status for check in checks] == [CheckStatus.PASSED]


def test_a_not_sourced_casilla_fails_only_once_the_law_figure_is_carried() -> None:
    value = replace(value_with_casillas(), casillas=(), not_sourced=(("0224", "1500.00"),))
    absent = assess_value(1, value, CalculationObservation(casillas={}))
    other = assess_value(1, value, CalculationObservation(casillas={"0224": "0.00"}))
    carried = assess_value(1, value, CalculationObservation(casillas={"0224": "1500"}))
    assert [check.status for check in absent] == [CheckStatus.PASSED]
    assert [check.status for check in other] == [CheckStatus.PASSED]
    assert [check.status for check in carried] == [CheckStatus.FAIL]
    assert carried[0].kind == "not_sourced"


def test_a_stated_refusal_asserts_its_code() -> None:
    value = replace(value_with_casillas(), refusal=_REFUSAL)
    right = assess_value(1, value, CalculationObservation(refusal=f"{_REFUSAL} REFUSED/INPUT"))
    other = assess_value(1, value, CalculationObservation(refusal="ERROR_SOMETHING_ELSE"))
    calculated = assess_value(1, value, _observed(value))
    assert [(check.status, check.kind) for check in right] == [(CheckStatus.REFUSAL_OK, "refusal")]
    assert [check.status for check in other] == [CheckStatus.REFUSAL_WRONG]
    assert [(check.status, check.actual) for check in calculated] == [(CheckStatus.REFUSAL_WRONG, "calculated")]


def test_an_unexpected_refusal_fails_every_casilla_and_an_unobservable_period_is_a_gap() -> None:
    value = value_with_casillas()
    refused = assess_value(1, value, CalculationObservation(refusal=_REFUSAL))
    unobserved = assess_value(1, value, CalculationObservation(unobserved="no route"))
    assert len(refused) == len(value.casillas)
    assert {check.status for check in refused} == {CheckStatus.FAIL}
    assert {check.status for check in unobserved} == {CheckStatus.GAP}
    expected_refusal = assess_value(1, replace(value, refusal=_REFUSAL), CalculationObservation(unobserved="no route"))
    assert [check.status for check in expected_refusal] == [CheckStatus.GAP]


@pytest.mark.parametrize(
    ("applicable", "verdict"),
    [(True, ("applicable", True)), (False, ("not_applicable", False)), ("unknown", ("incomplete", False))],
)
def test_the_expected_verdict_follows_the_three_states(
    applicable: bool | Literal["unknown"], verdict: tuple[str, bool]
) -> None:
    assert expected_verdict(replace(obligation(True), applicable=applicable)) == verdict


def _windows(item: ExpectedObligation) -> dict[tuple[str, str], CalendarWindow]:
    statutory = deadline().statutory_end.resolve(envelope())
    return {
        (item.modelo, period): CalendarWindow(closes_on=statutory, adjusted_closes_on=statutory)
        for period in item.periods
    }


def test_an_owed_modelo_needs_its_rows_and_a_lacked_one_none() -> None:
    owed, lacked = obligation(True), obligation(False)
    year = owed.year.resolve(envelope())
    calendar = CalendarView(entries=_windows(owed))
    explanations = {
        owed.modelo: Explanation(verdict="applicable", applicable=True),
        lacked.modelo: Explanation(verdict="not_applicable", applicable=False),
    }
    checks = assess_obligations(
        year, (owed, lacked), (), calendar=calendar, explanations=explanations, envelope=envelope()
    )
    assert {check.status for check in checks} == {CheckStatus.PASSED}
    empty = assess_obligations(
        year, (owed,), (), calendar=CalendarView(), explanations=explanations, envelope=envelope()
    )
    assert {check.status for check in empty if check.check == "calendar_row"} == {CheckStatus.FAIL}


def test_a_verdict_the_result_does_not_carry_is_a_gap_and_a_refused_read_fails() -> None:
    owed = obligation(True)
    calendar = CalendarView(entries=_windows(owed))
    for explained, status in (
        (Explanation(applicable=True), CheckStatus.GAP),
        (Explanation(refusal="ERROR_X"), CheckStatus.FAIL),
        (Explanation(verdict="incomplete", applicable=False), CheckStatus.FAIL),
    ):
        checks = assess_obligations(
            1, (owed,), (), calendar=calendar, explanations={owed.modelo: explained}, envelope=envelope()
        )
        assert [check.status for check in checks if check.check == "verdict"] == [status]


def test_calendar_advice_replaces_the_window_rows() -> None:
    advised = replace(obligation(True), calendar_advice="applicable_window_missing")
    explanations = {advised.modelo: Explanation(verdict="applicable", applicable=True)}
    good = CalendarView(advised=frozenset({(advised.modelo, "applicable_window_missing")}))
    bad = CalendarView(entries=_windows(advised))
    good_checks = assess_obligations(1, (advised,), (), calendar=good, explanations=explanations, envelope=envelope())
    bad_checks = assess_obligations(1, (advised,), (), calendar=bad, explanations=explanations, envelope=envelope())
    assert {check.status for check in good_checks} == {CheckStatus.PASSED}
    assert {check.check for check in bad_checks if check.status is CheckStatus.FAIL} == {
        "calendar_advice",
        "calendar_row",
    }


def test_a_refused_calendar_fails_once_without_row_checks() -> None:
    owed = obligation(True)
    checks = assess_obligations(
        1,
        (owed,),
        (),
        calendar=CalendarView(refusal="ERROR_X"),
        explanations={owed.modelo: Explanation(verdict="applicable", applicable=True)},
        envelope=envelope(),
    )
    assert [check.check for check in checks if check.status is CheckStatus.FAIL] == ["calendar"]


def test_a_deadline_closes_on_its_statutory_day_or_the_next_business_day() -> None:
    stated = deadline()
    statutory = stated.statutory_end.resolve(envelope())
    key = (stated.modelo, stated.period)
    on_time = CalendarView(entries={key: CalendarWindow(closes_on=statutory, adjusted_closes_on=statutory)})
    shifted_day = next_business_day(statutory)
    shifted = CalendarView(entries={key: CalendarWindow(closes_on=shifted_day, adjusted_closes_on=shifted_day)})
    late_day = shifted_day + timedelta(days=1)
    late = CalendarView(entries={key: CalendarWindow(closes_on=late_day, adjusted_closes_on=late_day)})
    for calendar, status in ((on_time, CheckStatus.PASSED), (shifted, CheckStatus.PASSED), (late, CheckStatus.FAIL)):
        checks = assess_obligations(1, (), (stated,), calendar=calendar, explanations={}, envelope=envelope())
        assert [check.status for check in checks] == [status]
    missing = assess_obligations(1, (), (stated,), calendar=CalendarView(), explanations={}, envelope=envelope())
    assert [check.status for check in missing] == [CheckStatus.FAIL]


def test_next_business_day_skips_the_weekend() -> None:
    statutory = deadline().statutory_end.resolve(envelope())
    friday = statutory + timedelta(days=(4 - statutory.weekday()) % 7)
    assert next_business_day(friday) == friday + timedelta(days=3)
    assert next_business_day(friday - timedelta(days=1)) == friday


def test_the_calendar_result_keys_rows_by_modelo_and_code_within_one_year() -> None:
    stated = deadline()
    year = stated.year.resolve(envelope())
    statutory = stated.statutory_end.resolve(envelope())
    row = {"closes_on": statutory.isoformat(), "adjusted_closes_on": statutory.isoformat()}
    result = {
        "entries": [
            {**row, "modelo": stated.modelo, "period": f"{year} {stated.period}"},
            {**row, "modelo": stated.modelo, "period": f"{year - 1} {stated.period}"},
        ],
        "coverage": {"advised": [{"modelo": "999", "reason": "applicable_window_missing"}]},
    }
    view = calendar_view(result, year)
    assert set(view.entries) == {(stated.modelo, stated.period)}
    assert view.entries[stated.modelo, stated.period].closes_on == statutory
    assert view.advised == frozenset({("999", "applicable_window_missing")})


def test_the_explanation_result_yields_its_verdict_when_it_carries_one() -> None:
    assert explanation({"verdict": "incomplete", "applicable": False}) == Explanation("incomplete", False)
    assert explanation({"applicable": True}) == Explanation(None, True)


_ROLE = "iva-resultado-regimen-general"
_ROLE_MODELO = "303"
_ROLE_PERIOD = "1T"


def _role_value(*roles: tuple[str, str]) -> ExpectedValue:
    return replace(
        value_with_casillas(),
        modelo=_ROLE_MODELO,
        period=_ROLE_PERIOD,
        year=YearToken(anchor="horizon", offset=-1),
        casillas=(),
        not_sourced=(),
        refusal=None,
        grounding="verified",
        roles=roles,
    )


def test_a_value_stating_only_roles_is_asserted() -> None:
    fontanero = persona("autonomo-fontanero")
    widened = replace(fontanero, expectations=replace(fontanero.expectations, values=(_role_value((_ROLE, "1.00")),)))
    assert len(asserted_values(widened, envelope())) == 1
    assert calculated_periods(widened, envelope())


def test_a_role_is_compared_at_the_casilla_of_the_return_edition() -> None:
    year = envelope().horizon - 1
    casilla = resolve(edition_identities(_ROLE_MODELO, year, _ROLE_PERIOD), _ROLE)
    assert casilla is not None
    value = _role_value((_ROLE, "10.00"))
    passed = assess_value(year, value, CalculationObservation(casillas={casilla: "10"}))
    failed = assess_value(year, value, CalculationObservation(casillas={casilla: "11"}))
    missing = assess_value(year, value, CalculationObservation(casillas={}))
    assert [(check.casilla, check.status) for check in passed] == [(casilla, CheckStatus.PASSED)]
    assert [check.status for check in failed] == [CheckStatus.FAIL]
    assert [check.status for check in missing] == [CheckStatus.FAIL]


def test_an_unresolved_role_is_a_gap_and_never_a_pass() -> None:
    year = envelope().horizon - 1
    value = _role_value(("no-such-continuity-key", "10.00"))
    (check,) = assess_value(year, value, CalculationObservation(casillas={"1": "10"}))
    assert check.status is CheckStatus.GAP
    assert check.casilla is None
    assert check.actual is not None
    assert "role:no-such-continuity-key" in check.actual
