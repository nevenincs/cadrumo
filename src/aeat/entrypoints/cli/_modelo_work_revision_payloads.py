"""Registered :class:`OutputSchema` payloads for work-revision inspection.

``aeat app modelo work revision`` and ``work observations`` share the nested
revision rows from :mod:`aeat.entrypoints.cli._modelo_revision_payload_parts`
and register strict JSON-envelope result schemas through
:func:`register_schema`.
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

    Carries the same calculation-revision fields as
    :class:`WorkCalculateResult` minus the persistence-confirmation
    pair (``saved`` / ``saved_confirmation``). Modelo 202 modality
    surfaces on the same optional fields so the inspection verb stays
    contract-compatible with the calculate verb's output.
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
    """Typed provenance view for one stored :class:`CalculationRevision`.

    ``observations`` reuses the same :class:`ObservationPayload` rows emitted by
    :class:`WorkRevisionResult` and :class:`aeat.entrypoints.cli._modelo_payloads.WorkCalculateResult`;
    the separate command exists so operators can inspect formula, legal, source,
    and operand provenance without reading the full revision payload.
    """

    operation: str = "modelo.work.observations"
    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    observation_count: int
    observations: tuple[ObservationPayload, ...]


__all__ = ["WorkObservationsResult", "WorkRevisionResult"]
