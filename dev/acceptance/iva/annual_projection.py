"""Typed public IVA annual readback projection and strict decimal decoding."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import cast

from .cli_journey import (
    IvaCliJourneyError,
)


def _decimal_casilla(payload: Mapping[str, object], casilla_id: str) -> Decimal:
    values = payload.get("casilla_values")
    if not isinstance(values, Mapping):
        raise IvaCliJourneyError("Modelo calculation returned no public casilla projection")
    try:
        return Decimal(str(values.get(casilla_id))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise IvaCliJourneyError(f"Modelo calculation returned no decimal {casilla_id}") from exc


def _period_code(value: object, *, filing_year: int) -> str | None:
    if not isinstance(value, Mapping) or value.get("filing_year") != filing_year:
        return None
    code = value.get("code")
    return code if isinstance(code, str) else None


def _unique_row(
    payload: Mapping[str, object], collection_key: str, id_key: str, expected_id: str
) -> Mapping[str, object]:
    rows = payload.get(collection_key)
    if not isinstance(rows, list):
        raise IvaCliJourneyError("fresh-process public list returned no collection")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get(id_key) == expected_id]
    if len(matches) != 1:
        raise IvaCliJourneyError("fresh-process public list did not return one expected identity")
    return cast(Mapping[str, object], matches[0])
