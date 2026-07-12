"""Registered work-revision inspection payloads for modelo CLI commands.

``aeat app modelo work revision`` and ``work observations`` both project a
persisted :class:`CalculationRevision` through
:func:`calculation_revision_payload`.
They share the nested
:class:`ObservationPayload`
and
:class:`ResultSummaryRowPayload`
rows, then register strict
:class:`OutputSchema` result schemas through
:func:`register_schema`.

The application/modelo facade remains authoritative for revision lookup,
selection, and Modelo 202 modality resolution; these classes only document the
JSON transport shape that enters
:class:`SchemaEnvelope` through
:func:`_emit_envelope`. The parent :mod:`_modelo_payloads` module re-exports
these split schemas so modelo work emitters keep one payload import surface.
"""

from __future__ import annotations

from pydantic import Field

from ...domain.calculations.registry import BindingId, CasillaId, RelationId
from ...domain.modelos import (
    CalculationRevisionId,
    WorkUnitId,
)
from ._modelo_revision_payload_parts import DetailRowPayload, ObservationPayload, ResultSummaryRowPayload
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.work.revision")
class WorkRevisionResult(OutputSchema):
    """Single-revision shape returned by ``aeat app modelo work revision``.

    Carries the JSON-safe projection of one
    :class:`CalculationRevision`, matching
    :class:`WorkCalculateResult` minus the persistence-confirmation pair
    (``saved`` / ``saved_confirmation``). Modelo 202 modality comes from
    :class:`Modelo202ModalitySummary` and stays on the same optional fields as
    the calculate result so inspection and calculation envelopes remain
    contract-compatible.
    """

    operation: str = "modelo.work.revision"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    detail_rows: tuple[DetailRowPayload, ...] = ()
    binding_overrides: dict[BindingId, str]
    relation_overrides: dict[RelationId, str] = Field(default_factory=dict)
    input_values_by_casilla_id: dict[CasillaId, str]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None
    modality: str | None = None
    modality_reason: str | None = None


@register_schema("modelo.work.observations")
class WorkObservationsResult(OutputSchema):
    """Typed provenance view for one stored :class:`CalculationRevision`.

    ``observations`` reuses the same :class:`ObservationPayload` rows emitted by
    :class:`WorkRevisionResult` and
    :class:`WorkCalculateResult`; the separate command exists so operators can
    inspect :obj:`FormulaId`,
    :obj:`LegalRefId`,
    :obj:`SourceRefId`, and operand
    provenance without reading the full revision payload.
    """

    operation: str = "modelo.work.observations"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    observation_count: int
    observations: tuple[ObservationPayload, ...]


__all__ = ["WorkObservationsResult", "WorkRevisionResult"]
