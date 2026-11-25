"""Typed public IVA annual readback projection and strict decimal decoding."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import cast

from .cli_journey import (
    IvaCliJourneyError,
)


def decimal_casilla(payload: Mapping[str, object], casilla_id: str) -> Decimal:
    """Read a casilla from the calculation payload as a two-decimal Decimal."""
    values = payload.get("casilla_values")
    if not isinstance(values, Mapping):
        raise IvaCliJourneyError("Modelo calculation returned no public casilla projection")
    try:
        return Decimal(str(values.get(casilla_id))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo calculation returned no decimal {casilla_id}") from exc


def period_code(value: object, *, filing_year: int) -> str | None:
    """Return the period code when the value belongs to the given filing year, else None."""
    if not isinstance(value, Mapping) or value.get("filing_year") != filing_year:
        return None
    code = value.get("code")
    return code if isinstance(code, str) else None


def unique_row(
    payload: Mapping[str, object], collection_key: str, id_key: str, expected_id: str
) -> Mapping[str, object]:
    """Return the single row whose identifier matches, refusing a missing or ambiguous match."""
    rows = payload.get(collection_key)
    if not isinstance(rows, list):
        raise IvaCliJourneyError("fresh-process public list returned no collection")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get(id_key) == expected_id]
    if len(matches) != 1:
        raise IvaCliJourneyError("fresh-process public list did not return one expected identity")
    return cast(Mapping[str, object], matches[0])
