"""Generic relation-prefill mechanics for registry-selected declarations."""

from __future__ import annotations

from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.formula_initial_values import (
    binding_values_with_absent_by_design_defaults,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import ModeloRevision


# fact-relocation: selected M202 relation and absent-by-design default declarations are consumed through RegistryQueryService
def _registry_relation_prefill_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> frozenset[BindingId]:
    """Resolve period-default relation slots through the generic registry query."""
    del revision
    report = RegistryQueryService(bundled_authority()).bindings(modelo, period=period)
    return frozenset(
        row.binding_id
        for row in report.rows
        if row.provider.kind is BindingSourceKind.RELATION_PREFILL and not row.operator_input_required
    )


def relation_prefill_period_zero_default_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> frozenset[BindingId]:
    """Resolve relation-prefill default binding identities from the registry."""
    return _registry_relation_prefill_binding_ids(revision, modelo=modelo, period=period)


def modelo_202_first_period_previous_payment_defaults(
    revision: ModeloRevision,
    *,
    modelo: str,
    period: str,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill default values from the selected registry revision."""
    default_binding_ids = relation_prefill_period_zero_default_binding_ids(
        revision,
        modelo=modelo,
        period=period,
    )
    if not default_binding_ids:
        return {}
    default_values = binding_values_with_absent_by_design_defaults(
        revision,
        {},
        target_period=period,
    )
    return {
        binding_id: default_values[binding_id] for binding_id in default_binding_ids if binding_id in default_values
    }
