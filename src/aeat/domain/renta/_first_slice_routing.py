"""First-slice Modelo 100 expense routing table.

This is the BOE-prescribed routing table from :class:`SpendingCategory`
to the Modelo 100 *estimacion directa* expense casilla that receives
the deductible amount for that category.

The mapping is canonical: it stores the registry ``casilla.id`` values
for the Modelo 100 instructions. Every consumer (the renta-deductibility
observation validator, the renta-ledger aggregator, the snapshot-time
referential-integrity gate) reads from the single
:data:`FIRST_SLICE_EXPENSE_CASILLAS` constant declared here.

The companion :mod:`._first_slice_routing_integrity` module performs
the snapshot-time check that asserts every casilla id mentioned in
this table is present in the modelo-100 registry. A regression in
either the registry or this routing table surfaces as a typed
``RegistryValidationError`` at snapshot construction.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..calculations.registry import CasillaId, validated_casilla_id
from ..categories import SpendingCategory

FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, CasillaId] = {
    SpendingCategory.CUOTAS_AUTONOMOS_SS: validated_casilla_id(
        "0186",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.CUOTAS_AUTONOMOS_SS",
    ),
    SpendingCategory.ARRENDAMIENTO_LOCAL: validated_casilla_id(
        "0192",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ARRENDAMIENTO_LOCAL",
    ),
    SpendingCategory.ASESORIA_CONTABLE: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_CONTABLE",
    ),
    SpendingCategory.ASESORIA_FISCAL: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_FISCAL",
    ),
    SpendingCategory.ASESORIA_JURIDICA: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.ASESORIA_JURIDICA",
    ),
    SpendingCategory.MATERIAL_OFICINA: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.MATERIAL_OFICINA",
    ),
    SpendingCategory.SOFTWARE_SUSCRIPCION: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.SOFTWARE_SUSCRIPCION",
    ),
    SpendingCategory.PUBLICIDAD_MARKETING: validated_casilla_id(
        "0199",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.PUBLICIDAD_MARKETING",
    ),
    SpendingCategory.GASTOS_BANCARIOS: validated_casilla_id(
        "0203",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.GASTOS_BANCARIOS",
    ),
    SpendingCategory.GASTOS_FINANCIEROS: validated_casilla_id(
        "0203",
        surface="FIRST_SLICE_EXPENSE_CASILLAS.GASTOS_FINANCIEROS",
    ),
}
"""SpendingCategory -> Modelo 100 estimacion directa expense casilla."""


def expected_casilla_for_category(category: SpendingCategory) -> CasillaId | None:
    """Return the routed casilla id for ``category``, or ``None`` if outside the first slice."""
    return FIRST_SLICE_EXPENSE_CASILLAS.get(category)


def first_slice_target_casillas() -> frozenset[CasillaId]:
    """Return every casilla id this routing table references.

    Used by the snapshot-time referential-integrity gate to confirm
    that every target the table can route to is a real casilla on
    the modelo-100 registry. A casilla id removed from the registry
    without a corresponding update here is a snapshot-build error.
    """
    return frozenset(FIRST_SLICE_EXPENSE_CASILLAS.values())


__all__ = [
    "FIRST_SLICE_EXPENSE_CASILLAS",
    "expected_casilla_for_category",
    "first_slice_target_casillas",
]
