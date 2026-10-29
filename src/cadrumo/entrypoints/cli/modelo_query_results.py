"""Typed ``--json`` payload schemas for modelo command envelopes.

Each command result is a strict
:class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets for a stable command path
and wrapped at emit time in
:class:`SchemaEnvelope` through
:func:`emit_envelope`. This file is the CLI-side
projection boundary for :mod:`modelo`: application and domain
results stay authoritative while these classes expose JSON-safe
:class:`WorkUnit`,
:class:`CalculationRevision`,
:class:`ModeloRecord`,
:class:`VerificationReport`,
:obj:`CasillaId`,
:obj:`LegalRefId`, and
:obj:`SourceRefId` fields to operators.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field, NonNegativeInt, field_validator

from ...application.aggregation.service import (
    PerModeloAggregationContributor,
)
from ...application.aggregation.withholding_observation_service import (
    WithholdingGenerationId,
    WithholdingMutationMode,
    WithholdingScopeToken,
)
from ...application.calculations.observations_repository import (
    PriorDomiciliationElectionProjection,
)
from ...application.modelo.export_projection import ModeloIvaWalletDecisionPublicProvenance
from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.identity.profile import ProfileId
from ...core.identity.transaction_ids import TransactionId
from ...core.json_contract import OutputSchema
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prose_elision import IssueDetail
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...core.text_bounds import NonEmptyStr
from ...core.type_guards import is_object_list
from ...domain.buckets.event import (
    BucketActorLabel,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
    BucketObjectId,
)
from ...domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    LegalRefId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.schema_base import LegalRefs, SourceRefs
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ...domain.modelos.codes import ModeloCode
from ._decimal_wire import DecimalWireText
from .modelo_aux_payloads import (
    WithholdingClaveBreakdownPayload,
)

if TYPE_CHECKING:
    from ...application.modelo.export_contracts import ModeloExportResult as _AppModeloExportResult


class DataInventoryCasillaPayload(OutputSchema):
    """One casilla entry on the ``modelo requires`` data-inventory checklist.

    Projects :class:`~application.modelo.data_inventory.DataInventoryCasilla`. ``binding_id``
    and ``binding_source`` are populated only for ``ledger_derivable`` and
    ``profile_derivable`` rows; required and optional manual entries carry no
    binding (they are hand-entered).

    The grounding invariant — ``legal_refs`` and ``source_refs`` non-empty —
    belongs to the canonical
    :class:`~application.modelo.data_inventory.DataInventoryCasilla`, which refuses to build an
    ungrounded entry, so every consumer of the checklist inherits it rather than
    only the JSON surface. This schema is the wire shape of an entry that
    already satisfies it.
    """

    casilla_id: CasillaId
    number: str
    label: str
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    binding_id: BindingId | None = None
    binding_source: str | None = None


class ModeloRequiresResult(OutputSchema):
    """Data-inventory checklist result returned by ``aeat app modelo requires``.

    Composes the registry snapshot for one ``(modelo, filing_year, period)``
    into the operator-facing "what data do I need" checklist: casillas the
    operator must hand-enter (``required_manual``), casillas they may
    optionally enter (``optional_manual``), casillas they supply on each detail
    row of a repeated export record (``detail_row_fields``), casillas the ledger aggregation
    mesh populates once the relevant transactions are imported and classified
    (``ledger_derivable``), and casillas populated from the active taxpayer
    profile (``profile_derivable``). The two cross-filing channels remain
    distinct as ``previous_filing`` and ``relation_prefill``;
    ``live_observation`` carries bucket-local observation, register, and
    invoice-backed sources, while ``unbucketed_sources`` preserves any binding
    pair outside the explicit classifier for the envelope advisory.

    ``unresolved_profile_bindings`` names the
    profile-derivable bindings the active profile has not yet supplied a fact
    for (e.g. an unset home-office usage ratio) so the operator can fix the
    gap before calculating, and ``unresolved_profile_keys`` names the profile
    facts those bindings consume, which is what the operator actually has to
    supply. ``profile_checked`` is ``False`` when no active profile was
    available to check.
    """

    operation: str = "modelo.requires"
    authority_generation: ContentDigest
    modelo: str
    revision: str
    filing_year: int
    period: str
    required_manual: list[DataInventoryCasillaPayload]
    optional_manual: list[DataInventoryCasillaPayload]
    detail_row_fields: list[DataInventoryCasillaPayload]
    ledger_derivable: list[DataInventoryCasillaPayload]
    profile_derivable: list[DataInventoryCasillaPayload]
    previous_filing: list[DataInventoryCasillaPayload]
    relation_prefill: list[DataInventoryCasillaPayload]
    live_observation: list[DataInventoryCasillaPayload]
    unbucketed_sources: list[DataInventoryCasillaPayload]
    unresolved_profile_bindings: list[BindingId]
    unresolved_profile_keys: list[str]
    profile_checked: bool


# ---------------------------------------------------------------------------
# Singleton verb schemas
# ---------------------------------------------------------------------------


class ModeloExportPayload(OutputSchema):
    """Modelo export result (path reference only — no raw bytes in envelope).

    Distinct from the application :class:`ModeloExportResult`:
    the backend result carries the write metadata plus an absolute ``Path`` and
    extra audit fields; this envelope projects the path-reference receipt
    (fichero-BOE bytes are never carried) using ``output_path`` (stringified),
    ``byte_size``, and ``file_sha256``. Derive instances via :meth:`from_result`.
    """

    operation: str = "modelo.export"
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_id: BucketId
    modelo: str
    filing_year: int
    period: Period
    output_path: str
    byte_size: int
    file_sha256: str
    format: str
    bucket_event_id: str
    resolved_result_disposition: ResultDisposition | None
    payment_election: PaymentElection | None = None
    refund_election: RefundElection | None = None
    prior_domiciliation_election: PriorDomiciliationElectionProjection
    software_identity_grade: AeatSoftwareIdentityGrade | None = None
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionPublicProvenance | None = None

    @classmethod
    def from_result(cls, result: _AppModeloExportResult) -> ModeloExportPayload:
        """Project the application :class:`ModeloExportResult` into this CLI :class:`ModeloExportPayload` envelope.

        ``output_path`` is stringified from the application ``Path``; the
        fichero-BOE bytes are intentionally excluded (the file is written to
        ``output_path``). ``operation`` is the CLI-only discriminator left at its
        default; the backend's ``exported_at``/``actor`` audit fields are not
        surfaced in the JSON envelope.
        """
        return cls(
            work_unit_id=result.work_unit_id,
            calculation_revision_id=result.calculation_revision_id,
            bucket_id=result.bucket_id,
            modelo=result.modelo,
            filing_year=result.filing_year,
            period=result.period,
            output_path=str(result.output_path),
            byte_size=result.byte_size,
            file_sha256=result.file_sha256,
            format=result.format,
            bucket_event_id=result.bucket_event_id,
            resolved_result_disposition=result.resolved_result_disposition,
            payment_election=result.payment_election,
            refund_election=result.refund_election,
            prior_domiciliation_election=result.prior_domiciliation_election,
            software_identity_grade=result.software_identity_grade,
            iva_wallet_decision_provenance=(
                ModeloIvaWalletDecisionPublicProvenance.from_provenance(result.iva_wallet_decision_provenance)
                if result.iva_wallet_decision_provenance is not None
                else None
            ),
        )


class DeltaRowPayload(OutputSchema):
    """One grounded :class:`CasillaId` comparison row in ``modelo.compare``.

    Preserves formula, legal-reference, and source-reference identifiers so the
    :class:`ModeloCompareResult` envelope does not lose registry provenance.
    """

    casilla_id: CasillaId
    label: str
    section: str
    year_a_value: str
    year_b_value: str
    delta: str
    pct_change: str | None
    formula_id: FormulaId | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class CompareSectionPayload(OutputSchema):
    """Named section grouping for :class:`DeltaRowPayload` rows."""

    section: str
    rows: list[DeltaRowPayload]


class ModeloCompareResult(OutputSchema):
    """Envelope result for ``modelo.compare``.

    Rows are carried both sectioned and flattened so table rendering and JSON
    consumers share the same :class:`DeltaRowPayload` provenance fields.
    """

    operation: str = "modelo.compare"
    modelo: str
    year_a: int
    year_b: int
    year_a_revision_id: RevisionId
    year_b_revision_id: RevisionId
    year_a_is_draft: bool
    year_b_is_draft: bool
    sections: list[CompareSectionPayload]
    delta_rows: list[DeltaRowPayload]


class ModeloLifecycleEventPayload(OutputSchema):
    """One bucket event in the modelo history output.

    Projects :class:`~cadrumo.domain.buckets.event.BucketEvent` through the identity
    aliases and closed enums that package already exports, rather than
    re-declaring their shape as free strings. Enum members and ``datetime``
    values render to the same JSON the former hand-built mapping emitted, so the
    wire form is unchanged.
    """

    event_id: BucketEventId
    event_type: BucketEventType
    occurred_at: datetime
    actor: BucketActorLabel
    object_type: BucketEventObjectType
    object_id: BucketObjectId
    payload: dict[str, str]


class ModeloHistoryResult(OutputSchema):
    """Chronological modelo lifecycle history result.

    ``period`` stays a free token: the filter accepts registry period codes and
    the censo lifecycle words (``alta`` / ``modificacion`` / ``baja``), and an
    unmatched token legitimately yields an empty history rather than a refusal.
    Only its blankness is constrained.
    """

    operation: str = "modelo.history"
    modelo: NonEmptyStr
    year: FilingYear | None = None
    period: NonEmptyStr | None = None
    count: NonNegativeInt
    events: list[ModeloLifecycleEventPayload]


class CasillaObservationPayload(OutputSchema):
    """One typed :class:`CasillaId` observation for projection-style results.

    Used by :class:`ModeloProjectResult` and
    :class:`WorkPreviewMaritimeExemptionResult`; ``legal_refs`` and
    ``source_refs`` stay required to preserve calculation grounding in CLI JSON.
    """

    casilla_id: CasillaId
    value: str
    formula_id: FormulaId | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs


class M130AccumulatedPayload(OutputSchema):
    """M130 summary inputs that feed :class:`ModeloProjectResult`.

    These stringified Decimal fields are operator-facing totals; the grounded
    per-casilla path is :class:`CasillaObservationPayload`.
    """

    ingresos: DecimalWireText
    gastos: DecimalWireText
    rendimiento_neto: DecimalWireText
    pagos_fraccionados: DecimalWireText


class M100ProjectionPayload(OutputSchema):
    """Projected M100 summary values in :class:`ModeloProjectResult`.

    This flat view gives stable top-line JSON keys; formula provenance lives in
    ``ModeloProjectResult.casilla_observations``.
    """

    base_liquidable_general_0505: str
    pagos_fraccionados_0604: str
    cuota_integra_estatal_0545: str
    cuota_integra_autonomica_0546: str
    cuota_liquida_estatal_0595: str
    cuota_liquida_autonomica_0596: str
    cuota_resultante_0597: str


class ModeloProjectResult(OutputSchema):
    """Envelope result for ``modelo.project``.

    Combines :class:`M130AccumulatedPayload` source totals, the flat
    :class:`M100ProjectionPayload` summary, and the required
    :class:`CasillaObservationPayload` provenance list.
    """

    operation: str = "modelo.project"
    year: int
    ccaa: str
    quarters_filed: int
    quarters_available: list[str]
    is_extrapolated: bool
    m130_accumulated: M130AccumulatedPayload
    casilla_observations: list[CasillaObservationPayload]
    m100_projection: M100ProjectionPayload


class ModeloReadinessMissingRequirementPayload(OutputSchema):
    """One missing profile requirement in the readiness result."""

    section_key: str
    field_key: str
    selector: str
    label: str
    legal_refs: list[str]
    modelos: list[str]


class ModeloReadinessMissingBindingPayload(OutputSchema):
    """One calculation binding readiness cannot satisfy."""

    binding_id: str
    source: BindingSourceKind
    input_channel: str


class LedgerIssuePayload(OutputSchema):
    """One ledger issue in the readiness result."""

    transaction_id: TransactionId
    reason: str
    detail: IssueDetail


class ModeloReadinessResult(OutputSchema):
    """Active-profile modelo readiness report."""

    operation: str = "modelo.readiness"
    authority_generation: ContentDigest
    profile_id: ProfileId
    modelo: str
    revision_id: RevisionId
    filing_year: int
    period: Period
    ready: bool
    profile_ready: bool
    profile_refusal: str
    registry_ready: bool
    registry_refusal: str
    binding_ready: bool
    missing: list[ModeloReadinessMissingRequirementPayload]
    missing_bindings: list[ModeloReadinessMissingBindingPayload]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: Period | None
    ledger_checked_transaction_count: int
    ledger_issues: list[LedgerIssuePayload]


class WorkResumeResult(OutputSchema):
    """Workflow resume precondition and context result.

    Combines the resumable
    :class:`WorkflowResumeContext` with selector
    metadata from
    :class:`WorkflowResumeTargetResolution`. The
    ``obligation`` payload is the serialized
    :class:`ModeloDeadline` the workflow engine would use
    for a fresh attempt.
    """

    operation: str = "modelo.work.resume"
    prior_workflow_run_id: str
    resolved_source: str | None = None
    work_unit_id: WorkUnitId | None = None
    short_work_unit_id: str | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    short_calculation_revision_id: str | None = None
    modelo: str
    period: Period
    aborted_reason: str
    obligation: dict[str, object]


class WithholdingWindowBaselinePayload(OutputSchema):
    """An exact public optimistic-concurrency baseline for one withholding scope."""

    scope_token: WithholdingScopeToken
    generation_id: WithholdingGenerationId


class WithholdingGenerationAuditPayload(OutputSchema):
    """Payload-free immutable lineage facts for the current withholding generation."""

    parent_generation_id: WithholdingGenerationId
    mode: WithholdingMutationMode
    supersedes_generation_id: WithholdingGenerationId | None = None

    @field_validator("mode", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_mode(cls, value: object) -> object:
        """Hydrate the closed mutation-mode token from JSON rendering."""
        if isinstance(value, str) and not isinstance(value, WithholdingMutationMode):
            return WithholdingMutationMode(value)
        return value


class WithholdingWindowReadbackPayload(OutputSchema):
    """Current withholding-window baseline and auditable generation lineage.

    This is deliberately metadata-only.  The active entries remain encrypted
    persistence data and are never copied into an aggregate command result or
    its human-readable logging projection.
    """

    baseline: WithholdingWindowBaselinePayload
    generation: NonNegativeInt
    generation_audit: WithholdingGenerationAuditPayload | None = None


class ModeloAggregateResult(OutputSchema):
    """Per-modelo aggregation result, projected from the canonical service result.

    Every field is typed from the contract
    :class:`~application.aggregation.service.PerModeloAggregationResult` already
    enforces: a bounded non-blank modelo, the closed
    :class:`~application.aggregation.service.PerModeloAggregationContributor` provider,
    closed :class:`~core.aggregation.BindingSourceKind` source kinds, and non-negative
    counters. Redeclaring them as bare strings and unbounded integers made this
    transport shell strictly more permissive than the result it renders, so an
    empty modelo, an unknown provider, a bogus source kind, or a negative count
    could be emitted as a valid envelope. Project the actual operation result
    through these bounded field types.

    ``clave_breakdown`` carries per-clave rows of the stored per-perceptor-clave
    withholding detail the modelo's calculation reads (empty when it reads
    none); it is primary structured result data the command produces, not an
    incidental diagnostic.

    ``clave_breakdown`` and ``observation_count`` are deliberately NOT
    cross-validated against each other. They are different stores, not one
    derived from the other: ``observation_count`` counts the retención rows the
    retenciones provider aggregated (``result.log_fields``), while
    ``clave_breakdown`` projects the per-perceptor-clave rows through
    ``aggregate_withholding_by_clave``. Modelo 190's calculation reads only the
    second store, so its ``observation_count`` is zero by construction.
    """

    operation: str = "modelo.aggregate"
    modelo: ModeloCode
    period: Period
    provider: PerModeloAggregationContributor
    observation_count: NonNegativeInt
    source_kinds: list[BindingSourceKind] = Field(default_factory=list)
    result_row_count: NonNegativeInt
    clave_breakdown: list[WithholdingClaveBreakdownPayload] = Field(default_factory=list)
    withholding_window: WithholdingWindowReadbackPayload | None = None

    @field_validator("provider", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_provider(cls, value: object) -> object:
        """Hydrate a raw provider token to its closed-enum member.

        The strict schema base does not coerce ``str`` -> ``StrEnum``, so a
        payload re-validated from its own JSON rendering is lifted here. An
        unknown token raises rather than passing through as free text.
        """
        if isinstance(value, str) and not isinstance(value, PerModeloAggregationContributor):
            return PerModeloAggregationContributor(value)
        return value

    @field_validator("source_kinds", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_source_kinds(cls, value: object) -> object:
        """Hydrate raw source-kind tokens to their closed-enum members."""
        if is_object_list(value):
            return [
                BindingSourceKind(item) if isinstance(item, str) and not isinstance(item, BindingSourceKind) else item
                for item in value
            ]
        return value

    @field_validator("source_kinds")
    @classmethod
    @pydantic_validation_boundary
    def _source_kinds_are_unique(cls, value: list[BindingSourceKind]) -> list[BindingSourceKind]:
        """Mirror the canonical result's uniqueness invariant."""
        if len(value) != len(set(value)):
            raise ValueError("source_kinds must be unique")
        return value


class WorkPreviewMaritimeExemptionResult(OutputSchema):
    """Envelope result for ``modelo.work.preview_maritime_exemption``.

    ``casilla_values`` is a convenience mapping keyed by :class:`CasillaId`;
    ``observations`` reuses :class:`CasillaObservationPayload` for grounded
    legal-reference and source-reference identifiers.
    """

    operation: str = "modelo.work.preview_maritime_exemption"
    worker_class: str | None = None
    vessel_flag: str | None = None
    waters_type: str | None = None
    vessel_registry: str | None = None
    retmar_registered: bool = False
    retmar_mandatory_filing: bool = False
    retmar_warning: str | None = None
    casilla_values: dict[CasillaId, str] = Field(default_factory=dict)
    observations: list[CasillaObservationPayload] = Field(default_factory=list)
