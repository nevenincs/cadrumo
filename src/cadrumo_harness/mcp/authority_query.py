"""Pinned, public reference queries exposed by the MCP surface.

Every query answers with the projection the shared reference-catalogue service
builds for the command line, so the tool and the command line return the same
content for the same question. The tool adds only argument validation and the
publication pin that identifies the generation answered from.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, cast

from cadrumo.application import reference_catalogue as catalogue
from cadrumo.application.modelo.registry_discovery import registry_bindings_for_year
from cadrumo.application.reference_catalogue import ReferenceQueryError
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.modelo import Modelo
from cadrumo.core.tax_domain import TaxDomain
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.portals.categories import PortalCategory
from cadrumo.domain.portals.errors import PortalRegistryError

from .protocol_contract import public_value

_SCOPED = {"modelo", "filing_year", "period", "as_of"}
_ALLOWED_COORDINATES = {
    "modelos": {"filing_year", "domain"},
    "support": set(),
    "bindings": {"modelo", "filing_year", "as_of"},
    "describe": _SCOPED,
    "casillas": _SCOPED | {"input_kind", "required", "form_number", "casilla_number"},
    "casilla": _SCOPED | {"casilla"},
    "formulas": _SCOPED,
    "categories": set(),
    "portals": {"category", "modelo"},
    "portal": {"portal"},
    "auth_providers": set(),
    "apoderado_scopes": set(),
}
_REQUIRED_COORDINATES = {
    "bindings": {"modelo", "filing_year"},
    "describe": {"modelo"},
    "casillas": {"modelo"},
    "casilla": {"modelo", "casilla"},
    "formulas": {"modelo"},
    "portal": {"portal"},
}


def _validated_query(args: dict[str, Any]) -> tuple[str, date | None]:
    query = cast(str, args["query"])
    if query not in _ALLOWED_COORDINATES:
        raise ValueError("unknown authority query")
    supplied = set(args) - {"query"}
    if supplied - _ALLOWED_COORDINATES[query] or _REQUIRED_COORDINATES.get(query, set()) - supplied:
        raise ValueError("invalid authority query coordinates")
    if query == "bindings" and not 1900 <= args["filing_year"] <= 9999:
        raise ValueError("invalid filing year")
    as_of = date.fromisoformat(args["as_of"]) if "as_of" in args else None
    return query, as_of


def _identifier[IdentifierT](build: Callable[[str], IdentifierT], value: str) -> IdentifierT:
    """Build a syntax-validated identifier, reporting a malformed one as a bad request."""
    try:
        return build(value)
    except CoreValidationError as error:
        raise ValueError("invalid authority query coordinates") from error


def _authority_report(
    query: str, args: dict[str, Any], as_of: date | None, operation: PinnedAuthorityOperation
) -> object:
    if query == "bindings":
        return registry_bindings_for_year(
            args["modelo"], filing_year=args["filing_year"], as_of=as_of, operation=operation
        )
    if query == "support":
        return catalogue.read_support_matrix(operation=operation)
    if query == "modelos":
        domain = _identifier(TaxDomain, args["domain"]) if "domain" in args else None
        return catalogue.list_modelos(year=args.get("filing_year"), domain=domain, operation=operation)
    if query in {"describe", "casillas", "casilla", "formulas"}:
        return _scoped_authority_report(query, args, as_of, operation)
    return _reference_report(query, args, operation)


def _scoped_authority_report(
    query: str, args: dict[str, Any], as_of: date | None, operation: PinnedAuthorityOperation
) -> object:
    modelo, year, period = args["modelo"], args.get("filing_year"), args.get("period")
    if query == "describe":
        return catalogue.describe_modelo(modelo, year=year, period=period, as_of=as_of, operation=operation)
    if query == "casillas":
        return catalogue.list_casillas(
            modelo,
            year=year,
            period=period,
            as_of=as_of,
            input_kind=InputKind(args["input_kind"]) if "input_kind" in args else None,
            required=args.get("required", False),
            form_number=args.get("form_number"),
            casilla_number=args.get("casilla_number"),
            operation=operation,
        )
    if query == "casilla":
        return catalogue.describe_casilla(
            modelo, args["casilla"], year=year, period=period, as_of=as_of, operation=operation
        )
    return catalogue.list_formulas(modelo, year=year, period=period, as_of=as_of, operation=operation)


def _reference_report(query: str, args: dict[str, Any], operation: PinnedAuthorityOperation) -> object:
    if query == "categories":
        return catalogue.read_ledger_categories()
    if query == "portals":
        return catalogue.list_portals(
            category=PortalCategory(args["category"]) if "category" in args else None,
            modelo=_identifier(Modelo, args["modelo"]) if "modelo" in args else None,
        )
    if query == "portal":
        return catalogue.view_portal(args["portal"])
    if query == "auth_providers":
        return catalogue.list_auth_providers()
    if query == "apoderado_scopes":
        return catalogue.list_apoderado_scopes(operation=operation)
    raise ValueError("unknown authority query")


def _refusal(code: str, message: str) -> dict[str, Any]:
    return {"outcome": "refused", "code": code, "message": message}


def authority_query(args: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical public report under a single publication pin."""
    query, as_of = _validated_query(args)
    with bundled_indexed_authority().operation() as operation:
        try:
            report = _authority_report(query, args, as_of, operation)
        except catalogue.CededAutonomicModeloError as error:
            return _refusal("ceded_autonomic_modelo", str(error))
        except ReferenceQueryError as error:
            return _refusal("invalid_request", str(error))
        except PortalRegistryError as error:
            return _refusal("portal_registry_refused", resolve_error_message(error))
        pin = operation.generation
        return {
            "outcome": "published",
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "report": public_value(report),
        }
