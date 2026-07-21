"""Shared before-validator that hydrates a registry scenario's ``filing_period``."""

from __future__ import annotations

from collections.abc import Mapping

from ....core import Period


def hydrate_scenario_filing_period(data: object) -> object:
    """Derive ``filing_period`` from ``filing_year`` + ``period`` for a scenario payload.

    The pydantic ``mode="before"`` validator body shared by the registry
    scenario models (:class:`~cadrumo.domain.calculations.registry.ParityScenario`
    and the calculation scenario). Returns ``data`` unchanged when it is not a
    mapping, already carries ``filing_period``, lacks a well-typed
    ``filing_year``/``period`` pair, or the pair does not form a valid
    :class:`~cadrumo.core.Period`.
    """
    if not isinstance(data, Mapping) or "filing_period" in data:
        return data
    filing_year = data.get("filing_year")
    period = data.get("period")
    if not isinstance(filing_year, int) or not isinstance(period, str):
        return data
    try:
        filing_period = Period.from_year_and_code(filing_year, period)
    except ValueError:
        return data
    return {**data, "filing_period": filing_period}
