"""First-slice Modelo 100 expense routing table.

This is the BOE-prescribed routing table from :class:`SpendingCategory`
to the Modelo 100 *estimacion directa* expense casilla that receives
the deductible amount for that category.

The mapping is canonical: AEAT publishes the casilla numbers in the
Modelo 100 instructions. Every consumer (the renta-deductibility
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

from ..categories import SpendingCategory

FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, str] = {
    SpendingCategory.CUOTAS_AUTONOMOS_SS: "0186",
    SpendingCategory.ARRENDAMIENTO_LOCAL: "0192",
    SpendingCategory.ASESORIA_CONTABLE: "0199",
    SpendingCategory.ASESORIA_FISCAL: "0199",
    SpendingCategory.ASESORIA_JURIDICA: "0199",
    SpendingCategory.GASTOS_BANCARIOS: "0203",
    SpendingCategory.GASTOS_FINANCIEROS: "0203",
}
"""SpendingCategory -> Modelo 100 estimacion directa expense casilla."""


def expected_casilla_for_category(category: SpendingCategory) -> str | None:
    """Return the routed casilla id for ``category``, or ``None`` if outside the first slice."""

    return FIRST_SLICE_EXPENSE_CASILLAS.get(category)


def first_slice_target_casillas() -> frozenset[str]:
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
