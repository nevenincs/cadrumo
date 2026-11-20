"""Pinned, public reference queries exposed by the MCP surface.

Every query answers with the projection the shared reference-catalogue service
builds for the command line, so the tool and the command line return the same
content for the same question. The tool adds argument validation, the
publication pin that identifies the generation answered from, and the bound on
how much one reply holds: a catalogue is served a page at a time, as summary rows
that name the query to read one row in full, and a formula expression too long
for one reply is served in windows.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, cast

from cadrumo.application import reference_catalogue as catalogue
from cadrumo.application.reference_catalogue import PinnedReferenceRead, ReferenceQueryError
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.modelo import Modelo
from cadrumo.core.tax_domain import TaxDomain
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.portals.categories import PortalCategory
from cadrumo.domain.portals.errors import PortalRegistryError

from .bounded_pages import REPLY_BYTES, CursorRefusedError, encoded_size, page_rows, page_text
from .protocol_contract import public_value

_SCOPED = {"modelo", "filing_year", "period", "as_of"}
_PAGED = {"limit", "cursor"}
_ALLOWED_COORDINATES = {
    "modelos": {"filing_year", "domain"} | _PAGED,
    "support": {"modelo"} | _PAGED,
    "bindings": _SCOPED | _PAGED,
    "describe": _SCOPED,
    "casillas": _SCOPED | {"input_kind", "required", "form_number", "casilla_number"} | _PAGED,
    "casilla": _SCOPED | {"casilla", "cursor"},
    "formulas": _SCOPED | _PAGED,
    "categories": set(),
    "portals": {"category", "modelo"} | _PAGED,
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
    if query == "bindings" and not FOUR_DIGIT_YEAR_FIRST <= args["filing_year"] <= FOUR_DIGIT_YEAR_LAST:
        raise ValueError("invalid filing year")
    as_of = date.fromisoformat(args["as_of"]) if "as_of" in args else None
    return query, as_of


def _identifier[IdentifierT](build: Callable[[str], IdentifierT], value: str) -> IdentifierT:
    """Build a syntax-validated identifier, reporting a malformed one as a bad request."""
    try:
        return build(value)
    except CoreValidationError as error:
        raise ValueError("invalid authority query coordinates") from error


def _pinned_report(query: str, args: dict[str, Any], as_of: date | None) -> PinnedReferenceRead[object]:
    if query == "bindings":
        return catalogue.read_pinned_reference(
            lambda operation: catalogue.list_bindings(
                args["modelo"], year=args["filing_year"], period=args.get("period"), as_of=as_of, operation=operation
            )
        )
    if query == "support":
        return catalogue.read_pinned_reference(lambda operation: catalogue.read_support_matrix(operation=operation))
    if query == "modelos":
        domain = _identifier(TaxDomain, args["domain"]) if "domain" in args else None
        return catalogue.read_pinned_reference(
            lambda operation: catalogue.list_modelos(year=args.get("filing_year"), domain=domain, operation=operation)
        )
    if query in {"describe", "casillas", "casilla", "formulas"}:
        return _scoped_report(query, args, as_of)
    return _reference_report(query, args)


def _scoped_report(query: str, args: dict[str, Any], as_of: date | None) -> PinnedReferenceRead[object]:
    modelo, year, period = args["modelo"], args.get("filing_year"), args.get("period")
    if query == "describe":
        return catalogue.read_pinned_reference(
            lambda operation: catalogue.describe_modelo(
                modelo, year=year, period=period, as_of=as_of, operation=operation
            )
        )
    if query == "casillas":
        input_kind = InputKind(args["input_kind"]) if "input_kind" in args else None
        return catalogue.read_pinned_reference(
            lambda operation: catalogue.list_casillas(
                modelo,
                year=year,
                period=period,
                as_of=as_of,
                input_kind=input_kind,
                required=args.get("required", False),
                form_number=args.get("form_number"),
                casilla_number=args.get("casilla_number"),
                operation=operation,
            )
        )
    if query == "casilla":
        return catalogue.read_pinned_reference(
            lambda operation: catalogue.describe_casilla(
                modelo, args["casilla"], year=year, period=period, as_of=as_of, operation=operation
            )
        )
    return catalogue.read_pinned_reference(
        lambda operation: catalogue.list_formulas(modelo, year=year, period=period, as_of=as_of, operation=operation)
    )


def _reference_report(query: str, args: dict[str, Any]) -> PinnedReferenceRead[object]:
    # These catalogues ship beside the authority; the answer still names the generation it was read under.
    if query == "categories":
        return catalogue.read_pinned_reference(lambda _operation: catalogue.read_ledger_categories())
    if query == "portals":
        category = PortalCategory(args["category"]) if "category" in args else None
        modelo = _identifier(Modelo, args["modelo"]) if "modelo" in args else None
        return catalogue.read_pinned_reference(
            lambda _operation: catalogue.list_portals(category=category, modelo=modelo)
        )
    if query == "portal":
        return catalogue.read_pinned_reference(lambda _operation: catalogue.view_portal(args["portal"]))
    if query == "auth_providers":
        return catalogue.read_pinned_reference(lambda _operation: catalogue.list_auth_providers())
    if query == "apoderado_scopes":
        return catalogue.read_pinned_reference(lambda operation: catalogue.list_apoderado_scopes(operation=operation))
    raise ValueError("unknown authority query")


def _refusal(code: str, message: str) -> dict[str, Any]:
    return {"outcome": "refused", "code": code, "message": message}


# The member of each list report that holds its rows.
_ROWS_MEMBER = {
    "modelos": "modelos",
    "support": "entries",
    "bindings": "rows",
    "casillas": "rows",
    "formulas": "rows",
    "portals": "rows",
}
# What a list serves of each row. A row can be long, so what it leaves out is read with the query its page names.
_CASILLA_SUMMARY = (
    "casilla_id",
    "number",
    "label",
    "input_kind",
    "required",
    "data_type",
    "binding",
    "formula",
    "form_number",
)
_FORMULA_SUMMARY = (
    "formula_id",
    "target_casilla_id",
    "input_casilla_ids",
    "input_bindings",
    "input_parameters",
    "input_relations",
)
_CASILLA_DETAIL = (
    "Rows are summaries: read one in full with query=casilla, casilla=<casilla_id> and the same modelo, "
    "filing_year and period"
)
_FORMULA_DETAIL = (
    "Rows are summaries without the expression: read it with query=casilla, casilla=<target_casilla_id> and "
    "the same modelo, filing_year and period"
)
_SUPPORT_DETAIL = "Rows leave out the renames: pass modelo to page one modelo's renames"
_EXPRESSION_DETAIL = (
    "formula_expression_json is the expression as JSON text, cut in windows: join the windows in order, then parse"
)


def _summary(row: dict[str, Any], members: tuple[str, ...]) -> dict[str, Any]:
    return {member: row[member] for member in members}


def _without_renames(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        **{member: value for member, value in entry.items() if member != "renames"},
        "rename_count": len(entry["renames"]),
    }


def _served_list(query: str, args: dict[str, Any], envelope: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Serve one page of a list report, its rows as summaries where a row can be long."""
    member = _ROWS_MEMBER[query]
    header = {name: value for name, value in report.items() if name != member}
    rows: list[Any] = report[member]
    facts: dict[str, str] = {}
    if query == "casillas":
        rows, facts = [_summary(row, _CASILLA_SUMMARY) for row in rows], {"detail": _CASILLA_DETAIL}
    elif query == "formulas":
        rows, facts = [_summary(row, _FORMULA_SUMMARY) for row in rows], {"detail": _FORMULA_DETAIL}
    elif query == "support" and "modelo" in args:
        wanted = args["modelo"].strip()
        entry = next((entry for entry in rows if entry["modelo_id"] == wanted), None)
        if entry is None:
            raise ReferenceQueryError(f"modelo {wanted} is not in the support matrix")
        # The one modelo's renames are the rows that page; its summary rides every page.
        header["entries"] = [_without_renames(entry)]
        member, rows = "renames", entry["renames"]
    elif query == "support":
        rows, facts = [_without_renames(entry) for entry in rows], {"detail": _SUPPORT_DETAIL}

    def compose(page: list[Any], paging: dict[str, Any]) -> dict[str, Any]:
        return {**envelope, "report": {**header, member: page}, "paging": paging}

    return page_rows("authority", args, rows, compose, **facts)


def _served_casilla(args: dict[str, Any], envelope: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Serve one casilla whole, or its formula expression in windows where the whole is too long for one reply."""
    whole = {**envelope, "report": report}
    expression = report.get("formula_expression")
    if expression is None or encoded_size(whole) <= REPLY_BYTES:
        if args.get("cursor"):
            raise CursorRefusedError("cursor applies only to a formula expression too long for one reply")
        return whole
    header = {name: value for name, value in report.items() if name != "formula_expression"}

    def compose(window: str, paging: dict[str, Any]) -> dict[str, Any]:
        return {**envelope, "report": {**header, "formula_expression_json": window}, "paging": paging}

    return page_text(
        "authority", args, canonical_json_bytes(expression).decode("utf-8"), compose, detail=_EXPRESSION_DETAIL
    )


def authority_query(args: dict[str, Any]) -> dict[str, Any]:
    """Return one canonical public report under a single publication pin."""
    query, as_of = _validated_query(args)
    try:
        answer = _pinned_report(query, args, as_of)
        envelope = {
            "outcome": "published",
            "logical_generation": answer.generation.logical_generation,
            "reader_incarnation": answer.generation.reader_incarnation,
        }
        report = public_value(answer.report)
        if query in _ROWS_MEMBER:
            return _served_list(query, args, envelope, report)
        if query == "casilla":
            return _served_casilla(args, envelope, report)
        return {**envelope, "report": report}
    except catalogue.CededAutonomicModeloError as error:
        return _refusal("ceded_autonomic_modelo", str(error))
    except (ReferenceQueryError, CursorRefusedError) as error:
        return _refusal("invalid_request", str(error))
    except PortalRegistryError as error:
        return _refusal("portal_registry_refused", resolve_error_message(error))
