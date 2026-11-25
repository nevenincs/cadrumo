"""The prorrata percentage computed through the real registry snapshot and formula runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..ledger_iva_bindings import resolve_ledger_iva_aggregation_binding_values
from ..schema import RegistrySnapshot

PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")

VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")

VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)


def snapshot_prorrata_percentage(
    snapshot: RegistrySnapshot, con_derecho: Decimal, total: Decimal, *, closes_on: date
) -> Decimal:
    """The casilla percentage the snapshot's formulas compute from the two volumes, at the period close."""
    declared = {binding.id for binding in snapshot.revision.bindings}
    binding_values: dict[str, Decimal] = {
        binding_id: Decimal("100") if binding_id.endswith("state-attribution-ratio") else Decimal("0")
        for binding_id in declared
        & {
            "modelo-303-compensacion-pendiente-anteriores",
            "modelo-303-autoconsumo-promotor-base",
            "modelo-303-profile-state-attribution-ratio",
        }
    }
    binding_values.update(resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()))
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        VOLUMEN_TOTAL_ID: total,
        VOLUMEN_CON_DERECHO_ID: con_derecho,
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": closes_on},
    )
    return result.values[PORCENTAJE_ID]
