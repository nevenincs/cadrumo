"""IVA-compensation registry query boundary.

The versioned M303/M390 registry owns compensation source and target semantic
IDs, annual partitions, period selection, and formula declarations. This
module retains the generic validation helper and exposes the authority-backed
query seam for consumers that resolve those declarations.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.query_reports import ModeloBindingsReport, ModeloFormulasReport


def iva_compensation_casilla_id(value: object) -> CasillaId:
    """Validate a registry-provided IVA-compensation casilla token."""
    try:
        return validated_casilla_id(value, surface="IVA compensation registry token")
    except ValueError as exc:
        raise RuntimeError(f"IVA compensation registry token {value!r} is not a CasillaId") from exc


def iva_compensation_registry_declarations(
    query_service: RegistryQueryService,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[ModeloBindingsReport, ModeloFormulasReport]:
    """Resolve compensation declarations from one selected registry scope.

    The query service selects the revision and returns the authored binding and
    formula reports. Model identifiers, casillas, source kinds, and expressions
    remain data in the selected registry revision rather than being repeated in
    this calculation module. A missing or invalid declaration is reported by
    the authority-backed query service; this seam does not invent a fallback.
    """
    return (
        query_service.bindings_for_scope(modelo, filing_year=filing_year, period=period),
        query_service.formulas_for_scope(modelo, filing_year=filing_year, period=period),
    )


__all__ = ["iva_compensation_casilla_id", "iva_compensation_registry_declarations"]
