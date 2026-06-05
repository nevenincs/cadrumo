"""Modelo work-unit lifecycle actions.

Each action loads the catalogue, applies a single mutation in
memory (or returns a read view), and writes the catalogue back.
The catalogue is content-addressed by ``work_unit_id`` so
deterministic derivation lets ``create_work_unit`` be idempotent:
calling it twice with the same four-axis key returns the same
record without producing a duplicate.

The action signatures take an explicit ``bucket_id`` so the
service layer is unit-testable without a workflow-state fixture.

Actions obtain a :class:`RegistrySnapshot` for the target revision from a
:class:`ValidatedRegistryAuthority`, then feed :class:`ModeloRevision` data
into the formula engine to produce or amend a calculation revision. Invoice
evidence is loaded from an :class:`InvoiceCatalogueRepository` when the
revision's source mesh includes invoice-backed bindings, and the
:class:`TransactionCatalogue` is consumed by the ledger aggregation step.
Ledger transactions are loaded via :class:`TransactionCatalogueRepository`.
Every mutating action emits a typed event to :class:`BucketEventHistoryRepository`.
The deadline window is derived from a :class:`TaxpayerProfile` when the
modelo has an obligation schedule.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.i18n import tr
from ...core.time import now as _utc_now
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import (
    ModeloRecordCatalogueRepository,
    upsert_filing_record,
)
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import (
    WorkUnitCatalogueRepository,
    upsert_work_unit,
)
from ...domain.modelos._work_unit import (
    WorkUnitState,
)
from ..workflow import (
    WorkflowInputMismatchError as WorkflowInputMismatchError,
)
from . import _iva_wallet_gate
from . import _m210_rate as _m210_rate
from ._action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRegistryUnavailableError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    CasillaProvenanceMissingError,
    ExternalModeloImportError,
    ModeloAggregationBindingError,
    ModeloApplicabilityFilterError,
    ModeloCrossPeriodCleanStateError,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    StoredCalculationDriftError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ._calculation_actions import (
    _IVA_LEDGER_EXEMPT_REGIMES as _IVA_LEDGER_EXEMPT_REGIMES,
)
from ._calculation_actions import (
    _iva_wallet_blocked_message as _iva_wallet_blocked_message,
)
from ._calculation_actions import (
    _raise_if_ledger_preflight_blocks_calculation as _raise_if_ledger_preflight_blocks_calculation,
)
from ._calculation_actions import (
    _reject_caller_overrides_of_source_bindings as _reject_caller_overrides_of_source_bindings,
)
from ._calculation_actions import (
    calculate_modelo_revision as calculate_modelo_revision,
)
from ._calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation as calculate_modelo_revision_from_bucket_aggregation,
)
from ._calculation_actions import (
    get_calculation_revision as get_calculation_revision,
)
from ._calculation_actions import (
    list_calculation_revisions as list_calculation_revisions,
)
from ._calculation_actions import (
    mark_revision_verificado_completo as mark_revision_verificado_completo,
)
from ._calculation_helpers import (
    amendment_observations as _amendment_observations,
)
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_helpers import (
    external_filing_observations as _external_filing_observations,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._filing_actions import (
    file_modelo_revision as file_modelo_revision,
)
from ._filing_actions import (
    get_filing_record as get_filing_record,
)
from ._filing_actions import (
    get_verification_report as get_verification_report,
)
from ._filing_actions import (
    list_filing_records as list_filing_records,
)
from ._filing_actions import (
    list_verification_reports as list_verification_reports,
)
from ._registry_helpers import (
    assert_revision_content_integrity as _assert_revision_content_integrity,
)
from ._registry_helpers import (
    reject_incomplete_amendment_casillas as _reject_incomplete_amendment_casillas,
)
from ._registry_helpers import (
    reject_unknown_import_casillas as _reject_unknown_import_casillas,
)
from ._registry_helpers import (
    reject_unknown_override_casillas as _reject_unknown_override_casillas,
)
from ._revision_persistence import (
    emit_bucket_event as _emit_bucket_event,
)
from ._verification_actions import (
    _PREDICATE_ADVISORY_WHEN_RATIO_GE as _PREDICATE_ADVISORY_WHEN_RATIO_GE,
)
from ._verification_actions import (
    _PREDICATE_ALL_NONZERO as _PREDICATE_ALL_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_ANY_NONZERO as _PREDICATE_ANY_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_CAP_LE_WHEN_POSITIVE as _PREDICATE_CAP_LE_WHEN_POSITIVE,
)
from ._verification_actions import (
    _PREDICATE_IMPLIES_NONZERO as _PREDICATE_IMPLIES_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_PROFILE_FIELD_REQUIRED as _PREDICATE_PROFILE_FIELD_REQUIRED,
)
from ._verification_actions import (
    _collect_revision_verification_findings as _collect_revision_verification_findings,
)
from ._verification_actions import (
    _cross_period_clean_state_next_action as _cross_period_clean_state_next_action,
)
from ._verification_actions import (
    _dt12_reduccion_advisory_finding as _dt12_reduccion_advisory_finding,
)
from ._verification_actions import (
    _evaluate_advisory_predicate_fires as _evaluate_advisory_predicate_fires,
)
from ._verification_actions import (
    _evaluate_applicability_filter as _evaluate_applicability_filter,
)
from ._verification_actions import (
    _evaluate_predicate_expression as _evaluate_predicate_expression,
)
from ._verification_actions import (
    _evaluate_verification_predicates as _evaluate_verification_predicates,
)
from ._verification_actions import (
    _iva_wallet_blocking_verification_finding as _iva_wallet_blocking_verification_finding,
)
from ._verification_actions import (
    _missing_required_casilla_finding as _missing_required_casilla_finding,
)
from ._verification_actions import (
    _require_cross_period_clean_state as _require_cross_period_clean_state,
)
from ._verification_actions import (
    _rewrite_m210_sentinels as _rewrite_m210_sentinels,
)
from ._verification_actions import (
    verify_modelo_revision as verify_modelo_revision,
)
from ._work_lifecycle import (
    create_work_unit as create_work_unit,
)
from ._work_lifecycle import (
    discard_work_unit as discard_work_unit,
)
from ._work_lifecycle import (
    get_work_unit as get_work_unit,
)
from ._work_lifecycle import (
    list_work_units as list_work_units,
)
from ._work_lifecycle import (
    rename_work_unit as rename_work_unit,
)
from ._workflow_gate import (
    _RevisionInputsProvider as _RevisionInputsProvider,
)
from ._workflow_gate import (
    workflow_period_for_work_unit,
)

if TYPE_CHECKING:
    pass

ModeloIvaWalletReconciliationBlocked = _iva_wallet_gate.ModeloIvaWalletReconciliationBlocked
ModeloIvaWalletReconciliationBlockedError = _iva_wallet_gate.ModeloIvaWalletReconciliationBlockedError
_apply_iva_compensation_decision_binding = _iva_wallet_gate.apply_iva_compensation_decision_binding
_require_iva_compensation_revision_match = _iva_wallet_gate.require_persisted_iva_compensation_decision_matches_revision
_require_persisted_iva_compensation_decision_matches_revision = _require_iva_compensation_revision_match
_taxpayer_nif_for_bucket = _iva_wallet_gate.taxpayer_nif_for_bucket
iva_wallet_blocked_message = _iva_wallet_gate.iva_wallet_blocked_message
resolve_iva_compensation_decision_for_calculation = _iva_wallet_gate.resolve_iva_compensation_decision_for_calculation
_resolve_m210_rate = _m210_rate.resolve_m210_rate




def amend_modelo_revision(
    *,
    from_filing_record_id: str,
    overrides: Mapping[str, Decimal],
    amendment_kind: CalculationRevisionAmendmentKind,
    reason: str,
    actor: str,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Build and file an amendment over an externally-filed return.

    Pipeline:

    1. Load the baseline filing record (must exist, must be CURRENT,
       must carry ``external_evidence``). The evidence gate ensures
       the amendment runs against AEAT-attested imported data, not a
       fabricated local original.
    2. Load the baseline calculation revision; merge its
       ``casilla_values`` with the operator-supplied ``overrides``
       to produce the corrected casilla map.
    3. Persist a new ``DRAFT`` calculation revision carrying
       ``amendment_kind``, ``amends_filing_record_id``, and the
       operator-supplied ``reason``.
    4. Transition it through ``VERIFICADO_COMPLETO`` (the verification
       contract for amendments is identity-equivalent to the
       calculate path because the registry-snapshot resolver still
       applies; here we mark it verified-complete directly because
       the operator opts in by invoking the amend verb).
    5. Build a new filing record with
       ``amends_filing_record_id = baseline.filing_record_id`` and
       status CURRENT; supersede the baseline record.
    6. Emit a ``modelo.amended`` bucket event linking the new
       filing record to the baseline.

    Args:
        from_filing_record_id: The id of the baseline filing record to amend.
            Must be CURRENT and carry ``external_evidence``.
        overrides: Casilla-id to Decimal mapping of corrected values to merge
            over the baseline revision's casilla map.
        amendment_kind: Whether the amendment is ``COMPLEMENTARIA`` or
            ``SUSTITUTIVA``.
        reason: Operator-supplied explanation for the amendment, recorded in
            the revision and bucket event.
        actor: Operator identifier recorded in the audit trail.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository override.
        bucket_event_repository: Optional bucket-event history repository
            override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status for the
        amendment.

    Raises:
        ModeloRecordNotFoundError: When ``from_filing_record_id`` is
            absent from the catalogue.
        AmendmentEvidenceMissingError: When the baseline record does
            not carry ``external_evidence``.
        AmendmentTargetStateError: When the baseline record is not
            in ``CURRENT`` status.
        WorkUnitNotFoundError: When the work unit referenced by the
            baseline record cannot be loaded.
        CalculationRevisionNotFoundError: When the baseline calculation
            revision referenced by the filing record is absent.
        CalculationRevisionStateError: When the amendment overrides
            produce a duplicate revision id already present in the catalogue.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    filing_catalogue = fr_repo.load()
    baseline = filing_catalogue.get(from_filing_record_id)
    if baseline is None:
        raise ModeloRecordNotFoundError(
            translated_message="application.modelo.errors.filing_record_not_found",
            context={"filing_record_id": from_filing_record_id},
        )
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            f"filing record {from_filing_record_id!r} has no external_evidence; the "
            f"modelo amend path requires an imported AEAT-attested baseline. Use the "
            f"standard re-file path (calculate → verify → file) for locally-filed returns."
        )
    if baseline.status is not ModeloRecordStatus.VIGENTE:
        raise AmendmentTargetStateError(
            f"filing record {from_filing_record_id!r} is in status {baseline.status.value!r}; "
            f"only CURRENT filings can be amended"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(baseline.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"filing record {from_filing_record_id!r} references missing work_unit_id={baseline.work_unit_id!r}"
        )

    revisions = cr_repo.load()
    baseline_revision = revisions.get(baseline.calculation_revision_id)
    if baseline_revision is None:
        raise CalculationRevisionNotFoundError(
            f"baseline calculation revision {baseline.calculation_revision_id!r} is missing from the catalogue"
        )

    _reject_unknown_override_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        overrides=overrides,
    )

    now = clock or _utc_now()
    corrected_values: dict[str, Decimal] = dict(baseline_revision.casilla_values)
    corrected_values.update(overrides)

    new_revision_id = derive_calculation_revision_id(
        work_unit_id=baseline.work_unit_id,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        casilla_values=corrected_values,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
    )
    if new_revision_id in revisions:
        raise CalculationRevisionStateError(
            f"amendment overrides produce calculation_revision_id {new_revision_id!r} "
            f"that already exists in the catalogue; no-op overrides cannot be filed as amendments"
        )

    # Carry regulatory grounding onto the amendment: build typed
    # CasillaObservation rows for the corrected casilla map so the
    # persisted amendment revision and its CLI emit preserve
    # legal_refs / source_refs (and baseline formula provenance for
    # non-overridden casillas) instead of an empty observations tuple.
    amendment_observations = _amendment_observations(
        corrected_values=corrected_values,
        overrides=overrides,
        baseline_revision=baseline_revision,
        snapshot=_resolve_registry_snapshot_for_work_unit(work_unit),
    )

    amendment_draft = CalculationRevision(
        calculation_revision_id=new_revision_id,
        work_unit_id=baseline.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot=baseline_revision.inputs_snapshot,
        binding_overrides=baseline_revision.binding_overrides,
        source_transaction_ids=baseline_revision.source_transaction_ids,
        borrador_snapshot_id=baseline_revision.borrador_snapshot_id,
        bindings_sourced_from_borrador=baseline_revision.bindings_sourced_from_borrador,
        casilla_values=corrected_values,
        observations=amendment_observations,
        created_at=now,
        updated_at=now,
        amendment_kind=amendment_kind,
        amends_filing_record_id=baseline.filing_record_id,
        amendment_reason=reason.strip(),
    )
    revisions = upsert_calculation_revision(revisions, amendment_draft)

    # Verify the corrected casilla map against the registry's
    # required-manual-input contract before transitioning. The amend
    # path mirrors the standard verify gate so a complementaria
    # cannot be filed with a missing required casilla.
    _reject_incomplete_amendment_casillas(
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        casilla_values=corrected_values,
    )

    # Transition draft → verified-complete (operator opts in by calling amend).
    verified_amendment = amendment_draft.model_copy(
        update={
            "state": CalculationRevisionState.VERIFICADO_COMPLETO,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, verified_amendment)

    new_filing_id = derive_filing_record_id(
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=new_revision_id,
        bucket_id=baseline.bucket_id,
        modelo=baseline.modelo,
        filing_year=baseline.filing_year,
        period=baseline.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=None,
        amends_filing_record_id=baseline.filing_record_id,
    )

    superseded_baseline = baseline.model_copy(
        update={
            "status": ModeloRecordStatus.SUPERSEDIDO,
            "superseded_at": now,
            "superseded_by_filing_record_id": new_filing_id,
        }
    )
    updated_filing_catalogue = upsert_filing_record(filing_catalogue, superseded_baseline)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    filed_amendment = verified_amendment.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, filed_amendment)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": new_revision_id,
                    "filed_calculation_revision_id": new_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=baseline.bucket_id,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "amends_filing_record_id": baseline.filing_record_id,
            "calculation_revision_id": new_revision_id,
            "work_unit_id": baseline.work_unit_id,
            "modelo": str(baseline.modelo),
            "filing_year": str(baseline.filing_year),
            "period": baseline.period,
            "amendment_kind": amendment_kind.value,
            "override_count": str(len(overrides)),
        },
    )

    return new_filing


def import_external_filing_evidence(
    *,
    work_unit_id: str,
    casilla_values: Mapping[str, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> ModeloRecord:
    """Persist an externally-filed return as a baseline filing record.

    This is the canonical entry point the import path (justificante
    PDF reader, AEAT CSV register importer, AEAT live capture) uses
    to land an externally-filed return as the bucket's baseline:

    1. Verify the work unit exists and is not discarded.
    2. Persist a fresh ``FILED`` calculation revision carrying the
       imported casilla values (no inputs / overrides — the operator
       did not compute this locally; AEAT's records are the source
       of truth).
    3. Build a ``CURRENT`` filing record with ``external_evidence``
       populated and ``aeat_accepted=True``.
    4. If a prior current filing exists for the (bucket, modelo,
       year, period) tuple, supersede it (same supersession chain
       the file path uses).
    5. Advance the work-unit pointers to the imported baseline.
    6. Emit a ``modelo.filing.imported`` bucket event linking the
       new filing record id to the evidence reference.

    The amend path consumes records produced here as its baseline.

    Args:
        work_unit_id: The stable id of the work unit to attach the imported
            filing to.
        casilla_values: The AEAT-attested casilla values from the imported
            filing. Must be non-empty.
        evidence_kind: The kind of external evidence being imported (e.g.
            justificante, borrador).
        evidence_reference_id: The AEAT-issued reference identifier for the
            imported filing. Must be non-blank after stripping.
        actor: Operator identifier recorded in the audit trail. Defaults to
            ``"aeat-import"``.
        work_unit_repository: Optional work-unit catalogue repository override.
        calculation_repository: Optional calculation-revision catalogue
            repository override.
        filing_repository: Optional filing-record catalogue repository override.
        bucket_event_repository: Optional bucket-event history repository
            override.
        clock: Optional UTC timestamp override.

    Returns:
        The newly created :class:`ModeloRecord` in ``CURRENT`` status.

    Raises:
        WorkUnitNotFoundError: when ``work_unit_id`` is absent.
        WorkUnitMutationRefusedError: when the work unit is discarded.
        ExternalModeloImportError: when ``casilla_values`` is empty,
            ``evidence_reference_id`` is blank, or the derived revision id
            already exists in the catalogue.
    """
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or ModeloRecordCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()

    if not casilla_values:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_no_casilla_values",
        )
    cleaned_reference = evidence_reference_id.strip()
    if not cleaned_reference:
        raise ExternalModeloImportError(
            translated_message="application.modelo.errors.external_filing_evidence_reference_blank",
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if work_unit.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            translated_message="application.modelo.errors.work_unit_discarded_cannot_import",
            context={"work_unit_id": work_unit_id},
        )

    snapshot = _reject_unknown_import_casillas(
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        casilla_values=casilla_values,
    )

    inputs_snapshot: dict[str, str] = {}
    binding_overrides: dict[str, str] = {}
    outputs = dict(casilla_values)
    observations = _external_filing_observations(casilla_values=outputs, snapshot=snapshot)

    now = clock or _utc_now()
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    if revision_id in revisions:
        raise ExternalModeloImportError(
            tr(
                "application.modelo.errors.external_import_duplicate_revision",
                calculation_revision_id=revision_id,
            ),
            translated_message="application.modelo.errors.external_import_duplicate_revision",
            context={"calculation_revision_id": revision_id},
        )

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.PRESENTADO,
        inputs_snapshot=inputs_snapshot,
        binding_overrides=binding_overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by=actor.strip(),
        filed_at=now,
        filed_by=actor.strip(),
        observations=observations,
    )
    revisions = upsert_calculation_revision(revisions, revision)

    new_filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=None,
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=evidence_kind,
            reference_id=cleaned_reference,
            imported_at=now,
        ),
    )

    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)

    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "filed_calculation_revision_id": revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILING_IMPORTED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "work_unit_id": work_unit_id,
            "calculation_revision_id": revision_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period,
            "evidence_kind": evidence_kind.value,
            "evidence_reference_id": cleaned_reference,
            "supersedes_filing_record_id": (prior_current.filing_record_id if prior_current is not None else ""),
            "casilla_count": str(len(outputs)),
        },
    )

    return new_filing


__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloCrossPeriodCleanStateError",
    "ModeloError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "StoredCalculationDriftError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "_assert_revision_content_integrity",
    "_build_typed_observations",
    "amend_modelo_revision",
    "calculate_modelo_revision",
    "calculate_modelo_revision_from_bucket_aggregation",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "import_external_filing_evidence",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verificado_completo",
    "rename_work_unit",
    "verify_modelo_revision",
    "workflow_period_for_work_unit",
]
