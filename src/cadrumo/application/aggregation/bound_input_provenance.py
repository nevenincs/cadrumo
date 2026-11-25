"""Name the resolver that handed the calculation a casilla value directly, apart from any binding."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...domain.modelos.calculation_revision_sources import bound_input_source_ref
from .source_mesh import CalculationSourceProvenance, CalculationSourceResolution


def bound_input_source_nodes(
    resolution: CalculationSourceResolution,
) -> Mapping[CasillaId, CalculationSourceProvenance]:
    """Return one value-free primary node per casilla the resolution supplied directly.

    A casilla fed this way has no binding for the persisted source trace to
    point at, so each gets its own node. A resolution that owns no single
    source kind cannot be named, and a casilla an inner merge already named
    keeps that node.
    """
    source = _single_source_kind(resolution)
    if source is None:
        return dict[CasillaId, CalculationSourceProvenance]()
    named = {row.source_ref for row in resolution.provenance}
    return {
        casilla_id: CalculationSourceProvenance(
            resolver_id=str(resolution.resolver_id),
            resolved_binding_source=source,
            contributor_source_kind=source.value,
            contributor_binding_source=source,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=bound_input_source_ref(casilla_id),
            parent_source_ref=None,
            source_casilla_ids=(casilla_id,),
        )
        for casilla_id in resolution.bound_inputs_by_casilla_id
        if bound_input_source_ref(casilla_id) not in named
    }


def _single_source_kind(resolution: CalculationSourceResolution) -> BindingSourceKind | None:
    kinds = set(resolution.owned_sources) or {row.resolved_binding_source for row in resolution.provenance}
    return next(iter(kinds)) if len(kinds) == 1 else None
