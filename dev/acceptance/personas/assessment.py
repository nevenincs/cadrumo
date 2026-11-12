"""Turn a persona's hand-grounded expectations into assertions on what the installed CLI reported.

The semantics are those of the in-process persona test
(``src/cadrumo/entrypoints/tests/test_persona_obligations.py``): an
expectation grounded ``unverified`` is a known gap and is not asserted; a value
stated only as concepts carries no casilla and is not asserted; a ``refusal``
asserts the error code the period's calculation settles with; a ``not_sourced``
casilla asserts that the application does not carry the law's figure; an
obligation's applicability comes from the overview explanation and its windows
and deadlines from the overview calendar. Where a modelo's obligations of one
year expect different verdicts for different periods, the modelo-wide
explanation cannot state them, and each period's verdict is read from the
calendar instead: its window row, or the verdict of its suppressed row. Nothing here edits an expectation to
agree with a run: every function only compares.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from cadrumo.tests.personas import (
    ExpectedDeadline,
    ExpectedObligation,
    ExpectedValue,
    Persona,
    YearEnvelope,
    per_period_modelos,
    values_in_force,
)

from ..persona_table.roles import edition_identities, resolve
from .receipt import CheckStatus, ObligationCheck, ValueCheck

_ABSENT = "absent"
_PRESENT = "present"


# -- what is asserted, per year --------------------------------------------------------------------------------------


def _states_figures(value: ExpectedValue) -> bool:
    return (
        bool(value.casillas or value.roles or value.not_sourced or value.refusal is not None)
        and value.grounding != "unverified"
    )


def asserted_values(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[int, ExpectedValue], ...]:
    """Every value the journey asserts, with its resolved year: casillas, not-sourced casillas or a refusal.

    Where a provision governs the year, the value limited to it stands in for the plain one.
    """
    return tuple(
        (year, value)
        for year, value in values_in_force(persona.expectations.values, envelope)
        if _states_figures(value)
    )


def asserted_obligations(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[int, ExpectedObligation], ...]:
    """Every obligation the journey asserts, with its resolved year."""
    return tuple(
        (item.year.resolve(envelope), item)
        for item in persona.expectations.obligations
        if item.grounding != "unverified"
    )


def asserted_deadlines(persona: Persona, envelope: YearEnvelope, year: int) -> tuple[ExpectedDeadline, ...]:
    """The deadlines of ``year`` the journey asserts."""
    return tuple(
        item
        for item in persona.expectations.deadlines
        if item.year.resolve(envelope) == year and item.grounding != "unverified"
    )


def calculated_periods(persona: Persona, envelope: YearEnvelope) -> tuple[tuple[str, int, str], ...]:
    """Each ``(modelo, year, period)`` whose calculation the asserted values read, once, in a stable order."""
    seen = {(value.modelo, year, value.period) for year, value in asserted_values(persona, envelope)}
    return tuple(sorted(seen, key=lambda item: (item[1], item[0], item[2])))


# -- values ----------------------------------------------------------------------------------------------------------


def decimal_or_none(value: object) -> Decimal | None:
    """The value as a Decimal, or ``None`` when it is not a number."""
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@dataclass(frozen=True, slots=True)
class CalculationObservation:
    """What the CLI reported for one period: its casilla values, its refusal, or why it could not be observed."""

    casillas: Mapping[str, str] = field(default_factory=dict)
    refusal: str | None = None
    unobserved: str | None = None


def _refusal_checks(year: int, value: ExpectedValue, observed: CalculationObservation) -> tuple[ValueCheck, ...]:
    stated = value.refusal or ""
    if observed.unobserved is not None:
        status, actual = CheckStatus.GAP, observed.unobserved
    elif observed.refusal is not None and stated in observed.refusal:
        status, actual = CheckStatus.REFUSAL_OK, observed.refusal
    else:
        status, actual = CheckStatus.REFUSAL_WRONG, observed.refusal or "calculated"
    return (
        ValueCheck(
            year=year,
            modelo=value.modelo,
            period=value.period,
            casilla=None,
            kind="refusal",
            expected=stated,
            actual=actual,
            status=status,
            legal_ref=value.legal_ref,
        ),
    )


def _casilla_status(expected: Decimal | None, actual: Decimal | None) -> CheckStatus:
    return CheckStatus.PASSED if actual == expected else CheckStatus.FAIL


def _not_sourced_status(law: Decimal | None, actual: Decimal | None) -> CheckStatus:
    """A not-sourced casilla fails only once the application carries the law's figure."""
    return CheckStatus.FAIL if actual is not None and actual == law else CheckStatus.PASSED


def _unreached_status(observed: CalculationObservation) -> tuple[CheckStatus, str] | None:
    if observed.unobserved is not None:
        return CheckStatus.GAP, observed.unobserved
    if observed.refusal is not None:
        return CheckStatus.FAIL, f"refused: {observed.refusal}"
    return None


def _stated_figures(year: int, value: ExpectedValue) -> list[tuple[str, str | None, str, str | None]]:
    """Each stated figure as ``(kind, casilla, amount, unresolved role)``; a role is placed in the return's edition."""
    stated: list[tuple[str, str | None, str, str | None]] = [
        ("casilla", casilla, amount, None) for casilla, amount in value.casillas
    ]
    if value.roles:
        held = edition_identities(value.modelo, year, value.period)
        for key, amount in value.roles:
            casilla = resolve(held, key)
            stated.append(("casilla", casilla, amount, None if casilla is not None else f"role:{key}"))
    stated += [("not_sourced", casilla, amount, None) for casilla, amount in value.not_sourced]
    return stated


def _figure_status(
    kind: str, expected: Decimal | None, actual: Decimal | None, unreached: tuple[CheckStatus, str] | None
) -> tuple[CheckStatus, str | None]:
    shown = None if actual is None else str(actual)
    if unreached is not None:
        return unreached
    if kind == "casilla":
        return _casilla_status(expected, actual), shown
    return _not_sourced_status(expected, actual), shown


def _figure_checks(year: int, value: ExpectedValue, observed: CalculationObservation) -> tuple[ValueCheck, ...]:
    unreached = _unreached_status(observed)
    rows: list[ValueCheck] = []
    for kind, casilla, amount, unresolved in _stated_figures(year, value):
        if casilla is None:
            status, shown = CheckStatus.GAP, f"{unresolved} unresolved in the return's edition"
        else:
            raw = observed.casillas.get(casilla)
            status, shown = _figure_status(
                kind, decimal_or_none(amount), None if raw is None else decimal_or_none(raw), unreached
            )
        rows.append(
            ValueCheck(
                year=year,
                modelo=value.modelo,
                period=value.period,
                casilla=casilla,
                kind="casilla" if kind == "casilla" else "not_sourced",
                expected=amount,
                actual=shown,
                status=status,
                legal_ref=value.legal_ref,
            )
        )
    return tuple(rows)


def assess_value(year: int, value: ExpectedValue, observed: CalculationObservation) -> tuple[ValueCheck, ...]:
    """The checks one stated value yields against what the CLI reported for its period."""
    if value.refusal is not None:
        return _refusal_checks(year, value, observed)
    return _figure_checks(year, value, observed)


# -- obligations -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CalendarWindow:
    """One calendar row's statutory and business-day-adjusted closing dates."""

    closes_on: date
    adjusted_closes_on: date


@dataclass(frozen=True, slots=True)
class CalendarView:
    """The calendar rows of one filing year by ``(modelo, period code)``, and the modelos it advises instead.

    ``suppressed`` holds the verdict of each obligation the calendar leaves off
    its rows, as it reports them when asked to show suppressed obligations.
    """

    entries: Mapping[tuple[str, str], CalendarWindow] = field(default_factory=dict)
    advised: frozenset[tuple[str, str]] = frozenset()
    suppressed: Mapping[tuple[str, str], str] = field(default_factory=dict)
    refusal: str | None = None


@dataclass(frozen=True, slots=True)
class Explanation:
    """One modelo's applicability as the overview explanation states it, or why it was not read."""

    verdict: str | None = None
    applicable: bool | None = None
    refusal: str | None = None


def expected_verdict(item: ExpectedObligation) -> tuple[str, bool]:
    """The explanation verdict and applicability an obligation expects."""
    if item.applicable == "unknown":
        return "incomplete", False
    if item.applicable is True:
        return "applicable", True
    return "not_applicable", False


def _render_verdict(verdict: str | None, applicable: bool | None) -> str:
    return f"{verdict}/{applicable}"


def _verdict_check(year: int, item: ExpectedObligation, explained: Explanation | None) -> ObligationCheck:
    verdict, applicable = expected_verdict(item)
    if explained is None or explained.refusal is not None:
        status, actual = CheckStatus.FAIL, f"refused: {explained.refusal}" if explained else "not read"
    elif explained.verdict is None:
        status, actual = CheckStatus.GAP, "the explanation result carries no applicability verdict"
    else:
        observed = (explained.verdict, explained.applicable)
        status = CheckStatus.PASSED if observed == (verdict, applicable) else CheckStatus.FAIL
        actual = _render_verdict(*observed)
    return ObligationCheck(
        year=year,
        modelo=item.modelo,
        period=None,
        check="verdict",
        expected=_render_verdict(verdict, applicable),
        actual=actual,
        status=status,
        legal_ref=item.legal_ref,
    )


def calendar_verdict(calendar: CalendarView, modelo: str, period: str) -> str:
    """The verdict the calendar shows for one period: applicable with a window row, else its suppressed verdict."""
    if (modelo, period) in calendar.entries:
        return "applicable"
    return calendar.suppressed.get((modelo, period), _ABSENT)


def _period_verdict_checks(year: int, item: ExpectedObligation, calendar: CalendarView) -> list[ObligationCheck]:
    if calendar.refusal is not None and not calendar.entries:
        return []
    verdict, _applicable = expected_verdict(item)
    checks: list[ObligationCheck] = []
    for period in item.periods:
        actual = calendar_verdict(calendar, item.modelo, period)
        checks.append(
            ObligationCheck(
                year=year,
                modelo=item.modelo,
                period=period,
                check="verdict",
                expected=verdict,
                actual=actual,
                status=CheckStatus.PASSED if actual == verdict else CheckStatus.FAIL,
                legal_ref=item.legal_ref,
            )
        )
    return checks


def _row_check(year: int, item: ExpectedObligation, period: str, *, expected: str, actual: str) -> ObligationCheck:
    return ObligationCheck(
        year=year,
        modelo=item.modelo,
        period=period,
        check="calendar_row",
        expected=expected,
        actual=actual,
        status=CheckStatus.PASSED if expected == actual else CheckStatus.FAIL,
        legal_ref=item.legal_ref,
    )


def _advice_checks(year: int, item: ExpectedObligation, calendar: CalendarView) -> list[ObligationCheck]:
    advice = item.calendar_advice or ""
    advised = (item.modelo, advice) in calendar.advised
    checks = [
        ObligationCheck(
            year=year,
            modelo=item.modelo,
            period=None,
            check="calendar_advice",
            expected=advice,
            actual=advice if advised else None,
            status=CheckStatus.PASSED if advised else CheckStatus.FAIL,
            legal_ref=item.legal_ref,
        )
    ]
    checks.extend(
        _row_check(
            year,
            item,
            period,
            expected=_ABSENT,
            actual=_PRESENT if (item.modelo, period) in calendar.entries else _ABSENT,
        )
        for period in item.periods
    )
    return checks


def _calendar_checks(year: int, item: ExpectedObligation, calendar: CalendarView) -> list[ObligationCheck]:
    """A modelo the persona must file has a window row for each period; one it lacks, or cannot decide, has none."""
    if item.calendar_advice is not None:
        return _advice_checks(year, item, calendar)
    if calendar.refusal is not None and not calendar.entries:
        return []
    wanted = _PRESENT if item.applicable is True else _ABSENT
    return [
        _row_check(
            year,
            item,
            period,
            expected=wanted,
            actual=_PRESENT if (item.modelo, period) in calendar.entries else _ABSENT,
        )
        for period in item.periods
    ]


def next_business_day(day: date) -> date:
    """The first weekday after ``day``."""
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following


def _deadline_check(
    deadline: ExpectedDeadline, year: int, calendar: CalendarView, envelope: YearEnvelope
) -> ObligationCheck:
    statutory = deadline.statutory_end.resolve(envelope)
    window = calendar.entries.get((deadline.modelo, deadline.period))
    if window is None:
        status, actual = CheckStatus.FAIL, None
    else:
        meets = window.closes_on == statutory or window.adjusted_closes_on == next_business_day(statutory)
        status = CheckStatus.PASSED if meets else CheckStatus.FAIL
        actual = f"{window.closes_on.isoformat()} (adjusted {window.adjusted_closes_on.isoformat()})"
    return ObligationCheck(
        year=year,
        modelo=deadline.modelo,
        period=deadline.period,
        check="deadline",
        expected=statutory.isoformat(),
        actual=actual,
        status=status,
        legal_ref=deadline.legal_ref,
    )


def _calendar_refusal_check(year: int, calendar: CalendarView) -> list[ObligationCheck]:
    if calendar.refusal is None:
        return []
    return [
        ObligationCheck(
            year=year,
            modelo="*",
            period=None,
            check="calendar",
            expected="calendar read",
            actual=f"refused: {calendar.refusal}",
            status=CheckStatus.FAIL,
            legal_ref=(),
        )
    ]


def assess_obligations(
    year: int,
    obligations: Sequence[ExpectedObligation],
    deadlines: Sequence[ExpectedDeadline],
    *,
    calendar: CalendarView,
    explanations: Mapping[str, Explanation],
    envelope: YearEnvelope,
) -> tuple[ObligationCheck, ...]:
    """The checks one year's obligations and deadlines yield against the overview reads.

    A modelo of :func:`per_period_modelos` has its verdict checked per period
    against the calendar rather than against its explanation.
    """
    checks = _calendar_refusal_check(year, calendar)
    per_period = per_period_modelos(obligations)
    for item in obligations:
        if item.modelo in per_period:
            checks.extend(_period_verdict_checks(year, item, calendar))
        else:
            checks.append(_verdict_check(year, item, explanations.get(item.modelo)))
        checks.extend(_calendar_checks(year, item, calendar))
    checks.extend(_deadline_check(deadline, year, calendar, envelope) for deadline in deadlines)
    return tuple(checks)


# -- the CLI's overview results --------------------------------------------------------------------------------------


def _period_parts(text: str) -> tuple[int | None, str]:
    """The year and code of a calendar period rendered ``"<year> <code>"``; ``None`` when it names no year."""
    head, _, code = text.rpartition(" ")
    return (int(head) if head.isdigit() else None), code


def _calendar_window(row: Mapping[str, object]) -> CalendarWindow:
    return CalendarWindow(
        closes_on=date.fromisoformat(str(row["closes_on"])),
        adjusted_closes_on=date.fromisoformat(str(row["adjusted_closes_on"])),
    )


def _advised(result: Mapping[str, object]) -> frozenset[tuple[str, str]]:
    coverage = result.get("coverage")
    rows = coverage.get("advised") if isinstance(coverage, Mapping) else None
    return frozenset((str(row.get("modelo")), str(row.get("reason"))) for row in rows or () if isinstance(row, Mapping))


def _suppressed(result: Mapping[str, object], year: int) -> dict[tuple[str, str], str]:
    suppressed: dict[tuple[str, str], str] = {}
    rows = result.get("suppressed_entries")
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        row_year, code = _period_parts(str(row.get("period", "")))
        if row_year == year:
            suppressed[str(row.get("modelo")), code] = str(row.get("verdict"))
    return suppressed


def calendar_view(result: Mapping[str, object], year: int) -> CalendarView:
    """The rows and suppressed obligations of filing year ``year`` from the ``app overview calendar`` JSON result.

    The CLI row names its period as ``"<year> <code>"`` and carries no separate
    filing year, so the period's year stands for it.
    """
    entries: dict[tuple[str, str], CalendarWindow] = {}
    rows = result.get("entries")
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, Mapping):
            continue
        row_year, code = _period_parts(str(row.get("period", "")))
        if row_year == year:
            entries[str(row.get("modelo")), code] = _calendar_window(row)
    return CalendarView(entries=entries, advised=_advised(result), suppressed=_suppressed(result, year))


def explanation(result: Mapping[str, object]) -> Explanation:
    """One modelo's verdict and applicability from the ``app overview explain`` JSON result."""
    verdict = result.get("verdict")
    applicable = result.get("applicable")
    return Explanation(
        verdict=str(verdict) if isinstance(verdict, str) else None,
        applicable=applicable if isinstance(applicable, bool) else None,
    )
