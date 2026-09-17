"""Generic relation-prefill mechanics for registry-selected declarations."""

from __future__ import annotations

from decimal import Decimal

from ...core.aggregation import BindingSourceKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_temporal import binding_applies_to_period
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.formula_initial_values import (
    binding_values_with_absent_by_design_defaults,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.schema import ModeloRevision


# Registry authority: selected M202 relation and absent-by-design defaults are
# consumed through the registry query boundary.
def _registry_relation_prefill_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    operation: PinnedAuthorityOperation,
) -> frozenset[BindingId]:
    """Resolve period-default relation slots for one selected filing scope.

    The scoped query selects the revision for the caller's actual filing year
    and period. Compare every returned coordinate with the already-selected
    snapshot before reading any row; a missing or divergent declaration has no
    fallback relation slot.
    """
    try:
        selected_revision = operation.revision_for_context(
            modelo,
            filing_year=filing_year,
            period=period,
        )
    except (RegistrySnapshotError, RegistryValidationError):
        return frozenset[BindingId]()
    if str(selected_revision.id) != str(revision.id):
        return frozenset[BindingId]()
    return frozenset(
        binding.id
        for binding in selected_revision.bindings
        if binding.source is BindingSourceKind.RELATION_PREFILL
        and isinstance(binding.provider, RelationPrefillProvider)
        and binding.provider.relation_kind == "previous_period"
        and str(binding.provider.source_modelo) == modelo
        and not binding_applies_to_period(binding.applicability, period)
    )


def relation_prefill_period_zero_default_binding_ids(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    operation: PinnedAuthorityOperation,
) -> frozenset[BindingId]:
    """Resolve relation-prefill default binding identities from the registry.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    return _registry_relation_prefill_binding_ids(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        operation=operation,
    )


def modelo_202_first_period_previous_payment_defaults(
    revision: ModeloRevision,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill default values from the selected registry revision.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    default_binding_ids = relation_prefill_period_zero_default_binding_ids(
        revision,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        operation=operation,
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
