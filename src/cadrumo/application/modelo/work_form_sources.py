"""Name where one editor field's value comes from, from the bindings that feed it.

A bound value is described by its primary binding, the one an override
replaces: its source kind's family says what kind of place the value comes
from, and a carry from an earlier declaration names that declaration when the
binding's own temporal selector identifies it. A value the calculation took
from an imported AEAT draft is described as AEAT data, because that snapshot,
not the binding's usual source, supplied it.

Nothing here is inferred from a label or a box number: the family comes from
the total source-kind table, and an earlier declaration from the registry's
temporal anchors through the one derivation the carry resolvers use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from ...core.aggregation import BindingSourceKind
from ...core.period import Period
from ...domain.calculations.registry.binding_temporal import temporal_period_anchors
from ...domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.m303_regimen_simplificado_annual_summary_bindings import (
    M303RegimenSimplificadoAnnualSummaryProvider,
)
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.schema import BindingDefinition
from .source_policy import SourceFamily, source_policy
from .work_form_models import ModeloFormEarlierFiling, ModeloFormValueSource


def earlier_filings(binding: BindingDefinition, *, target: Period) -> tuple[ModeloFormEarlierFiling, ...]:
    """Return the earlier declarations ``binding`` reads for the ``target`` declaration.

    Only a provider that names its source modelo and a temporal window
    identifies them. A window that names no source period for this target is a
    scope-out, so it identifies none; every other provider identifies none
    either, rather than having one guessed for it.
    """
    provider = binding.provider
    if not isinstance(
        provider, PreviousFilingProvider | RelationPrefillProvider | M303RegimenSimplificadoAnnualSummaryProvider
    ):
        return ()
    try:
        anchors = temporal_period_anchors(provider.temporal, target_period=target.registry_token)
    except RegistryValidationError:
        return ()
    return tuple(
        ModeloFormEarlierFiling(
            modelo=str(provider.source_modelo),
            period=Period.from_year_and_code(target.filing_year + year_delta, source_period),
        )
        for year_delta, source_period in anchors
    )


def bound_value_source(
    binding_ids: Sequence[BindingId],
    *,
    bindings: Mapping[str, BindingDefinition],
    aeat_data_binding_ids: frozenset[str],
    target: Period,
) -> ModeloFormValueSource | None:
    """Describe where a value fed by ``binding_ids`` comes from; the first binding is the primary one.

    ``aeat_data_binding_ids`` are the bindings the current calculation took
    from an imported AEAT draft; a field any of them feeds reads as AEAT data.
    A field no binding feeds has no source to describe.
    """
    if not binding_ids:
        return None
    from_aeat_data = next((binding_id for binding_id in binding_ids if str(binding_id) in aeat_data_binding_ids), None)
    if from_aeat_data is not None:
        return ModeloFormValueSource(
            family=SourceFamily.AEAT_DRAFT, binding_id=from_aeat_data, source_kind=BindingSourceKind.BORRADOR
        )
    primary = bindings[str(binding_ids[0])]
    return ModeloFormValueSource(
        family=source_policy(primary.source).family,
        binding_id=primary.id,
        source_kind=primary.source,
        earlier_filings=earlier_filings(primary, target=target),
    )


FIXED_BY_THE_FORM: Final[ModeloFormValueSource] = ModeloFormValueSource(family=SourceFamily.FIXED_BY_DESIGN)
"""The source of a value the declared layout fixes as a design constant, with no binding behind it."""


__all__ = ["FIXED_BY_THE_FORM", "bound_value_source", "earlier_filings"]
