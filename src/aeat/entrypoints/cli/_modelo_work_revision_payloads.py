"""Registered work-revision inspection payloads for modelo CLI commands.

``aeat app modelo work revision`` and ``work observations`` both project a
persisted :class:`~aeat.domain.modelos.CalculationRevision` through
:func:`~aeat.entrypoints.cli._modelo_rendering.calculation_revision_payload`.
They share the nested
:class:`~aeat.entrypoints.cli._modelo_revision_payload_parts.ObservationPayload`
and
:class:`~aeat.entrypoints.cli._modelo_revision_payload_parts.ResultSummaryRowPayload`
rows, then register strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` result schemas through
:func:`~aeat.entrypoints.cli._schemas.register_schema`.

The application/modelo facade remains authoritative for revision lookup,
selection, and Modelo 202 modality resolution; these classes only document the
JSON transport shape that enters
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope` through
:func:`~aeat.entrypoints.cli._common._emit_envelope`. The parent
:mod:`aeat.entrypoints.cli._modelo_payloads` module re-exports these split
schemas so modelo work emitters keep one payload import surface.
"""

from __future__ import annotations

from pydantic import Field

from ...domain.calculations.registry import BindingId, CasillaId, RelationId
from ...domain.modelos._ids import CalculationRevisionId, WorkUnitId
from ._modelo_revision_payload_parts import ObservationPayload, ResultSummaryRowPayload
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.work.revision")
class WorkRevisionResult(OutputSchema):
    """Single-revision shape returned by ``aeat app modelo work revision``.

    Carries the JSON-safe projection of one
    :class:`~aeat.domain.modelos.CalculationRevision`, matching
    :class:`~aeat.entrypoints.cli._modelo_payloads.WorkCalculateResult` minus
    the persistence-confirmation pair (``saved`` / ``saved_confirmation``).
    Modelo 202 modality comes from
    :class:`~aeat.application.modelo.Modelo202ModalitySummary` and stays on the
    same optional fields as the calculate result so inspection and calculation
    envelopes remain contract-compatible.
    """

    operation: str = "modelo.work.revision"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
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
    """Typed provenance view for one stored :class:`~aeat.domain.modelos.CalculationRevision`.

    ``observations`` reuses the same :class:`ObservationPayload` rows emitted by
    :class:`WorkRevisionResult` and
    :class:`~aeat.entrypoints.cli._modelo_payloads.WorkCalculateResult`; the
    separate command exists so operators can inspect
    :class:`~aeat.domain.calculations.registry.FormulaId`,
    :class:`~aeat.domain.calculations.registry.LegalRefId`,
    :class:`~aeat.domain.calculations.registry.SourceRefId`, and operand
    provenance without reading the full revision payload.
    """

    operation: str = "modelo.work.observations"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    observation_count: int
    observations: tuple[ObservationPayload, ...]


__all__ = ["WorkObservationsResult", "WorkRevisionResult"]
