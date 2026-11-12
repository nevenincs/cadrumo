"""Read what the CLI reports for each asserted obligation and value, and run a whole journey."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from cadrumo.tests.personas import (
    ExpectedObligation,
)

from .assessment import (
    CalculationObservation,
    CalendarView,
    Explanation,
    asserted_deadlines,
    asserted_obligations,
    asserted_values,
    assess_obligations,
    assess_value,
    calculated_periods,
    calendar_view,
    explanation,
)
from .history import calculate_return, replay_history
from .journey import (
    Journey,
    found,
)
from .receipt import ObligationCheck, ValueCheck
from .replay import (
    add_documents,
    classify_rows,
    complete_setup,
    create_profile,
    import_ledger,
    open_inventory,
    record_invoices,
    replay_household,
    replay_profile,
    replay_withholding,
)

# -- assessment ------------------------------------------------------------------------------------------------------


_INCOMPLETE_PROFILE = "REFUSED_CLI_BOUNDARY"
"""The calendar's refusal of a profile whose answers it depends on are missing."""


def _calendar(journey: Journey, year: int) -> CalendarView:
    args = (
        "app",
        "overview",
        "calendar",
        "--from",
        f"{year}-01-01",
        "--to",
        f"{year + 1}-12-31",
        "--show-suppressed",
    )
    reply = journey.run(f"obligations.{year}.calendar", args)
    if not reply.ok and reply.refusal is not None and reply.refusal.startswith(_INCOMPLETE_PROFILE):
        journey.note(
            f"obligations.{year}.calendar: the CLI refuses the calendar of a profile with unanswered facts unless "
            "--allow-incomplete is given, where the in-process overview read answers; read again with it"
        )
        reply = journey.run(f"obligations.{year}.calendar_incomplete", (*args, "--allow-incomplete"))
    if not reply.ok:
        return CalendarView(refusal=reply.refusal)
    return calendar_view(reply.result, year)


def _explanation(journey: Journey, year: int, modelo: str) -> Explanation:
    args = ("app", "overview", "explain", modelo, "--year", str(year))
    reply = journey.run(f"obligations.{year}.explain.{modelo}", args)
    if not reply.ok:
        return Explanation(refusal=reply.refusal)
    return explanation(reply.result)


def assess_year_obligations(journey: Journey) -> tuple[ObligationCheck, ...]:
    """Every asserted obligation and deadline, read from the overview calendar and explanations of its year."""
    by_year: dict[int, list[ExpectedObligation]] = {}
    for year, item in asserted_obligations(journey.persona, journey.envelope):
        by_year.setdefault(year, []).append(item)
    checks: list[ObligationCheck] = []
    for year, items in sorted(by_year.items()):
        calendar = _calendar(journey, year)
        modelos = sorted({item.modelo for item in items})
        explanations = {modelo: _explanation(journey, year, modelo) for modelo in modelos}
        deadlines = asserted_deadlines(journey.persona, journey.envelope, year)
        checks.extend(
            assess_obligations(
                year, items, deadlines, calendar=calendar, explanations=explanations, envelope=journey.envelope
            )
        )
    return tuple(checks)


def _casillas(result: Mapping[str, Any]) -> dict[str, str]:
    values = found(result, "casilla_values")
    if isinstance(values, Mapping):
        return {str(key): str(value) for key, value in values.items()}
    if isinstance(values, list):
        return {str(found(item, "key") or found(item, "casilla_id")): str(found(item, "value")) for item in values}
    return {}


def observe_period(journey: Journey, modelo: str, year: int, period: str) -> CalculationObservation:
    """What the CLI holds for one period: the replayed revision's casillas, or a fresh calculation's."""
    step = f"values.{modelo}.{year}.{period}"
    revision_id = journey.revisions.get((modelo, year, period))
    if revision_id is not None:
        reply = journey.run(f"{step}.revision", ("app", "modelo", "work", "revision", revision_id))
    else:
        reply, _ = calculate_return(journey, step, modelo=modelo, year=year, period=period, last=period)
    if not reply.ok:
        return CalculationObservation(refusal=reply.refusal)
    casillas = _casillas(reply.result)
    if not casillas:
        return CalculationObservation(unobserved=f"{step}: the result carries no casilla values")
    return CalculationObservation(casillas=casillas)


def assess_values(journey: Journey) -> tuple[ValueCheck, ...]:
    """Every asserted value against what the CLI calculated for its period."""
    observed = {
        (modelo, year, period): observe_period(journey, modelo, year, period)
        for modelo, year, period in calculated_periods(journey.persona, journey.envelope)
    }
    checks: list[ValueCheck] = []
    for year, value in asserted_values(journey.persona, journey.envelope):
        checks.extend(assess_value(year, value, observed[value.modelo, year, value.period]))
    return tuple(checks)


REPLAY: tuple[Callable[[Journey], None], ...] = (
    replay_profile,
    replay_household,
    replay_withholding,
    import_ledger,
    classify_rows,
    record_invoices,
    add_documents,
    open_inventory,
    complete_setup,
    replay_history,
)
"""The replay, in the in-process materialiser's order."""


def run_journey(journey: Journey) -> tuple[tuple[ObligationCheck, ...], tuple[ValueCheck, ...]]:
    """Replay the persona, then assess its obligations and values against what the CLI reports."""
    if not create_profile(journey):
        journey.note("profile.create refused, so nothing else could run")
        return (), ()
    for replay in REPLAY:
        replay(journey)
    for block in journey.persona.declared_blocks():
        journey.note(f"{block}: a declarative block no production operation records; not loaded")
    return assess_year_obligations(journey), assess_values(journey)
