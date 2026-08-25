"""Work-revision inspection payloads for modelo CLI commands.

``aeat app modelo work revision`` and ``work observations`` both project a
persisted :class:`CalculationRevision` through
:func:`calculation_revision_payload`.
They share the nested
:class:`ObservationPayload`
and
:class:`ResultSummaryRowPayload`
rows with strict :class:`OutputSchema` result schemas.

The application/modelo facade remains authoritative for revision lookup,
selection, and Modelo 202 modality resolution; these classes only document the
JSON transport shape that enters
:class:`SchemaEnvelope` through
:func:`emit_envelope`. The parent :mod:`_modelo_payloads` module re-exports
these split schemas so modelo work emitters keep one payload import surface.
"""

from __future__ import annotations

from ...core.identity import CalculationRevisionId, WorkUnitId
from ...core.json_contract import OutputSchema
from ._modelo_revision_payload_parts import CalculationRevisionProjectionFields, ObservationPayload


class WorkRevisionResult(CalculationRevisionProjectionFields):
    """Single-revision shape returned by ``aeat app modelo work revision``.

    Carries the JSON-safe projection of one
    :class:`CalculationRevision` (the shared
    :class:`CalculationRevisionProjectionFields` base), matching
    :class:`WorkCalculateResult` minus the persistence-confirmation pair
    (``saved`` / ``saved_confirmation``). Modelo 202 modality comes from
    :class:`Modelo202ModalitySummary` and stays on the same optional fields as
    the calculate result so inspection and calculation envelopes remain
    contract-compatible.
    """

    operation: str = "modelo.work.revision"
    modality: str | None = None
    modality_reason: str | None = None


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
