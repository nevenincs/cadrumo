"""Snapshot resolution for the Modelo 303 annual Orden authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from ....core import Modelo
from ....domain.iva import M303RegimenSimplificadoScopeDecision
from ....domain.period import period_end_date
from .errors import RegistryValidationError
from .ids import SourceRefId
from .m303_orden_projection_models import (
    ActividadOrdenAnualRef,
    M303AnnualOrdenProjection,
    M303AnnualOrdenSnapshot,
    M303RegimenSimplificadoSnapshot,
)
from ._schema_references import SourceReference
from ._supplementary_orden import supplementary_orden_authority

if TYPE_CHECKING:
    from .schema import RegistrySnapshot


def resolve_m303_regimen_simplificado_snapshot(
    *,
    registry_snapshot: RegistrySnapshot,
    scope_decision: M303RegimenSimplificadoScopeDecision,
) -> M303RegimenSimplificadoSnapshot:
    """Resolve the sole annual-Orden and record-design snapshot for an explicit scope input."""
    if registry_snapshot.modelo.id != Modelo.M303:
        raise RegistryValidationError("M303 regimen simplificado resolver requires a Modelo 303 registry snapshot")
    record_design = _unique_active_record_design(
        sources=registry_snapshot.sources,
        revision_source_refs=registry_snapshot.revision.source_refs,
        filing_year=registry_snapshot.filing_year,
        period=registry_snapshot.period,
    )
    projection = _select_m303_annual_orden_projection(registry_snapshot)
    return M303RegimenSimplificadoSnapshot(
        filing_year=registry_snapshot.filing_year,
        registry_revision_id=registry_snapshot.revision.id,
        scope_decision=scope_decision,
        orden=m303_annual_orden_snapshot_from_projection(projection),
        record_design=record_design,
    )


def m303_annual_orden_snapshot_from_projection(
    projection: M303AnnualOrdenProjection,
) -> M303AnnualOrdenSnapshot:
    """Materialize one exact annual-Orden projection without selecting a filing revision."""
    return M303AnnualOrdenSnapshot(
        ejercicio=projection.ejercicio,
        registry_revision_id=projection.registry_revision_id,
        source_ref=projection.source_ref,
        source_content_digest=projection.source_content_digest,
        activities=projection.activities,
        activity_refs=tuple(
            ActividadOrdenAnualRef(
                orden_id=activity.orden_id,
                ejercicio=projection.ejercicio,
                registry_revision_id=projection.registry_revision_id,
                source_ref=projection.source_ref,
                source_content_digest=projection.source_content_digest,
            )
            for activity in projection.activities
        ),
        agricultural_authority=projection.agricultural_authority,
        non_agricultural_ingresos_a_cuenta=projection.non_agricultural_ingresos_a_cuenta,
        seasonal_indexes=projection.seasonal_indexes,
        difficult_justification=projection.difficult_justification,
        lorca_2022_reduction=projection.lorca_2022_reduction,
    )


def _select_m303_annual_orden_projection(registry_snapshot: RegistrySnapshot) -> M303AnnualOrdenProjection:
    """Select the internal projection consumed only by the canonical resolver."""
    if registry_snapshot.modelo.id != Modelo.M303:
        raise RegistryValidationError("annual Orden projection selector requires a Modelo 303 registry snapshot")
    return supplementary_orden_authority(
        registry_snapshot.supplementary_ordenes,
        Modelo.M303,
    ).require_projection(
        ejercicio=registry_snapshot.filing_year,
        registry_revision_id=registry_snapshot.revision.id,
    )


def _unique_active_record_design(
    *,
    sources: Mapping[SourceRefId, SourceReference],
    revision_source_refs: Sequence[SourceRefId],
    filing_year: int,
    period: str,
) -> SourceReference:
    filing_date = period_end_date(filing_year, period)
    candidates = tuple(
        source
        for source in sources.values()
        if source.kind == "record_design"
        and source.id in revision_source_refs
        and source.record_design_epoch is not None
        and source.applies_from is not None
        and source.applies_from <= filing_date
        and (source.applies_to is None or source.applies_to >= filing_date)
    )
    if len(candidates) != 1:
        raise RegistryValidationError(
            f"modelo 303 revision must cite exactly one active record-design source, got {len(candidates)}",
        )
    return candidates[0]
