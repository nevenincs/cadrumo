"""Modelo declaration export: write a verified-complete or filed calculation revision to a local AEAT-compatible file.

:func:`~cadrumo.application.modelo.export_modelo_revision` accepts a
:class:`~CalculationRevision` id, rebuilds and approves a
:class:`~domain.filing.ModeloDraft` from the revision replay inputs,
then writes a fichero-BOE-formatted artefact to the operator-supplied output
path. A ``MODELO_EXPORTED`` event is appended to the
:class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Export consumes the registry-authored fichero-BOE layouts through the filing
runtime schema provider; Python code owns orchestration and safety checks, while
the registry remains the authority for record fields, casillas, header keys, and
provenance. The service refuses non-exportable revision states, cross-bucket
targets, missing profile facts, unclean cross-period prerequisites, unmatched IVA
wallet decisions, missing ledger evidence, and unusable output paths before the
operator-visible file is committed.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. Export is fundamentally an offline operation
that produces a file the operator presents through sede.agenciatributaria.gob.es
themselves.

The CLI verb ``aeat app modelo export`` is a thin delegate over this
service.

See Also:
    :func:`~cadrumo.application.modelo._revision_replay_inputs.revision_filing_replay_inputs`:
        Reconstructs the filing inputs from the persisted revision.
    :func:`~cadrumo.application.filing.build_draft`:
        Builds the transient registry-backed draft that is exported.
    :func:`~cadrumo.application.filing.export_draft`:
        Serializes the approved draft through registry export layouts.
    :func:`~cadrumo.application.modelo._verification_actions.require_cross_period_clean_state`:
        Rechecks cross-period filing prerequisites before writing the export.
    :func:`~cadrumo.application.modelo._result_disposition_resolution.resolve_modelo_result_disposition`:
        Determines the fichero declaration type and refund disposition.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, Field, NonNegativeInt

from ...adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ...core.atomic_write import StagedPublication, hardened_staged_publication
from ...core.export_layout_format import ExportLayoutFormat
from ...core.filing_producer_key import FilingProducerKey
from ...core.filing_year import FilingYear
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest, PrefixedContentDigest, WorkUnitId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.payment_election import PaymentElection
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.product_identity import AeatProductSoftwareIdentity
from ...core.refund_election import RefundElection
from ...core.result_disposition import ResultDisposition
from ...core.time.clock import now as _utc_now
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
    compute_registro_regularizacion,
)
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.schema import DataBindingDefinition
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.deadlines.models import ModeloIVAProfile, TaxpayerProfile
from ...domain.filing.errors import FilingExportError
from ...domain.filing.protocols import ModeloInputs
from ...domain.filing.schema import ModeloCasillaProvenance, ModeloDraft
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.justificante import JustificanteRepositoryProtocol
from ...domain.modelos.calculation_revision import SEALED_REVISION_STATES, CalculationRevision
from ...domain.modelos.errors import ModeloError, ModeloExportError
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.prorrata_register.register import ProrrataRegister
from ..aggregation import (
    IvaDifferentiatedDeductionContribution,
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations_from_repositories,
    resolve_iva_differentiated_deduction_contributions,
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)
from ..calculations._m303_regimen_simplificado_annual_summary import (
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..calculations.cross_period_clean_state import CrossPeriodExpectedMemberSet
from ..calculations.observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    PriorDomiciliationElectionProjection,
)
from ..filing._draft_construction import build_draft
from ..filing._export import export_draft, export_layout_renderability_reason
from ..filing.draft_review import approve_draft
from ..filing.export_verification import DeclaracionExportResult, assert_export_artifact_matches_receipt
from ..filing.producer_snapshot import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M303FilingFacts,
    Modelo111ProfileFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from ..filing.runtime import RegistrySchemaAccessor, build_runtime_schema_provider, filing_profile_from_taxpayer
from ._action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPreconditionErrorMixin,
    ModeloPriorDomiciliationElectionRefusedError,
    WorkUnitNotFoundError,
)
from ._export_amendment_evidence import resolve_persisted_amendment_export_evidence
from ._iva_wallet_gate import require_persisted_iva_compensation_decision_matches_revision
from ._ledger_evidence_gate import deductible_iva_evidence_gap_transaction_ids
from ._m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies,
    m303_regimen_simplificado_scope_for_profile,
)
from ._preconditions import (
    ModeloPreconditionFailure,
    build_modelo_precondition_failure,
    build_modelo_precondition_failure_for_scenario,
)
from ._prior_domiciliation import resolve_prior_domiciliation_election
from ._profile_export_binding import (
    resolve_declaration_contact,
    resolve_export_identity,
    resolve_profile_export_values,
)
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from ._result_disposition_resolution import resolve_modelo_result_disposition
from ._revision_persistence import (
    emit_modelo_bucket_event as _emit_bucket_event,
)
from ._revision_persistence import (
    require_filing_instance_evidence_for_work_unit,
)
from ._revision_replay_inputs import revision_filing_replay_inputs
from ._row_source_identity_replay import attach_revision_row_source_identities
from ._verification_actions import (
    cross_period_expected_member_sets_from_profile,
    require_cross_period_clean_state,
)

_LOCAL_EXPORT_EVIDENCE_STATUS = "local_export_not_official_aeat_filing_evidence"
_LOCAL_EXPORT_OFFICIAL_EVIDENCE_MESSAGE = (
    "Local export wrote an AEAT-compatible fichero-BOE file only; it is not official AEAT filing evidence. "
    "Official evidence comes from AEAT after filing: justificante, consulta de declaraciones presentadas, "
    "or CSV cotejo."
)
_COMPLETENESS_UNVERIFIED_MESSAGE = (
    "This fichero-BOE was NOT completeness-verified: its modelo revision declares no calculation-completeness "
    "manifest, so the structural-parity gate could not confirm every required casilla reached disk. The file may "
    "be structurally thin. Review the exported casillas against the official Diseño de Registros before filing."
)


class ModeloExportReadinessRefusal(BaseModel):
    """Application-owned readiness fact and its declared operator outcome."""

    model_config = _STRICT_FROZEN

    reason: str
    context: dict[str, str]
    precondition_failure: ModeloPreconditionFailure


def _modelo_export_layout_readiness_refusal(
    *,
    modelo: str,
    layout: ExportLayoutDefinition | None,
) -> ModeloExportReadinessRefusal | None:
    """Project one resolved export layout into the application readiness contract."""
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is None:
        return None
    context = {"modelo": modelo, "reason": reason}
    if layout is not None:
        context["layout_id"] = str(layout.id)
        context["layout_format"] = str(layout.format)
    return ModeloExportReadinessRefusal(
        reason=reason,
        context=context,
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key="modelo.readiness",
            scenario_id="modelo.readiness.export_layout.unrenderable",
            evidence_id="modelo.readiness.export_layout",
            evidence_values=context,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            action_argument_values={"modelo": modelo},
        ),
    )


def modelo_export_readiness_refusal(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_ready: bool,
) -> ModeloExportReadinessRefusal | None:
    """Return the one declared readiness outcome when local export is unavailable.

    The application evaluates layout renderability and chooses the declared
    action.  The CLI may only resolve this returned verdict against its live
    surface before presentation.
    """
    if not registry_ready:
        return None
    provider = build_runtime_schema_provider(
        filing_year=filing_year,
        period=period,
        modelos=(modelo,),
    )
    subview = provider.get_subview(modelo)
    layout = subview.export_layouts[0] if subview.export_layouts else None
    return _modelo_export_layout_readiness_refusal(modelo=modelo, layout=layout)




class ModeloIvaWalletDecisionProvenance(BaseModel):
    """Redacted audit join for the Modelo 303 IVA wallet authority decision.

    This intentionally excludes taxpayer identifiers, wallet amounts, and local
    recurrence amounts. The fingerprint lets audits join back to encrypted
    secure-object storage without copying live fiscal values into export events
    or result payloads.
    """

    model_config = _STRICT_FROZEN

    decision_ref: PrefixedContentDigest
    selected_authority: str = Field(min_length=1, max_length=64)
    divergence: str = Field(min_length=1, max_length=64)
    target_year: FilingYear
    target_period: Period
    authority_source_kinds: tuple[str, ...] = Field(default_factory=tuple)
    authority_source_refs: tuple[PrefixedContentDigest, ...] = Field(default_factory=tuple)


class _PreparedModeloExport(NamedTuple):
    """Validated inputs shared by draft approval and export persistence."""

    work_unit: WorkUnit
    revision: CalculationRevision
    period: Period
    schema_provider: RegistrySchemaAccessor
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None
    prior_domiciliation_election: PriorDomiciliationElectionProjection
    amendment_evidence: AmendmentEvidence | None


class ModeloExportCrossBucketRefusedError(ModeloError):
    """Raised when the addressed revision's parent work unit belongs to a bucket other than the active profile bucket.

    Bucket events must scope to the active bucket; allowing the service
    to emit into a foreign bucket would let any caller pollute another
    operator's history.
    """


class ModeloExportNoActiveBucketError(ModeloError):
    """Raised when no active profile bucket is configured.

    Export needs an active bucket because the resulting MODELO_EXPORTED
    event is scoped to a bucket id and the work-unit lookup is
    bucket-bound.
    """


class ModeloExportEvidenceMissingError(ModeloPreconditionErrorMixin, ModeloExportError):
    """Raised when a ledger-derived revision lacks exportable evidence."""


class ModeloExportUnsupportedError(ModeloExportError):
    """Raised when a modelo revision has no renderable local fichero-BOE export layout."""


class ModeloExportOutputPathError(ModeloExportError):
    """Raised when the operator-supplied ``--output`` path cannot receive the artefact.

    Validated up front, before any fichero-BOE bytes are written, so an
    unusable destination (empty path, an existing directory, a missing or
    unwritable parent directory) is refused with a typed, operator-facing
    message instead of surfacing a raw ``OSError`` traceback from the
    staged write — and crucially before any cleartext financial bytes
    touch disk.
    """


class ModeloExportCommand(BaseModel):
    """Strict input contract for :func:`~cadrumo.application.modelo.export_modelo_revision`.

    Attributes:
        calculation_revision_id: SHA-256 hex id of the calculation
            revision to export. Must be in ``VERIFICADO_COMPLETO`` or
            ``FILED`` state.
        output_path: Absolute or working-directory-relative path to
            write the fichero-BOE artefact. Parent directories are
            created if missing.
        actor: Operator identifier captured into the
            ``MODELO_EXPORTED`` event payload and used as the draft
            ``approved_by`` field for the transient export draft.
        refund_election: The operator's per-filing Modelo 303 negative-result
            disposition election threaded into the shared disposition resolver so
            the exported fichero "Tipo de declaración" matches the election made at
            filing. Defaults to ``COMPENSAR``; ``DEVOLVER`` requests the credit
            back and is honoured only for a lawful refund period (refused
            otherwise).
        payment_election: The operator's positive-result settlement election.
            ``INGRESO`` retains the standard declaration type, while a supported
            Modelo 303 ``DOMICILIACION`` resolves to ``U``. Unsupported or
            sign-incompatible elections are refused by the shared resolver.
        prior_domiciliation_election: Explicit Modelo 303 action for a prior
            domiciliation. It is required for Modelo 303; non-303 exports
            resolve the neutral ``KEEP`` value internally.
        product_software_identity: Explicit, reviewed product/software
            authority for the Modelo 303 DP30300 envelope. It is required for
            Modelo 303 and is not inferred from a taxpayer or presenter.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    output_path: Path
    actor: str = Field(min_length=1, max_length=128)
    presenter: PresenterIdentity | None = None
    taxpayer_identity: TaxpayerIdentityFacts | None = None
    amendment_evidence: AmendmentEvidence | None = None
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection | None = None
    product_software_identity: AeatProductSoftwareIdentity | None = None


class ModeloExportResult(BaseModel):
    """Receipt produced by :func:`~cadrumo.application.modelo.export_modelo_revision`.

    Composes the lower-level
    :class:`~cadrumo.application.filing.DeclaracionExportResult` (already a
    byte-level receipt of the written file) with the work-unit-level
    identity the operator addresses.

    Attributes:
        calculation_revision_id: The exported revision id.
        work_unit_id: The parent work unit's id.
        bucket_id: The bucket the work unit lives in (always equal to
            the active profile bucket at export time).
        modelo: AEAT modelo identifier.
        filing_year: AEAT filing year.
        period: Filing period as a typed :class:`~cadrumo.core.Period` value.
        output_path: Absolute path the file was written to.
        byte_size: Size of the written file in bytes.
        file_sha256: Hex-encoded SHA-256 of the written bytes.
        format: Wire format string (currently always ``"fichero-boe"``).
        exported_at: UTC timestamp of the write.
        actor: Operator identifier captured into the event.
        bucket_event_id: Id of the ``MODELO_EXPORTED`` event appended
            to the catalogue.
        resolved_result_disposition: The single resolved AEAT declaration type.
        payment_election: The semantic positive-result election when applicable.
        refund_election: The semantic negative-result election when applicable.
        casilla_provenance: Regulatory grounding for casillas covered
            by the exported fichero-BOE layout.
    """

    model_config = _STRICT_FROZEN

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    output_path: Path
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    format: str = Field(min_length=1)
    exported_at: datetime
    actor: str = Field(min_length=1, max_length=128)
    bucket_event_id: str = Field(min_length=1, max_length=128)
    resolved_result_disposition: ResultDisposition = ResultDisposition.INGRESO
    payment_election: PaymentElection | None = None
    refund_election: RefundElection | None = None
    prior_domiciliation_election: PriorDomiciliationElectionProjection = Field(
        default_factory=lambda: PriorDomiciliationElectionProjection(
            election=PriorDomiciliationElection.KEEP,
        ),
    )
    casilla_provenance: tuple[ModeloCasillaProvenance, ...] = Field(default_factory=tuple)
    iva_wallet_decision_provenance: ModeloIvaWalletDecisionProvenance | None = None
    local_evidence_status: str = Field(default=_LOCAL_EXPORT_EVIDENCE_STATUS, min_length=1)
    official_evidence_message: str = Field(default=_LOCAL_EXPORT_OFFICIAL_EVIDENCE_MESSAGE, min_length=1)
    completeness_unverified: bool = Field(
        default=False,
        description=(
            "True when a fixed-width fichero-BOE export could not be completeness-verified because the modelo "
            "revision declares no calculation-completeness manifest, so the structural-parity gate did not run. "
            "The CLI surfaces a non-blocking coverage advisory when set. False when the gate ran (manifest present) "
            "or the transport is not the fixed-width fichero-BOE."
        ),
    )

    @property
    def completeness_advisory_message(self) -> str:
        """Operator-facing coverage advisory text for a completeness-unverified export."""
        return _COMPLETENESS_UNVERIFIED_MESSAGE


def _sha256_ref(value: str) -> str:
    return f"sha256:{sha256_hex(value.encode('utf-8'))}"


def _validate_output_path(output_path: Path) -> None:
    """Refuse an unusable ``--output`` destination before writing any bytes.

    A clean typed refusal here is the only safe place to reject a bad
    destination: once the staged write has run, real fichero-BOE financial
    bytes already exist in the staging sibling, and a late ``OSError`` at
    publication would surface a raw traceback for a destination that was
    unusable before a single byte was rendered.

    Raises:
        ModeloExportOutputPathError: When the path is empty, names an
            existing directory, or its parent directory is missing or
            not a directory.
    """
    raw = str(output_path).strip()
    if not raw or raw == ".":
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": raw or "(empty)", "reason": "path is empty"},
        )
    if output_path.is_dir():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "path is an existing directory"},
        )
    parent = output_path.parent
    if not parent.exists():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "parent directory does not exist"},
        )
    if not parent.is_dir():
        raise ModeloExportOutputPathError(
            translated_message="application.modelo.errors.export_output_path_invalid",
            context={"output_path": str(output_path), "reason": "parent path is not a directory"},
        )


def _iva_wallet_decision_export_provenance(
    decision: IvaCompensationReconciliationDecision | None,
) -> ModeloIvaWalletDecisionProvenance | None:
    """Project an IVA wallet decision into a redacted export/event join record."""
    if decision is None:
        return None
    return ModeloIvaWalletDecisionProvenance(
        decision_ref=_sha256_ref(decision.model_dump_json()),
        selected_authority=str(decision.selected_authority),
        divergence=str(decision.divergence),
        target_year=decision.target_year,
        target_period=decision.target_period,
        authority_source_kinds=tuple(str(source.source_kind) for source in decision.authority_sources),
        authority_source_refs=tuple(_sha256_ref(source.source_locator) for source in decision.authority_sources),
    )


iva_wallet_decision_export_provenance = _iva_wallet_decision_export_provenance


def _raise_if_ledger_export_evidence_missing(revision: CalculationRevision) -> None:
    """Refuse ledger-derived exports that lack bundled evidence or a reference."""
    if not revision.source_transaction_ids:
        return
    if revision.ledger_filing_evidence is not None:
        return
    if revision.ledger_filing_snapshot is not None:
        return
    raise ModeloExportEvidenceMissingError(
        translated_message="application.modelo.errors.export_ledger_evidence_missing",
        context={"calculation_revision_id": revision.calculation_revision_id},
    )


def _require_exportable_revision_state(revision: CalculationRevision) -> None:
    if revision.state not in SEALED_REVISION_STATES:
        raise CalculationRevisionStateError(
            translated_message="application.modelo.errors.export_revision_state_refused",
            context={
                "calculation_revision_id": revision.calculation_revision_id,
                "state": revision.state.value,
            },
        )


def _compose_export_dictionary_values(
    *,
    draft: ModeloDraft,
    taxpayer_identity: TaxpayerIdentityFacts,
    bucket_id: str,
    profile_export_bindings: Sequence[DataBindingDefinition] = (),
) -> dict[str, object]:
    """Resolve typed XML dictionary values from canonical profile bindings."""
    values: dict[str, object] = dict(
        resolve_profile_export_values(profile_export_bindings, bucket_id=bucket_id),
    )
    if taxpayer_identity.full_name is None:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={"cause": "XML dictionary export requires exact taxpayer full_name"},
        )
    values["DPNIF_D"] = draft.profile_tax_id
    values["DP_APENOM_D"] = taxpayer_identity.full_name
    return values


def _resolve_work_unit_period(work_unit: WorkUnit) -> Period:
    """Return the typed :class:`~cadrumo.core.Period` carried by the work unit."""
    if work_unit.period.filing_year != work_unit.filing_year:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_period_unmappable",
            context={"work_unit_id": work_unit.work_unit_id, "period": work_unit.period.registry_token},
        )
    return work_unit.period


def _raise_if_export_layout_unsupported(*, work_unit: WorkUnit, schema_provider: RegistrySchemaAccessor) -> None:
    """Refuse a modelo whose registry snapshot cannot render fichero-BOE bytes."""
    modelo = str(work_unit.modelo)
    subview = schema_provider.get_subview(modelo)
    layout = subview.export_layouts[0] if subview.export_layouts else None
    reason = export_layout_renderability_reason(modelo, layout)
    if reason is None:
        return
    context = {
        "modelo": modelo,
        "reason": reason,
    }
    if layout is not None:
        context["layout_id"] = layout.id
        context["layout_format"] = layout.format
    raise ModeloExportUnsupportedError(
        translated_message="application.modelo.errors.export_unsupported",
        context=context,
    )


def _require_prior_domiciliation_marker_layout(
    *,
    work_unit: WorkUnit,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Require the selected registry revision to own the rectificativa ``X`` field."""
    if prior_domiciliation_election.election is PriorDomiciliationElection.KEEP:
        return
    marker_producer_key = FilingProducerKey.PRIOR_DOMICILIATION_ACTION
    layouts = schema_provider.get_subview(str(work_unit.modelo)).export_layouts
    if any(
        field.producer_key is marker_producer_key
        for layout in layouts
        for record in layout.records
        for field in record.fields
    ):
        return
    raise ModeloPriorDomiciliationElectionRefusedError(
        translated_message="errors.refused.refused_modelo_prior_domiciliation_election",
        context={
            "modelo": str(work_unit.modelo),
            "revision_id": work_unit.revision_id,
            "producer_key": marker_producer_key.value,
            "revision_renders_action_marker": False,
        },
    )


def _approve_export_draft(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    actor: str,
    approved_at: datetime,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[Period, ModeloDraft]:
    """Build and approve the export draft for one :class:`~CalculationRevision`.

    The :class:`~cadrumo.domain.deadlines.TaxpayerProfile` is forwarded to
    :func:`~cadrumo.application.modelo._revision_replay_inputs.revision_filing_replay_inputs`
    so export uses the same profile-applicability relation inputs as the filing
    workflow gate. Returns the resolved :class:`~cadrumo.core.Period` and approved
    :class:`~domain.filing.ModeloDraft`.
    """
    inputs: ModeloInputs = revision_filing_replay_inputs(
        revision=revision,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
    )
    try:
        draft = build_draft(
            modelo=work_unit.modelo,
            period=period,
            profile=filing_profile_from_taxpayer(workflow_profile),
            inputs=inputs,
            schema_provider=schema_provider,
        )
        draft = attach_revision_row_source_identities(draft=draft, revision=revision)
        approved = approve_draft(
            draft,
            bucket_id=work_unit.bucket_id,
            approved_by=actor,
            schema_provider=schema_provider,
            approved_at=approved_at,
        )
    except FilingExportError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_approval_failed",
            context={"calculation_revision_id": revision.calculation_revision_id},
        ) from exc
    return period, approved


def _resolve_m303_export_arrivals(
    *,
    period: Period,
    prorrata_register: ProrrataRegister,
    iva_aggregation: IvaLedgerAggregation,
    bienes_register: BienesInversionIvaRegister,
) -> tuple[
    tuple[IvaDifferentiatedDeductionContribution, ...],
    BienesInversionIvaRegister,
    RegistroRegularizacionResult,
]:
    """Assemble current canonical register arrivals from the work-unit-bound register."""
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=period.filing_year,
        period=period.registry_token,
    )
    if prorrata_register.is_sectorized:
        apportionment = iva_aggregation.prorrata_apportionment
        if apportionment is None or not apportionment.sector_apportionments:
            raise FilingProducerSnapshotError(
                "modelo 303 differentiated sectors require canonical sector apportionment",
            )
        contributions = resolve_iva_differentiated_deduction_contributions(
            snapshot.revision,
            iva_aggregation.observations,
            apportionment=apportionment,
        )
    else:
        contributions = ()
    definitive_by_identifier: dict[str, Decimal] = {}
    for record in bienes_register.in_window_records(period.filing_year):
        entry = prorrata_register.entry_for(
            period.filing_year,
            sector_id=record.prorrata_sector_id,
        )
        if entry is not None and entry.definitive_percentage is not None:
            definitive_by_identifier[record.identifier] = entry.definitive_percentage
    regularisation_result = compute_registro_regularizacion(
        bienes_register,
        regularizacion_year=period.filing_year,
        prorrata_definitiva_by_identifier=definitive_by_identifier,
    )
    if regularisation_result.pending_percentage_count:
        raise FilingProducerSnapshotError(
            "modelo 303 Bienes de inversión regularisation requires definitive prorrata evidence",
        )
    return contributions, bienes_register, regularisation_result


def _require_m303_regimen_simplificado_scope_matches_profile(
    *,
    filing_facts: M303FilingFacts,
    workflow_profile: TaxpayerProfile,
) -> None:
    """Require persisted M303 evidence to agree with the canonical profile scope."""
    expected_scope = m303_regimen_simplificado_scope_for_profile(workflow_profile)
    if filing_facts.regimen_simplificado.scope_decision != expected_scope:
        raise FilingProducerSnapshotError(
            "modelo 303 simplified-regime filing evidence disagrees with the canonical IVA profile composition",
        )


def _build_export_producer_snapshot(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    resolved_result_disposition: ResultDisposition,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    amendment_evidence: AmendmentEvidence | None,
) -> FilingProducerSnapshot:
    """Build the sole typed producer boundary or refuse before any write."""
    presenter, taxpayer_identity = _require_export_identity(command, work_unit=work_unit)
    try:
        modelo = Modelo(str(work_unit.modelo))
        iva_profile = workflow_profile.iva
        model_profile, m303_filing_facts = _resolve_export_model_profile(
            modelo=modelo,
            work_unit=work_unit,
            revision=revision,
            workflow_profile=workflow_profile,
            iva_profile=iva_profile,
        )
        return build_filing_producer_snapshot(
            modelo=modelo,
            taxpayer_tax_id=workflow_profile.tax_id,
            taxpayer_identity=taxpayer_identity,
            presenter=presenter,
            model_profile=model_profile,
            elections=FilingElectionFacts(
                result_disposition=resolved_result_disposition,
                payment=command.payment_election,
                refund=command.refund_election,
                prior_domiciliation=prior_domiciliation_election.election,
            ),
            amendment_evidence=amendment_evidence,
            refund_account=iva_profile.refund_account if iva_profile is not None else None,
            charge_account=iva_profile.charge_account if iva_profile is not None else None,
            m303_filing_facts=m303_filing_facts,
            # Read separately from the identity pair: AEAT's "persona con quien
            # relacionarse" is a third party, and under a gestor it is routinely
            # neither the taxpayer nor the presenter.
            declaration_contact=resolve_declaration_contact(bucket_id=str(work_unit.bucket_id)),
        )
    except (FilingProducerSnapshotError, ValueError) as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause_type": type(exc).__name__,
            },
        ) from exc


def _require_export_identity(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
) -> tuple[PresenterIdentity, TaxpayerIdentityFacts]:
    """Resolve the producer identity, deriving it from the profile when unset.

    An explicit command identity wins, so a caller that knows better -- a
    future representative or gestor surface -- overrides without threading
    anything new through this path. Otherwise the identity is read from the
    filing profile in the work unit's OWN bucket, which is the same bucket the
    export's other profile-sourced values already resolve against; taking it
    from the active bucket instead would let a cross-bucket export stamp one
    taxpayer's declaration with another's name.

    The refusal survives derivation rather than being replaced by it: a profile
    that is absent, or that declares no tax id or no usable name, still refuses
    here instead of producing a filed artefact with a half-built identity.
    """
    if command.presenter is not None and command.taxpayer_identity is not None:
        return command.presenter, command.taxpayer_identity
    derived = resolve_export_identity(bucket_id=str(work_unit.bucket_id))
    presenter = command.presenter or (derived[0] if derived else None)
    taxpayer_identity = command.taxpayer_identity or (derived[1] if derived else None)
    if presenter is None or taxpayer_identity is None:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause": "explicit presenter and taxpayer identity facts are required",
            },
        )
    return presenter, taxpayer_identity


def _resolve_export_model_profile(
    *,
    modelo: Modelo,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    iva_profile: ModeloIVAProfile | None,
) -> tuple[FilingModelProfileFacts, M303FilingFacts | None]:
    if modelo is Modelo.M303:
        if iva_profile is None:
            raise FilingProducerSnapshotError("modelo 303 requires an explicitly declared IVA profile")
        return iva_profile, _resolve_m303_filing_facts_for_export(
            work_unit=work_unit,
            revision=revision,
            workflow_profile=workflow_profile,
        )
    if modelo is Modelo.M202:
        return Modelo202ProducerProfile(taxpayer_profile=workflow_profile, activities=()), None
    if modelo is Modelo.M111:
        return Modelo111ProfileFacts(colegio_concertado=workflow_profile.colegio_concertado), None
    return GeneralFilingProfileFacts(), None


def _resolve_m303_filing_facts_for_export(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
) -> M303FilingFacts:
    filing_instance_evidence = require_filing_instance_evidence_for_work_unit(
        work_unit=work_unit,
        revision=revision,
    )
    assert filing_instance_evidence is not None
    prorrata_register_repository = ProrrataRegisterRepository(bucket_id=work_unit.bucket_id)
    prorrata_register = prorrata_register_repository.load()
    iva_aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=work_unit.bucket_id,
        period=work_unit.period,
        prorrata_register_repository=prorrata_register_repository,
    )
    differentiated_contributions, bienes_register, regularisation_result = _resolve_m303_export_arrivals(
        period=filing_instance_evidence.m303.period,
        prorrata_register=prorrata_register,
        iva_aggregation=iva_aggregation,
        bienes_register=BienesInversionIvaRegisterRepository(bucket_id=work_unit.bucket_id).load(),
    )
    filing_facts = resolve_m303_filing_facts(
        evidence=filing_instance_evidence,
        supplier_regime=resolve_m303_supplier_regime_arrival(
            period=work_unit.period,
            iva_aggregation=iva_aggregation,
        ),
        prorrata_transition=resolve_m303_prorrata_transition_arrival(
            period=work_unit.period,
            prorrata_register=prorrata_register,
        ),
        prorrata_register=prorrata_register,
        differentiated_contributions=differentiated_contributions,
        bienes_register=bienes_register,
        regularisation_result=regularisation_result,
    )
    _require_m303_regimen_simplificado_scope_matches_profile(
        filing_facts=filing_facts,
        workflow_profile=workflow_profile,
    )
    return filing_facts


def _persist_exported_draft(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    period: Period,
    approved: ModeloDraft,
    exported_at: datetime,
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    amendment_evidence: AmendmentEvidence | None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    schema_provider: RegistrySchemaAccessor,
) -> ModeloExportResult:
    resolved_result_disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=command.refund_election,
        payment_election=command.payment_election,
    )
    producer_snapshot = _build_export_producer_snapshot(
        command=command,
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        resolved_result_disposition=resolved_result_disposition,
        prior_domiciliation_election=prior_domiciliation_election,
        amendment_evidence=amendment_evidence,
    )
    export_subview = schema_provider.get_subview(str(work_unit.modelo))
    export_layout = export_subview.export_layouts[0] if export_subview.export_layouts else None
    dictionary_values = (
        _compose_export_dictionary_values(
            draft=approved,
            taxpayer_identity=producer_snapshot.taxpayer_identity,
            bucket_id=work_unit.bucket_id,
            profile_export_bindings=export_subview.profile_export_bindings,
        )
        if export_layout is not None and export_layout.format is ExportLayoutFormat.XML_DICTIONARY
        else {}
    )
    # The fichero-BOE bytes are staged, the MODELO_EXPORTED event is committed,
    # and only then does the artefact become operator-visible: a crash between
    # the write and the event leaves a staged file carrying no provenance
    # rather than a filing artefact no event accounts for. The staging file is
    # an unguessable sibling reserved by the shared deferred-publish tier,
    # which discards it on EVERY exit that does not publish -- including an
    # operator interrupt -- so cleartext financial data cannot outlive a failed
    # export next to the destination the operator chose.
    with hardened_staged_publication(command.output_path) as staged:
        receipt = _write_export_staging(
            staged=staged,
            command=command,
            approved=approved,
            producer_snapshot=producer_snapshot,
            dictionary_values=dictionary_values,
            prior_domiciliation_election=prior_domiciliation_election.election,
            product_software_identity=command.product_software_identity,
            schema_provider=schema_provider,
        )
        event = _emit_export_event(
            command=command,
            work_unit=work_unit,
            receipt=receipt,
            iva_wallet_provenance=iva_wallet_provenance,
            resolved_result_disposition=resolved_result_disposition,
            prior_domiciliation_election=prior_domiciliation_election,
            exported_at=exported_at,
            bucket_event_repository=bucket_event_repository,
        )
        # Defence in depth: even though _validate_output_path refused an
        # existing-directory / unwritable destination up front, a concurrent
        # change to the destination (a TOCTOU race) can still make the
        # publication fail with an OSError. Translate it to the same typed
        # refusal that destination check raises, rather than surfacing a raw
        # traceback from inside the write substrate.
        try:
            staged.publish()
        except OSError as exc:
            raise ModeloExportOutputPathError(
                translated_message="application.modelo.errors.export_output_path_invalid",
                context={"output_path": str(command.output_path), "reason": str(exc)},
            ) from exc

    # The receipt below was measured against the staging file, and the result and
    # the durable MODELO_EXPORTED event both publish those numbers against
    # ``command.output_path`` instead. Re-bind them to the artefact that
    # actually landed, through the same check the draft writer used, so the
    # published size and digest are proven of the operator-visible file rather
    # than transplanted from the staging path the rename has just consumed.
    assert_export_artifact_matches_receipt(receipt, artifact_path=command.output_path)

    # Coverage honesty: a fixed-width fichero-BOE whose revision declares no
    # completeness manifest cannot be structural-parity-verified (the pre-write
    # gate in export_draft only runs when a manifest is present), so surface a
    # non-blocking advisory rather than implying the export was verified.
    _export_subview = schema_provider.get_subview(str(work_unit.modelo))
    _export_layout = _export_subview.export_layouts[0] if _export_subview.export_layouts else None
    completeness_unverified = (
        _export_layout is not None
        and _export_layout.format is ExportLayoutFormat.FIXED_WIDTH
        and _export_subview.completeness_manifest is None
    )

    return ModeloExportResult(
        calculation_revision_id=command.calculation_revision_id,
        work_unit_id=work_unit.work_unit_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=period,
        output_path=command.output_path,
        byte_size=receipt.byte_size,
        file_sha256=receipt.file_sha256,
        format=receipt.format.value,
        exported_at=exported_at,
        actor=command.actor,
        bucket_event_id=event.event_id,
        resolved_result_disposition=resolved_result_disposition,
        payment_election=(
            command.payment_election
            if resolved_result_disposition
            in {
                ResultDisposition.INGRESO,
                ResultDisposition.DOMICILIACION,
                ResultDisposition.CUENTA_CORRIENTE_INGRESO,
            }
            else None
        ),
        refund_election=(
            command.refund_election
            if resolved_result_disposition
            in {
                ResultDisposition.COMPENSACION,
                ResultDisposition.DEVOLUCION,
                ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
                ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
            }
            else None
        ),
        prior_domiciliation_election=prior_domiciliation_election,
        casilla_provenance=receipt.casilla_provenance,
        iva_wallet_decision_provenance=iva_wallet_provenance,
        completeness_unverified=completeness_unverified,
    )


def _write_export_staging(
    *,
    staged: StagedPublication,
    command: ModeloExportCommand,
    approved: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object],
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor,
) -> DeclaracionExportResult:
    try:
        return export_draft(
            approved,
            output_path=staged.path,
            producer_snapshot=producer_snapshot,
            dictionary_values=dictionary_values,
            prior_domiciliation_election=prior_domiciliation_election,
            product_software_identity=product_software_identity,
            schema_provider=schema_provider,
        )
    except FilingExportError as exc:
        # Surface the underlying FilingExportError cause in the typed context
        # (aeat-cli-contract: structured provenance
        # rides on context). The generic write-failed message otherwise masks
        # structural causes the operator must act on — most importantly a modelo
        # whose registry snapshot declares no export layout (e.g. Modelo 202 has
        # no Diseño de Registros authored, so a verified-complete revision cannot
        # be written to fichero-BOE), which reads as a misleading disk/IO failure.
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause": str(exc),
            },
        ) from exc


def _emit_export_event(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    receipt: DeclaracionExportResult,
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None,
    resolved_result_disposition: ResultDisposition,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    exported_at: datetime,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
) -> BucketEvent:
    # Route through the shared ``_emit_bucket_event`` helper every
    # other modelo service uses rather than re-implementing the
    # derive / append / save sequence inline. The helper performs a
    # single-catalogue ``save_many`` write (via
    # ``BucketEventHistoryRepository.save``), which is exactly what
    # export needs — there is no second persisted record to bundle,
    # so the multi-write co-transactional pattern does not apply here.
    # The staging ordering is preserved: the event commits inside the
    # helper before the caller publishes, and a failure here propagates
    # out of the staging context, which discards the staged file.
    event_payload = {
        "calculation_revision_id": command.calculation_revision_id,
        "work_unit_id": work_unit.work_unit_id,
        "output_path": str(command.output_path),
        "byte_size": str(receipt.byte_size),
        "file_sha256": receipt.file_sha256,
        "format": receipt.format.value,
        "modelo": work_unit.modelo,
        "filing_year": str(work_unit.filing_year),
        "period": work_unit.period.registry_token,
        "resolved_result_disposition": resolved_result_disposition.value,
    }
    if resolved_result_disposition in {
        ResultDisposition.INGRESO,
        ResultDisposition.DOMICILIACION,
        ResultDisposition.CUENTA_CORRIENTE_INGRESO,
    }:
        event_payload["payment_election"] = command.payment_election.value
    if resolved_result_disposition in {
        ResultDisposition.COMPENSACION,
        ResultDisposition.DEVOLUCION,
        ResultDisposition.CUENTA_CORRIENTE_DEVOLUCION,
        ResultDisposition.DEVOLUCION_TRANSFERENCIA_EXTRANJERO,
    }:
        event_payload["refund_election"] = command.refund_election.value
    event_payload["prior_domiciliation_election"] = prior_domiciliation_election.election.value
    if prior_domiciliation_election.baseline_filing_record_id is not None:
        event_payload["prior_domiciliation_baseline_filing_record_id"] = (
            prior_domiciliation_election.baseline_filing_record_id
        )
        event_payload["prior_domiciliation_baseline_evidence_reference_id"] = (
            prior_domiciliation_election.baseline_evidence_reference_id or ""
        )
        event_payload["prior_domiciliation_baseline_result_disposition"] = (
            prior_domiciliation_election.baseline_result_disposition.value
            if prior_domiciliation_election.baseline_result_disposition is not None
            else ""
        )
        event_payload["prior_domiciliation_baseline_source_header_locator"] = (
            prior_domiciliation_election.baseline_source_header_locator or ""
        )
    if iva_wallet_provenance is not None:
        event_payload.update(
            {
                "iva_wallet_decision_ref": iva_wallet_provenance.decision_ref,
                "iva_wallet_selected_authority": iva_wallet_provenance.selected_authority,
                "iva_wallet_divergence": iva_wallet_provenance.divergence,
                "iva_wallet_target_year": str(iva_wallet_provenance.target_year),
                "iva_wallet_target_period": iva_wallet_provenance.target_period.registry_token,
                "iva_wallet_authority_source_kinds": ",".join(iva_wallet_provenance.authority_source_kinds),
                "iva_wallet_authority_source_refs": ",".join(iva_wallet_provenance.authority_source_refs),
            },
        )
    return _emit_bucket_event(
        repository=bucket_event_repository,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_EXPORTED,
        occurred_at=exported_at,
        actor=command.actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=command.calculation_revision_id,
        payload=event_payload,
    )


def _raise_if_deductible_iva_evidence_missing(revision: CalculationRevision) -> None:
    """Refuse legacy revisions whose deductible IVA evidence is incomplete."""
    deductible_gap_transaction_ids = deductible_iva_evidence_gap_transaction_ids(revision)
    if not deductible_gap_transaction_ids:
        return
    raise ModeloExportEvidenceMissingError(
        translated_message="application.modelo.errors.deductible_iva_evidence_missing",
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "transaction_ids": list(deductible_gap_transaction_ids),
            "reason": "deductible_iva_evidence_missing",
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.export",
            condition_id="modelo.export.deductible_iva_evidence.present",
            scenario_id="modelo.export.deductible_iva_evidence.missing",
            evidence_id="modelo.export.deductible_iva_evidence",
            evidence_values={
                "calculation_revision_id": revision.calculation_revision_id,
                "work_unit_id": revision.work_unit_id,
                "transaction_count": len(deductible_gap_transaction_ids),
                "transaction_ids": "|".join(deductible_gap_transaction_ids),
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


def _load_modelo_export_authorities(
    command: ModeloExportCommand,
    *,
    active_bucket_id: str,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
) -> tuple[CalculationRevision, WorkUnit]:
    revision = calculation_repository.load().get(command.calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": command.calculation_revision_id},
        )
    work_unit = work_unit_repository.load().get(revision.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": revision.work_unit_id},
        )
    try:
        require_filing_instance_evidence_for_work_unit(work_unit=work_unit, revision=revision)
    except ModeloError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context={
                "calculation_revision_id": command.calculation_revision_id,
                "cause_type": type(exc).__name__,
            },
        ) from exc
    if work_unit.bucket_id != active_bucket_id:
        raise ModeloExportCrossBucketRefusedError(
            translated_message="application.modelo.errors.export_cross_bucket_refused",
            context={"work_unit_id": work_unit.work_unit_id},
        )
    return revision, work_unit


def _prepare_modelo_export_schema(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
) -> tuple[Period, RegistrySchemaAccessor]:
    period = _resolve_work_unit_period(work_unit)
    schema_provider = build_runtime_schema_provider(
        filing_year=period.filing_year,
        period=period,
        modelos=(work_unit.modelo,),
    )
    _raise_if_export_layout_unsupported(work_unit=work_unit, schema_provider=schema_provider)
    from ._profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(work_unit)
    _require_persisted_required_bindings_resolved(work_unit=work_unit, revision=revision, action="export")
    return period, schema_provider


def _require_modelo_export_clean_state(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    iva_wallet_decision: IvaCompensationReconciliationDecision | None,
    calculation_observation_repository: CalculationObservationRepository,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> None:
    require_cross_period_clean_state(
        work_unit,
        observation_repository=calculation_observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        iva_compensation_decision=iva_wallet_decision,
        expected_member_sets=cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(workflow_profile).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        target_revision=revision,
    )


def _resolve_modelo_export_prior_domiciliation(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    schema_provider: RegistrySchemaAccessor,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    calculation_observation_repository: CalculationObservationRepository,
) -> PriorDomiciliationElectionProjection:
    is_m303 = str(work_unit.modelo) == Modelo.M303.value
    if is_m303 and command.prior_domiciliation_election is None:
        raise ModeloExportError(
            "Modelo 303 export requires an explicit prior-domiciliation election",
            context={"calculation_revision_id": command.calculation_revision_id},
        )
    if is_m303 and command.product_software_identity is None:
        raise ModeloExportError(
            "Modelo 303 export requires explicit product/software identity authority",
            context={"calculation_revision_id": command.calculation_revision_id},
        )
    if not is_m303 and command.product_software_identity is not None:
        raise ModeloExportError(
            "product/software identity is only admitted for the Modelo 303 filing envelope",
            context={"calculation_revision_id": command.calculation_revision_id},
        )
    prior_domiciliation_election = resolve_prior_domiciliation_election(
        election=(
            command.prior_domiciliation_election
            if is_m303
            else command.prior_domiciliation_election or PriorDomiciliationElection.KEEP
        ),
        work_unit=work_unit,
        revision=revision,
        filing_repository=filing_repository,
        observation_repository=calculation_observation_repository,
    )
    _require_prior_domiciliation_marker_layout(
        work_unit=work_unit,
        prior_domiciliation_election=prior_domiciliation_election,
        schema_provider=schema_provider,
    )
    return prior_domiciliation_election


def _prepare_modelo_export(
    command: ModeloExportCommand,
    *,
    active_bucket_id: str,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    calculation_observation_repository: CalculationObservationRepository,
    justificante_repository: JustificanteRepositoryProtocol | None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> _PreparedModeloExport:
    """Load and validate every persisted authority required before export bytes."""
    revision, work_unit = _load_modelo_export_authorities(
        command,
        active_bucket_id=active_bucket_id,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
    )
    amendment_evidence = resolve_persisted_amendment_export_evidence(
        command,
        revision,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        work_unit_repository=work_unit_repository,
        filing_repository=filing_repository,
        justificante_repository=justificante_repository,
    )
    _require_exportable_revision_state(revision)
    _raise_if_ledger_export_evidence_missing(revision)
    _raise_if_deductible_iva_evidence_missing(revision)
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=revision,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies(work_unit),
    )
    period, schema_provider = _prepare_modelo_export_schema(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=filing_repository,
    )
    iva_wallet_decision = require_persisted_iva_compensation_decision_matches_revision(
        work_unit,
        revision,
        repository=iva_compensation_decision_repository,
    )
    _require_modelo_export_clean_state(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        iva_wallet_decision=iva_wallet_decision,
        calculation_observation_repository=calculation_observation_repository,
        filing_repository=filing_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )
    prior_domiciliation_election = _resolve_modelo_export_prior_domiciliation(
        command,
        work_unit=work_unit,
        revision=revision,
        schema_provider=schema_provider,
        filing_repository=filing_repository,
        calculation_observation_repository=calculation_observation_repository,
    )
    return _PreparedModeloExport(
        work_unit=work_unit,
        revision=revision,
        period=period,
        schema_provider=schema_provider,
        iva_wallet_provenance=_iva_wallet_decision_export_provenance(iva_wallet_decision),
        prior_domiciliation_election=prior_domiciliation_election,
        amendment_evidence=amendment_evidence,
    )


def export_modelo_revision(
    command: ModeloExportCommand,
    *,
    workflow_profile: TaxpayerProfile,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    verification_repository: VerificationReportCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    iva_compensation_decision_repository: IvaWalletDecisionRepository | None = None,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    justificante_repository: JustificanteRepositoryProtocol | None = None,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    clock: datetime | None = None,
) -> ModeloExportResult:
    """Export a verified-complete or filed calculation revision to disk.

    ``workflow_profile`` is the
    :class:`~cadrumo.domain.deadlines.TaxpayerProfile` used to compose the filing
    draft headers and to replay profile-applicability relation inputs.

    Local-only: never contacts AEAT. Re-builds the filing draft from
    :func:`~cadrumo.application.modelo._revision_replay_inputs.revision_filing_replay_inputs`
    so the exported file reflects the same legal casilla and relation map that
    would be filed.

    The revision must be ``VERIFICADO_COMPLETO``, ``PRESENTADO``, or
    ``PRESENTADO_SUPERSEDIDO`` and must belong to the active bucket. Before
    writing any operator-visible file, the service validates the output path,
    export-layout renderability, profile readiness, ledger evidence, IVA wallet
    decision provenance, and cross-period clean state. It then rebuilds and
    approves a transient :class:`~domain.filing.ModeloDraft`, builds one typed
    filing producer snapshot, serializes through
    :func:`~cadrumo.application.filing.export_draft`, appends ``MODELO_EXPORTED`` to
    the bucket-event-history catalogue, and finally publishes the staged
    artefact onto the operator's path. Any write, event, or publication failure
    discards the staged cleartext artefact before raising.

    Returns:
        :class:`~cadrumo.application.modelo.ModeloExportResult`: The export
        receipt, including byte size, digest, event id, casilla provenance, and
        any redacted IVA wallet decision provenance.

    See Also:
        :class:`~cadrumo.application.modelo.ModeloExportCommand`:
            Strict input envelope for the revision id, output path, actor, and
            refund election.
        :func:`~cadrumo.application.filing.build_filing_producer_snapshot`:
            Builds the sole typed producer boundary consumed by the renderer.
        :func:`~cadrumo.application.modelo._export._validate_output_path`:
            Refuses unsafe destinations before fichero bytes are written.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id

    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloExportNoActiveBucketError(
            translated_message="application.modelo.errors.export_no_active_bucket",
        )

    # Validate the destination before touching the catalogue or writing any
    # bytes: an unusable --output (empty, existing directory, missing parent)
    # is a clean typed refusal here, never a raw OSError traceback at the
    # late publication — and never after cleartext financial bytes exist.
    _validate_output_path(command.output_path)

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository(
        m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
    )
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    vr_repo = verification_repository or VerificationReportCatalogueRepository()
    obs_repo = calculation_observation_repository or CalculationObservationRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    prepared = _prepare_modelo_export(
        command,
        active_bucket_id=active_bucket_id,
        workflow_profile=workflow_profile,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        calculation_observation_repository=obs_repo,
        justificante_repository=justificante_repository,
        iva_compensation_decision_repository=iva_compensation_decision_repository,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )
    work_unit = prepared.work_unit
    revision = prepared.revision
    export_period = prepared.period
    schema_provider = prepared.schema_provider
    iva_wallet_provenance = prepared.iva_wallet_provenance
    prior_domiciliation_provenance = prepared.prior_domiciliation_election
    amendment_evidence = prepared.amendment_evidence

    now = clock or _utc_now()
    export_period, approved = _approve_export_draft(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        actor=command.actor,
        approved_at=now,
        period=export_period,
        schema_provider=schema_provider,
    )
    return _persist_exported_draft(
        command=command,
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=export_period,
        approved=approved,
        exported_at=now,
        iva_wallet_provenance=iva_wallet_provenance,
        prior_domiciliation_election=prior_domiciliation_provenance,
        amendment_evidence=amendment_evidence,
        bucket_event_repository=bv_repo,
        schema_provider=schema_provider,
    )


__all__ = [
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportEvidenceMissingError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportOutputPathError",
    "ModeloExportResult",
    "ModeloExportUnsupportedError",
    "ModeloIvaWalletDecisionProvenance",
    "_raise_if_ledger_export_evidence_missing",
    "export_modelo_revision",
    "iva_wallet_decision_export_provenance",
]
