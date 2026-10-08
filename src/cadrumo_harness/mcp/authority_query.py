"""Pinned, public tax-authority queries exposed by the MCP surface."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from cadrumo.application.modelo.registry_discovery import (
    registry_bindings_for_year,
    registry_casilla_for_registry_scope,
    registry_casillas_for_registry_scope,
    registry_describe_modelo_for_registry_scope,
    registry_formulas_for_registry_scope,
    registry_list_modelos,
    registry_support_matrix,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from .protocol_contract import public_value

_ALLOWED_COORDINATES = {
    "modelos": {"filing_year"},
    "support": set(),
    "bindings": {"modelo", "filing_year", "as_of"},
    "describe": {"modelo", "filing_year", "period", "as_of"},
    "casillas": {"modelo", "filing_year", "period", "as_of"},
    "casilla": {"modelo", "filing_year", "period", "casilla", "as_of"},
    "formulas": {"modelo", "filing_year", "period", "as_of"},
}


def _required_coordinates(query: str) -> set[str]:
    if query == "bindings":
        required = {"modelo", "filing_year"}
    elif query in {"modelos", "support"}:
        required: set[str] = set()
    else:
        required = {"modelo", "filing_year", "period"}
    if query == "casilla":
        required.add("casilla")
    return required


def _validated_query(args: dict[str, Any]) -> tuple[str, date | None]:
    query = cast(str, args["query"])
    if query not in _ALLOWED_COORDINATES:
        raise ValueError("unknown authority query")
    supplied = set(args) - {"query"}
    if supplied - _ALLOWED_COORDINATES[query] or _required_coordinates(query) - supplied:
        raise ValueError("invalid authority query coordinates")
    if "filing_year" in args and not 1900 <= args["filing_year"] <= 9999:
        raise ValueError("invalid filing year")
    as_of = date.fromisoformat(args["as_of"]) if "as_of" in args else None
    return query, as_of


def _authority_report(query: str, args: dict[str, Any], as_of: date | None, operation: Any) -> object:
    if query == "modelos":
        return registry_list_modelos(year=args.get("filing_year"), operation=operation)
    if query == "support":
        return registry_support_matrix(operation=operation)
    if query == "bindings":
        return registry_bindings_for_year(
            args["modelo"], filing_year=args["filing_year"], as_of=as_of, operation=operation
        )
    return _scoped_authority_report(query, args, as_of, operation)


def _scoped_authority_report(query: str, args: dict[str, Any], as_of: date | None, operation: Any) -> object:
    filing_year, period = args["filing_year"], args["period"]
    if query == "describe":
        return registry_describe_modelo_for_registry_scope(
            args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
        )
    if query == "casillas":
        return registry_casillas_for_registry_scope(
            args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
        )
    if query == "casilla":
        return registry_casilla_for_registry_scope(
            args["modelo"],
            args["casilla"],
            filing_year=filing_year,
            period=period,
            as_of=as_of,
            operation=operation,
        )
    if query == "formulas":
        return registry_formulas_for_registry_scope(
            args["modelo"], filing_year=filing_year, period=period, as_of=as_of, operation=operation
        )
    raise ValueError("unknown authority query")


def authority_query(args: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical public report under a single publication pin."""
    query, as_of = _validated_query(args)
    with bundled_indexed_authority().operation() as operation:
        report = _authority_report(query, args, as_of, operation)
        pin = operation.generation
        return {
            "outcome": "published",
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "report": public_value(report),
        }
