"""Shared before-validator that hydrates a registry scenario's ``filing_period``."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ConfigDict, TypeAdapter, ValidationError

from ....core import Period

_SCENARIO_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object], config=ConfigDict(strict=True)
)


def _scenario_mapping(value: object) -> dict[str, object] | None:
    """Return a strictly typed scenario mapping when ``value`` is one."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _SCENARIO_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def hydrate_scenario_filing_period(data: object) -> object:
    """Derive ``filing_period`` from ``filing_year`` + ``period`` for a scenario payload.

    The pydantic ``mode="before"`` validator body shared by the registry
    scenario models (:class:`~cadrumo.domain.calculations.registry.ParityScenario`
    and the calculation scenario). Returns ``data`` unchanged when it is not a
    mapping, already carries ``filing_period``, lacks a well-typed
    ``filing_year``/``period`` pair, or the pair does not form a valid
    :class:`~cadrumo.core.Period`.
    """
    payload = _scenario_mapping(data)
    if payload is None or "filing_period" in payload:
        return data
    filing_year = payload.get("filing_year")
    period = payload.get("period")
    if not isinstance(filing_year, int) or not isinstance(period, str):
        return data
    try:
        filing_period = Period.from_year_and_code(filing_year, period)
    except ValueError:
        return data
    return {**payload, "filing_period": filing_period}
