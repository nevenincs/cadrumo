"""Modelo declaration export: write a verified-complete or filed calculation revision to a local AEAT-compatible file.

:func:`~cadrumo.application.modelo.export.export_modelo_revision` accepts a
:class:`~CalculationRevision` id, rebuilds and approves a
:class:`~domain.filing.schema.ModeloDraft` from the revision replay inputs,
then writes a fichero-BOE-formatted artefact to the operator-supplied output
path. A ``MODELO_EXPORTED`` event is appended to the
:class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`.

Export consumes the registry-authored fichero-BOE layouts through the filing
runtime schema provider; Python code owns orchestration and safety checks, while
the registry remains the authority for record fields, casillas, header keys, and
provenance. The service refuses non-exportable revision states, cross-bucket
targets, missing profile facts, unclean cross-period prerequisites, unmatched IVA
wallet decisions, missing ledger evidence, Modelo 193 settled prior-accrual rows
whose amounts no official source settles, and unusable output paths before the
operator-visible file is committed.

The service is local-only: it never contacts AEAT and never invokes
``require_live_read``. Export is fundamentally an offline operation
that produces a file the operator presents through sede.agenciatributaria.gob.es
themselves.

The CLI verb ``aeat app modelo export`` is a thin delegate over this
service.

See Also:
    :func:`~cadrumo.application.modelo.revision_replay_inputs.revision_filing_replay_inputs`:
        Reconstructs the filing inputs from the persisted revision.
    :func:`~cadrumo.application.filing.draft_construction.build_draft`:
        Builds the transient registry-backed draft that is exported.
    ``cadrumo.application.filing.export_draft``:
        Serializes the approved draft through registry export layouts.
    :func:`~cadrumo.application.modelo.verification_cross_period.require_cross_period_clean_state`:
        Rechecks cross-period filing prerequisites before writing the export.
    :func:`~cadrumo.application.modelo.result_disposition_resolution.resolve_modelo_result_disposition`:
        Determines the fichero declaration type and refund disposition.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime

from ...core.atomic_write import StagedPublication
from ...core.export_layout_format import ExportLayoutFormat
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.result_disposition import ResultDisposition
from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.applicability_modelo202 import derive_modelo_202_modality
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.filing.errors import FilingExportError
from ...domain.filing.schema import ModeloDraft
from ...domain.filing.software_identity import (
    AeatProductSoftwareIdentity,
)
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.errors import (
    ModeloError,
    ModeloExportError,
    ModeloExportPriorDomiciliationElectionRequiredError,
)
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.cross_period_models import CrossPeriodExpectedMemberSet
from ..calculations.m303_regimen_simplificado_annual_summary import (
    validate_m303_regimen_simplificado_annual_summary_target_revision,
)
from ..calculations.observations_repository import (
    PriorDomiciliationElectionProjection,
)
from ..filing.export import export_draft
from ..filing.export_verification import (
    DeclaracionExportResult,
    FilingExportConsumedResult,
    FilingExportPayloadConsumer,
    assert_export_artifact_matches_receipt,
)
from ..filing.producer_snapshot import (
    AmendmentEvidence,
    FilingProducerSnapshot,
)
from ..filing.runtime import RegistryModeloSubview, RegistrySchemaAccessor, build_runtime_schema_provider
from ._ledger_evidence_gate import deductible_iva_evidence_gap_transaction_ids
from ._required_binding_gate import (
    require_persisted_revision_required_bindings_resolved as _require_persisted_required_bindings_resolved,
)
from .action_errors import (
    CalculationRevisionNotFoundError,
    WorkUnitNotFoundError,
)
from .calculation_note_gate import require_work_unit_calculation_unblocked
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .export_accounts import (
    build_export_producer_snapshot,
    export_completeness_unverified,
    m303_nota_three_requires_refund_account,
    refund_account_country,
    require_domiciliation_before_cutoff,
    require_m360_solicitud_for_export,
    resolve_export_accounts,
    selected_account_reference,
)
from .export_amendment_evidence import resolve_persisted_amendment_export_evidence
from .export_contracts import (
    ModeloExportAccountReference,
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportEvidenceMissingError,
    ModeloExportNoActiveBucketError,
    ModeloExportResult,
    ModeloIvaWalletDecisionProvenance,
    PreparedModeloExport,
)
from .export_ports import ModeloExportPorts
from .export_preparation import (
    approve_export_draft,
    compose_export_dictionary_values,
    envelope_requires_product_identity,
    envelope_stamped_software_identity,
    export_sink,
    iva_wallet_decision_export_provenance,
    raise_if_export_layout_unsupported,
    raise_if_ledger_export_evidence_missing,
    require_exportable_revision_state,
    requireprior_domiciliation_marker_layout,
    resolve_work_unit_period,
)
from .filing_revision_persistence import require_filing_instance_evidence_for_work_unit
from .iva_wallet_gate import require_persisted_iva_compensation_decision_matches_revision
from .m123_count_authority_gate import Modelo123CountAuthorityStage, require_modelo_123_count_authority
from .m193_settled_row_gate import Modelo193SettledRowStage, require_modelo_193_settled_row_amount_authority
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_annual_summary_applies,
)
from .modelo_bucket_events import emit_modelo_bucket_event as _emit_bucket_event
from .preconditions import (
    build_modelo_precondition_failure,
)
from .prior_domiciliation import resolveprior_domiciliation_election
from .profile_export_binding import (
    taxpayer_identity_profile_facts,
)
from .result_disposition_resolution import resolve_modelo_result_disposition
from .verification_cross_period import cross_period_expected_member_sets_from_profile, require_cross_period_clean_state


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
    export_ports: ModeloExportPorts,
    schema_provider: RegistrySchemaAccessor,
    operation: PinnedAuthorityOperation,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    payload_consumer: FilingExportPayloadConsumer | None = None,
) -> ModeloExportResult:
    m360_solicitud = require_m360_solicitud_for_export(command, work_unit=work_unit, export_ports=export_ports)
    accounts = resolve_export_accounts(
        command,
        work_unit=work_unit,
        export_ports=export_ports,
        exported_at=exported_at,
        m360_solicitud=m360_solicitud,
    )
    resolved_result_disposition = resolve_modelo_result_disposition(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        period=period,
        refund_election=command.refund_election,
        payment_election=command.payment_election,
        refund_account_country=refund_account_country(accounts.refund),
    )
    domiciliation_cutoff_unverified = require_domiciliation_before_cutoff(
        command,
        work_unit=work_unit,
        resolved_result_disposition=resolved_result_disposition,
        exported_at=exported_at,
        operation=operation,
    )
    producer_snapshot = build_export_producer_snapshot(
        command=command,
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        resolved_result_disposition=resolved_result_disposition,
        prior_domiciliation_election=prior_domiciliation_election,
        amendment_evidence=amendment_evidence,
        accounts=accounts,
        m360_solicitud=m360_solicitud,
        export_ports=export_ports,
        operation=operation,
    )
    selected_account = selected_account_reference(producer_snapshot, accounts=accounts)
    export_subview = schema_provider.get_subview(str(work_unit.modelo))
    export_layout = export_subview.export_layouts[0] if export_subview.export_layouts else None
    software_identity = envelope_stamped_software_identity(
        export_layout,
        product_software_identity=export_ports.product_software_identity,
    )
    dictionary_values = _dictionary_values_for_export(
        approved,
        producer_snapshot,
        work_unit,
        operation,
        export_subview,
        export_layout,
    )
    receipt: DeclaracionExportResult | FilingExportConsumedResult
    if payload_consumer is not None:
        receipt = _consume_export_payload(
            payload_consumer=payload_consumer,
            command=command,
            approved=approved,
            producer_snapshot=producer_snapshot,
            dictionary_values=dictionary_values,
            prior_domiciliation_election=prior_domiciliation_election.election,
            product_software_identity=software_identity if envelope_requires_product_identity(export_layout) else None,
            schema_provider=schema_provider,
        )
        event = _emit_export_event(
            command=command,
            work_unit=work_unit,
            receipt=receipt,
            iva_wallet_provenance=iva_wallet_provenance,
            resolved_result_disposition=resolved_result_disposition,
            prior_domiciliation_election=prior_domiciliation_election,
            selected_account=selected_account,
            exported_at=exported_at,
            bucket_event_repository=export_ports.bucket_event,
        )
    else:
        sink = export_sink(command)
        with sink.staged() as staged:
            receipt = _write_export_staging(
                staged=staged,
                command=command,
                approved=approved,
                producer_snapshot=producer_snapshot,
                dictionary_values=dictionary_values,
                prior_domiciliation_election=prior_domiciliation_election.election,
                product_software_identity=software_identity
                if envelope_requires_product_identity(export_layout)
                else None,
                schema_provider=schema_provider,
                mutation_writer=mutation_writer,
            )
            event = _emit_export_event(
                command=command,
                work_unit=work_unit,
                receipt=receipt,
                iva_wallet_provenance=iva_wallet_provenance,
                resolved_result_disposition=resolved_result_disposition,
                prior_domiciliation_election=prior_domiciliation_election,
                selected_account=selected_account,
                exported_at=exported_at,
                bucket_event_repository=export_ports.bucket_event,
            )
            if mutation_writer is None:
                sink.publish(staged)
            else:
                mutation_writer(lambda: sink.publish(staged))

        assert_export_artifact_matches_receipt(receipt, artifact_path=command.output_path)

    return _export_result(
        command=command,
        work_unit=work_unit,
        period=period,
        receipt=receipt,
        event=event,
        resolved_result_disposition=resolved_result_disposition,
        prior_domiciliation_election=prior_domiciliation_election,
        selected_account=selected_account,
        exported_at=exported_at,
        iva_wallet_provenance=iva_wallet_provenance,
        software_identity=software_identity,
        domiciliation_cutoff_unverified=domiciliation_cutoff_unverified,
        schema_provider=schema_provider,
    )


def _dictionary_values_for_export(
    approved: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    export_subview: RegistryModeloSubview,
    export_layout: ExportLayoutDefinition | None,
) -> dict[str, object] | None:
    return (
        compose_export_dictionary_values(
            draft=approved,
            taxpayer_identity=producer_snapshot.taxpayer_identity,
            bucket_id=work_unit.bucket_id,
            operation=operation,
            profile_export_bindings=export_subview.profile_export_bindings,
        )
        if export_layout is not None and export_layout.format is ExportLayoutFormat.XML_DICTIONARY
        else None
    )


def _export_result(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    period: Period,
    receipt: DeclaracionExportResult | FilingExportConsumedResult,
    event: BucketEvent,
    resolved_result_disposition: ResultDisposition | None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    selected_account: ModeloExportAccountReference | None,
    exported_at: datetime,
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None,
    software_identity: AeatProductSoftwareIdentity | None,
    domiciliation_cutoff_unverified: bool,
    schema_provider: RegistrySchemaAccessor,
) -> ModeloExportResult:
    # Coverage honesty: a fixed-width fichero-BOE whose revision declares no
    # completeness manifest cannot be structural-parity-verified (the pre-write
    # gate in export_draft only runs when a manifest is present), so surface a
    # non-blocking advisory rather than implying the export was verified.
    completeness_unverified = export_completeness_unverified(work_unit, schema_provider)

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
        selected_account=selected_account,
        casilla_provenance=receipt.casilla_provenance,
        iva_wallet_decision_provenance=iva_wallet_provenance,
        software_identity_grade=None if software_identity is None else software_identity.grade,
        domiciliation_cutoff_unverified=domiciliation_cutoff_unverified,
        completeness_unverified=completeness_unverified,
    )


def _write_export_staging(
    *,
    staged: StagedPublication,
    command: ModeloExportCommand,
    approved: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
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
            mutation_writer=mutation_writer,
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
            context=_export_write_failure_context(command, exc),
        ) from exc


def _consume_export_payload(
    *,
    payload_consumer: FilingExportPayloadConsumer,
    command: ModeloExportCommand,
    approved: ModeloDraft,
    producer_snapshot: FilingProducerSnapshot,
    dictionary_values: Mapping[str, object] | None,
    prior_domiciliation_election: PriorDomiciliationElection,
    product_software_identity: AeatProductSoftwareIdentity | None,
    schema_provider: RegistrySchemaAccessor,
) -> FilingExportConsumedResult:
    try:
        return export_draft(
            approved,
            payload_consumer=payload_consumer,
            producer_snapshot=producer_snapshot,
            dictionary_values=dictionary_values,
            prior_domiciliation_election=prior_domiciliation_election,
            product_software_identity=product_software_identity,
            schema_provider=schema_provider,
        )
    except FilingExportError as exc:
        raise ModeloExportError(
            translated_message="application.modelo.errors.export_draft_write_failed",
            context=_export_write_failure_context(command, exc),
        ) from exc


def _export_write_failure_context(command: ModeloExportCommand, exc: FilingExportError) -> dict[str, object]:
    """Name what the operator must supply when the refusal is a missing identity fact.

    The layout refuses a blank required field by its producer key, which is a
    registry spelling the operator never sees; the profile fact it is read from
    is what they declare. Any other export failure keeps its own cause.
    """
    missing_producer_key = (exc.context or {}).get("missing_producer_key")
    profile_facts = (
        taxpayer_identity_profile_facts(missing_producer_key) if isinstance(missing_producer_key, str) else ()
    )
    if not profile_facts:
        return {"calculation_revision_id": command.calculation_revision_id, "cause": str(exc)}
    named = " or ".join(profile_facts)
    return {
        "calculation_revision_id": command.calculation_revision_id,
        "cause": f"the export requires the profile fact {named}, which is not set",
        "missing_profile_facts": list(profile_facts),
    }


def _emit_export_event(
    *,
    command: ModeloExportCommand,
    work_unit: WorkUnit,
    receipt: DeclaracionExportResult | FilingExportConsumedResult,
    iva_wallet_provenance: ModeloIvaWalletDecisionProvenance | None,
    resolved_result_disposition: ResultDisposition | None,
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
    selected_account: ModeloExportAccountReference | None,
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
    }
    if resolved_result_disposition is not None:
        event_payload["resolved_result_disposition"] = resolved_result_disposition.value
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
    if selected_account is not None:
        # The role and the opaque register id only: account material never
        # reaches the event catalogue.
        event_payload["selected_account_role"] = selected_account.role.value
        if selected_account.own_account_id is not None:
            event_payload["selected_own_account_id"] = selected_account.own_account_id
    _append_prior_domiciliation_event(event_payload, prior_domiciliation_election)
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


def _append_prior_domiciliation_event(
    event_payload: dict[str, str],
    prior_domiciliation_election: PriorDomiciliationElectionProjection,
) -> None:
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


def _raise_if_deductible_iva_evidence_missing(
    revision: CalculationRevision,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse legacy revisions whose deductible IVA evidence is incomplete."""
    deductible_gap_transaction_ids = deductible_iva_evidence_gap_transaction_ids(revision, operation=operation)
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


def load_exportable_revision_target(
    calculation_revision_id: CalculationRevisionId,
    *,
    active_bucket_id: str,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationRevision, WorkUnit]:
    """Resolve the revision an export addresses together with its work unit.

    The lookup every modelo export destination shares: the revision must exist,
    its registry coordinates must still resolve under the caller's pinned
    authority generation, its work unit must exist and carry the filing-instance
    evidence its lifecycle requires, and that work unit must live in the active
    bucket. A destination that repeated any of these would be free to admit a
    revision the fichero-BOE refuses.

    Raises:
        CalculationRevisionNotFoundError: No revision carries that id.
        WorkUnitNotFoundError: The revision names a work unit that is absent.
        ModeloExportError: The work unit lacks required filing-instance evidence.
        ModeloExportCrossBucketRefusedError: The work unit belongs to another
            bucket than the active one.
    """
    revision = export_ports.calculation.load(operation=operation).get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    require_calculation_revision_coordinates_current(revision, operation=operation)
    work_unit = export_ports.work_unit.load().get(revision.work_unit_id)
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
                "calculation_revision_id": calculation_revision_id,
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
    operation: PinnedAuthorityOperation,
) -> tuple[Period, RegistrySchemaAccessor]:
    period = resolve_work_unit_period(work_unit)
    schema_provider = build_runtime_schema_provider(
        filing_year=period.filing_year,
        period=period,
        modelos=(work_unit.modelo,),
    )
    raise_if_export_layout_unsupported(work_unit=work_unit, schema_provider=schema_provider)
    from .profile_readiness_gate import require_profile_ready_for_work_unit

    require_profile_ready_for_work_unit(
        work_unit,
        profile_decode_context=operation.profile_decode_context(),
        operation=operation,
    )
    _require_persisted_required_bindings_resolved(
        work_unit=work_unit,
        revision=revision,
        action="export",
        operation=operation,
    )
    require_work_unit_calculation_unblocked(
        work_unit=work_unit, revision=revision, action="export", operation=operation
    )
    return period, schema_provider


def _require_modelo_export_clean_state(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    workflow_profile: TaxpayerProfile,
    iva_wallet_decision: IvaCompensationReconciliationDecision | None,
    export_ports: ModeloExportPorts,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
) -> None:
    require_cross_period_clean_state(
        work_unit,
        observation_repository=export_ports.observation,
        filing_repository=export_ports.filing,
        calculation_repository=export_ports.calculation,
        verification_repository=export_ports.verification,
        justificante_repository=export_ports.justificante,
        iva_compensation_decision=iva_wallet_decision,
        expected_member_sets=cross_period_expected_member_sets_from_profile(
            workflow_profile,
            cross_period_expected_member_sets,
        ),
        taxpayer_tax_id=workflow_profile.tax_id,
        activity_start_date=workflow_profile.activity_start_date,
        modelo_202_modality=derive_modelo_202_modality(
            workflow_profile,
            effective_date=date(work_unit.filing_year, 12, 31),
        ).modality,
        taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
        workflow_profile=workflow_profile,
        target_revision=revision,
    )


def _resolve_modelo_exportprior_domiciliation(
    command: ModeloExportCommand,
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    amendment_evidence: AmendmentEvidence | None,
    schema_provider: RegistrySchemaAccessor,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> PriorDomiciliationElectionProjection:
    """Resolve the page-3 prior-domiciliation action, KEEP unless the filing must choose.

    KEEP is the neutral value: it leaves the marker blank and changes nothing
    AEAT holds. Only a Modelo 303 rectificativa stating the rectified amount makes the
    choice consequential -- KEEP puts the refund account on the DID page under
    Nota 3, CANCEL_OR_MODIFY does not -- so that filing alone must state it.
    """
    if command.prior_domiciliation_election is None and m303_nota_three_requires_refund_account(
        work_unit, revision, PriorDomiciliationElection.KEEP, amendment_evidence, operation=operation
    ):
        raise ModeloExportPriorDomiciliationElectionRequiredError(
            "a Modelo 303 rectificativa stating the rectified amount requires an explicit prior-domiciliation election",
            context={"calculation_revision_id": command.calculation_revision_id, "modelo": str(work_unit.modelo)},
        )
    prior_domiciliation_election = resolveprior_domiciliation_election(
        election=command.prior_domiciliation_election or PriorDomiciliationElection.KEEP,
        work_unit=work_unit,
        revision=revision,
        filing_repository=export_ports.filing,
        observation_repository=export_ports.observation,
        operation=operation,
    )
    requireprior_domiciliation_marker_layout(
        work_unit=work_unit,
        prior_domiciliation_election=prior_domiciliation_election,
        schema_provider=schema_provider,
    )
    return prior_domiciliation_election


def _prepare_modelo_export(
    command: ModeloExportCommand,
    *,
    evaluated_at: datetime,
    active_bucket_id: str,
    workflow_profile: TaxpayerProfile,
    export_ports: ModeloExportPorts,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet],
    operation: PinnedAuthorityOperation,
) -> PreparedModeloExport:
    """Load and validate every persisted authority required before export bytes."""
    revision, work_unit = load_exportable_revision_target(
        command.calculation_revision_id,
        active_bucket_id=active_bucket_id,
        export_ports=export_ports,
        operation=operation,
    )
    require_modelo_123_count_authority(
        work_unit,
        retencion_ports=export_ports.retencion_observation_ports,
        stage=Modelo123CountAuthorityStage.EXPORT,
    )
    require_modelo_193_settled_row_amount_authority(work_unit, revision, stage=Modelo193SettledRowStage.EXPORT)
    amendment_evidence = resolve_persisted_amendment_export_evidence(
        command,
        revision,
        work_unit=work_unit,
        workflow_profile=workflow_profile,
        work_unit_repository=export_ports.work_unit,
        filing_repository=export_ports.filing,
        justificante_repository=export_ports.justificante,
    )
    require_exportable_revision_state(revision)
    # A handoff whose filed source was replaced makes the revision a statement
    # about superseded facts, so it is refused before anything judges that
    # revision's own evidence -- the order verification and filing keep too.
    validate_m303_regimen_simplificado_annual_summary_target_revision(
        target_work_unit=work_unit,
        target_revision=revision,
        work_unit_repository=export_ports.work_unit,
        calculation_repository=export_ports.calculation,
        filing_repository=export_ports.filing,
        regimen_simplificado_applies=m303_regimen_simplificado_annual_summary_applies(work_unit),
        operation=operation,
    )
    raise_if_ledger_export_evidence_missing(revision)
    _raise_if_deductible_iva_evidence_missing(revision, operation=operation)
    period, schema_provider = _prepare_modelo_export_schema(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        operation=operation,
    )
    iva_wallet_decision = require_persisted_iva_compensation_decision_matches_revision(
        work_unit,
        revision,
        repository=export_ports.iva_compensation_decision,
        observation_repository=export_ports.observation,
        history_repository=export_ports.iva_compensation_history,
        operation=operation,
        evaluated_at=evaluated_at,
    )
    _require_modelo_export_clean_state(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        iva_wallet_decision=iva_wallet_decision,
        export_ports=export_ports,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
    )
    prior_domiciliation_election = _resolve_modelo_exportprior_domiciliation(
        command,
        work_unit=work_unit,
        revision=revision,
        amendment_evidence=amendment_evidence,
        schema_provider=schema_provider,
        export_ports=export_ports,
        operation=operation,
    )
    return PreparedModeloExport(
        work_unit=work_unit,
        revision=revision,
        period=period,
        schema_provider=schema_provider,
        iva_wallet_provenance=iva_wallet_decision_export_provenance(iva_wallet_decision),
        prior_domiciliation_election=prior_domiciliation_election,
        amendment_evidence=amendment_evidence,
    )


def export_modelo_revision(
    command: ModeloExportCommand,
    *,
    workflow_profile: TaxpayerProfile,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
    cross_period_expected_member_sets: Iterable[CrossPeriodExpectedMemberSet] = (),
    clock: datetime | None = None,
    mutation_writer: Callable[[Callable[[], None]], None] | None = None,
    payload_consumer: FilingExportPayloadConsumer | None = None,
) -> ModeloExportResult:
    """Export a verified-complete or filed calculation revision to disk.

    ``workflow_profile`` is the
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile` used to compose the filing
    draft headers and to replay profile-applicability relation inputs.

    Local-only: never contacts AEAT. Re-builds the filing draft from
    :func:`~cadrumo.application.modelo.revision_replay_inputs.revision_filing_replay_inputs`
    so the exported file reflects the same legal casilla and relation map that
    would be filed.

    The revision must be ``VERIFICADO_COMPLETO``, ``PRESENTADO``, or
    ``PRESENTADO_SUPERSEDIDO`` and must belong to the active bucket. Before
    writing any operator-visible file, the service validates the output path,
    export-layout renderability, profile readiness, ledger evidence, IVA wallet
    decision provenance, and cross-period clean state. It then rebuilds and
    approves a transient :class:`~domain.filing.schema.ModeloDraft`, builds one typed
    filing producer snapshot, serializes through
    ``cadrumo.application.filing.export_draft``, appends ``MODELO_EXPORTED`` to
    the bucket-event-history catalogue, and finally publishes the staged
    artefact onto the operator's path. Any write, event, or publication failure
    discards the staged cleartext artefact before raising.

    When ``payload_consumer`` is supplied the validated fichero bytes are handed
    to it in memory instead and no file is written: ``command.output_path``
    then names the artefact the caller publishes those bytes inside, and the
    ``MODELO_EXPORTED`` event records it with the digest of the fichero bytes.

    Returns:
        :class:`~cadrumo.application.modelo.export_contracts.ModeloExportResult`: The export
        receipt, including byte size, digest, event id, casilla provenance, and
        any redacted IVA wallet decision provenance.

    See Also:
        :class:`~cadrumo.application.modelo.export_contracts.ModeloExportCommand`:
            Strict input envelope for the revision id, output path, actor, and
            refund election.
        :func:`~cadrumo.application.filing.producer_snapshot.build_filing_producer_snapshot`:
            Builds the sole typed producer boundary consumed by the renderer.
        :meth:`~cadrumo.application.modelo.export_sink.LocalFileExportSink.require_writable`:
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
    if payload_consumer is None:
        export_sink(command).require_writable()

    now = clock or _utc_now()
    prepared = _prepare_modelo_export(
        command,
        active_bucket_id=active_bucket_id,
        workflow_profile=workflow_profile,
        export_ports=export_ports,
        cross_period_expected_member_sets=cross_period_expected_member_sets,
        operation=operation,
        evaluated_at=now,
    )
    work_unit = prepared.work_unit
    revision = prepared.revision
    export_period = prepared.period
    schema_provider = prepared.schema_provider
    iva_wallet_provenance = prepared.iva_wallet_provenance
    prior_domiciliation_provenance = prepared.prior_domiciliation_election
    amendment_evidence = prepared.amendment_evidence

    export_period, approved = approve_export_draft(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=workflow_profile,
        actor=command.actor,
        approved_at=now,
        period=export_period,
        schema_provider=schema_provider,
        ports=export_ports.draft_review_ports,
        operation=operation,
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
        export_ports=export_ports,
        schema_provider=schema_provider,
        operation=operation,
        mutation_writer=mutation_writer,
        payload_consumer=payload_consumer,
    )
