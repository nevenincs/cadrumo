"""Register modelo lifecycle operations using their canonical writers and public contracts."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.hex_ids import WorkUnitId
from ...core.logging import get_logger
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
)
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import (
    OperationTerminalReceipt,
    require_succeeded_receipt_references,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from ._edit_execution import apply_modelo_edit
from .action_errors import (
    CalculationRevisionNotFoundError,
    M303FilingEvidenceError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    modelo_edit_refusal_error,
)
from .amendment_action_ports import AmendmentActionPortsFactory
from .amendment_actions import amend_modelo_revision
from .amendment_projection import ModeloWorkAmendPublicResultV2
from .calculation_action_ports import CalculationActionPortsFactory
from .calculation_advisory_projection import ModeloCalculationAdvisories
from .calculation_projection import ModeloCalculationSnapshot
from .calculation_report_export import (
    ModeloCalculationReportCommand,
    ModeloCalculationReportResult,
    export_modelo_calculation_report,
)
from .edit_apply_contracts import ModeloEditApplyOperationRequestV1, ModeloEditApplyPublicResultV1
from .edit_baseline_projection import ModeloEditApplyBaselineV1
from .edit_models import (
    ModeloEditApplyRequestV1,
    ModeloEditDomainRefusalV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionResultV1,
    ModeloEditRefusalV1,
    ModeloEditScalarAddressV1,
)
from .edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from .edit_refusal_projection import ModeloEditCalculationPrerequisiteV1, ModeloEditPrerequisiteObserver
from .export import ModeloExportCommand, ModeloExportResult, export_modelo_revision
from .export_ports import ModeloExportPorts, ModeloExportPortsFactory
from .export_projection import (
    ModeloCalculationReportPublicReceipt,
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
    ModeloFicheroBoePublicReceipt,
)
from .filing_action_ports import FilingActionPortsFactory
from .filing_actions import file_modelo_revision
from .filing_projection import ModeloFilingRecordSnapshot
from .lifecycle_advisories import ModeloLifecycleAdvisories, build_modelo_lifecycle_advisories
from .m303_filing_evidence import m303_filing_evidence_failure
from .m303_ordinary_filing_evidence_authoring import author_ordinary_m303_evidence_for_work
from .metadata_projection import ModeloWorkMetadataSnapshot
from .review_package_signing_ports import ReviewPackageSigningKeypairCapabilityFactory
from .verification_actions import verify_modelo_revision_with_preconditions
from .verification_projection import ModeloVerificationSnapshot
from .work_amend_contracts import ModeloWorkAmendRequest
from .work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from .work_change_contracts import (
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from .work_export_contracts import ModeloExportRequest, ModeloExportSettledResult
from .work_filing_contracts import ModeloWorkFilePublicResultV2, ModeloWorkFileRequest
from .work_lifecycle import discard_work_unit, get_work_unit, rename_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from .workspace_models import ModeloWorkspaceRefreshTargetV1

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
    from ...domain.modelos.filing_record import ModeloRecord
    from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
    from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..auth.operator_scope_ports import OperatorScopePorts
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext
    from .calculate_input import ModeloWorkCalculationServiceResult, WorkCalculateInputBundle
    from .calculation_action_ports import CalculationActionPorts
    from .calculation_summary_pdf_ports import CalculationSummaryPdfWriter
    from .verification_repository_ports import VerificationRepositoryBundleFactory


MODELO_WORK_RENAME_OPERATION_DEFINITION_ID = "modelo.work.rename"


MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID = "modelo.work.discard"


MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID = "modelo.work.calculate"


MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID = "modelo.work.verify"


MODELO_WORK_FILE_OPERATION_DEFINITION_ID = "modelo.work.file"


MODELO_EXPORT_OPERATION_DEFINITION_ID = "modelo.export"


MODELO_WORK_AMEND_OPERATION_DEFINITION_ID = "modelo.work.amend"


MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID = "modelo.edit.apply"


#: Suffix appended to a definition id to name that enrolment's refresh-target
#: schema. Every Modelo enrolment binds the SAME target model, but each needs
#: its own schema identity: the registry resolves a schema binding by scanning
#: every registration and taking the first identity match, so one id shared
#: across enrolments would stop that lookup being definition-scoped.
MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX = "workspace_refresh_target"


class _WorkUnitSubject(BaseModel):
    """Validate an operation subject reference as a real work-unit identifier."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId


def resolve_modelo_work_unit_refresh_target(
    terminal_receipt: OperationTerminalReceipt,
    /,
) -> ModeloWorkspaceRefreshTargetV1:
    """Derive the workspace read one settled Modelo work operation invalidates.

    Every definition below addresses one work unit, so the settled receipt's
    ``subject_ref`` is that unit's identifier. It is validated here rather
    than trusted: a subject that is not a well-formed
    :data:`~cadrumo.core.identity.hex_ids.WorkUnitId` raises, and the resolving
    service turns that into a typed refusal instead of handing a frontend a
    target it cannot read.
    """
    return ModeloWorkspaceRefreshTargetV1(
        work_unit_id=_WorkUnitSubject(work_unit_id=terminal_receipt.identity.subject_ref).work_unit_id,
    )


def _modelo_workspace_refresh_target_binding(definition_id: str) -> OperationSchemaBindingV1:
    """Bind one enrolment's refresh-target schema to the shared target model."""
    return OperationSchemaBindingV1.bind(
        schema_id=f"{definition_id}.{MODELO_WORKSPACE_REFRESH_TARGET_SCHEMA_SUFFIX}",
        schema_version=1,
        model_type=ModeloWorkspaceRefreshTargetV1,
    )


class ModeloWorkRenameExecutor:
    """Run the existing rename writer under one recorded operation identity."""

    def __init__(self, *, work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Bind the active-profile lifecycle authorities at the composition root."""
        self._work_lifecycle_ports_factory = work_lifecycle_ports_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkRenameRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the single writer and retain its typed encrypted result.

        The writer owns the atomic write set - the work-unit catalogue and the
        bucket lifecycle event co-commit inside it - so nothing here opens a
        second write path around them.

        The declared phase is published BEFORE delegating, because a phase
        marks entering a stage rather than finishing one: an observer watching
        this operation should see it start, not learn of it only once the
        write has already landed. Without this the definition advertises a
        phase no surface can ever show.
        """
        await context.events.phase(MODELO_WORK_RENAME_OPERATION_DEFINITION_ID)
        ports = self._work_lifecycle_ports_factory()

        def observed_unit() -> WorkUnit:
            unit = get_work_unit(request.payload.work_unit_id, ports=ports)
            if unit.name != request.payload.observed_name or unit.updated_at != request.payload.observed_updated_at:
                raise WorkUnitMutationRefusedError(
                    translated_message="errors.refused.modelo_work_rename_approval_stale",
                    context={"work_unit_id": request.payload.work_unit_id},
                )
            return unit

        current = await await_cancellation_complete(
            asyncio.to_thread(observed_unit), task_name="modelo-work-rename-observation"
        )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                renamed = await asyncio.to_thread(
                    rename_work_unit,
                    request.payload.work_unit_id,
                    request.payload.new_name,
                    actor=request.payload.actor,
                    ports=ports,
                    expected=current,
                )
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    ModeloWorkRenamePublicResultV2(
                        work_unit_id=renamed.work_unit_id,
                        name=renamed.name,
                        bucket_id=renamed.bucket_id,
                        unit=ModeloWorkMetadataSnapshot.from_work_unit(renamed),
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-rename-publication")


class ModeloWorkDiscardApprovalStaleError(CadrumoError):
    """Raised when the approved unit is no longer the unit on disk."""


def calculation_public_result(
    result: ModeloWorkCalculationServiceResult, *, operation: PinnedAuthorityOperation
) -> ModeloWorkCalculatePublicResultV2:
    """Project the exact canonical return without post-publication catalogue reads."""
    return ModeloWorkCalculatePublicResultV2(
        work_unit_id=result.work_unit.work_unit_id,
        calculation_revision_id=result.revision.calculation_revision_id,
        calculation=ModeloCalculationSnapshot.from_revision(
            result.revision, work_unit=result.work_unit, operation=operation
        ),
        advisories=ModeloCalculationAdvisories.from_result(result, operation=operation),
        unit=ModeloWorkMetadataSnapshot.from_work_unit(result.work_unit),
        revision_published=result.revision_published,
    )


@dataclass(frozen=True, slots=True)
class PreparedModeloWorkCalculation:
    """One admitted work unit with canonical inputs and calculation authorities."""

    work_unit: WorkUnit
    ports: CalculationActionPorts
    inputs: WorkCalculateInputBundle


async def prepare_modelo_work_calculation(
    payload: ModeloWorkCalculateRequest,
    *,
    operation: PinnedAuthorityOperation,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> PreparedModeloWorkCalculation:
    """Apply the ordinary admission, M303 evidence, and input-channel policy."""
    from ...core.bucket_pointer import require_active_bucket_id
    from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit

    active_bucket_id = require_active_bucket_id()
    ports = calculation_action_ports_factory(bucket_id=active_bucket_id, operation=operation)
    if ports.work_unit_repository.bucket_id != active_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    work_unit = require_active_work_unit(
        ports.work_unit_repository.load(),
        work_unit_id=payload.work_unit_id,
        repository_bucket_id=ports.work_unit_repository.bucket_id,
        use=ActiveWorkUnitUse.CALCULATE,
    )
    if work_unit.bucket_id != active_bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if payload.caller_context is ModeloWorkCalculateCallerContext.REPLAY_HEAD:
        replayed = await await_cancellation_complete(
            asyncio.to_thread(
                _replayed_head_inputs,
                payload=payload,
                work_unit=work_unit,
                ports=ports,
                operation=operation,
                attachment_store_factory=attachment_store_factory,
            ),
            task_name="modelo-work-calculate-caller-context-replay",
        )
        return PreparedModeloWorkCalculation(work_unit=work_unit, ports=ports, inputs=replayed)
    filing_instance_evidence = _ordinary_m303_filing_instance_evidence(
        payload=payload,
        work_unit=work_unit,
        operation=operation,
        attachment_store_factory=attachment_store_factory,
    )
    inputs = await await_cancellation_complete(
        asyncio.to_thread(
            payload.inputs.build_bundle,
            work_unit_id=payload.work_unit_id,
            ports=ports,
            profile=None,
            detail_rows=tuple(row.to_row() for row in payload.detail_rows),
            filing_instance_evidence=filing_instance_evidence,
        ),
        task_name="modelo-work-calculate-input-preparation",
    )
    return PreparedModeloWorkCalculation(work_unit=work_unit, ports=ports, inputs=inputs)


def _replayed_head_inputs(
    *,
    payload: ModeloWorkCalculateRequest,
    work_unit: WorkUnit,
    ports: CalculationActionPorts,
    operation: PinnedAuthorityOperation,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> WorkCalculateInputBundle:
    """Project the current head's caller context onto the calculation input channels.

    A head stored before operator layers existed replays no values (they are
    unknown, not empty), and the recalculation records no layer either, so that
    uncertainty is carried rather than silently resolved.
    """
    from ...core.authority_grade import RegistryAuthorityGrade
    from .calculate_input import WorkCalculateInputBundle
    from .caller_context import caller_context_calculation_inputs, caller_context_of

    head = (
        ports.calculation_repository.load(operation=operation).get(work_unit.current_calculation_revision_id)
        if work_unit.current_calculation_revision_id is not None
        else None
    )
    caller_context = caller_context_of(head)
    filing_instance_evidence = _ordinary_m303_filing_instance_evidence(
        payload=payload,
        work_unit=work_unit,
        operation=operation,
        attachment_store_factory=attachment_store_factory,
        replayed=caller_context.filing_instance_evidence,
    )
    replay = caller_context_calculation_inputs(
        caller_context,
        revision=operation.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        ).revision,
    )
    return WorkCalculateInputBundle.build(
        casilla_inputs=replay.casilla_inputs,
        text_casilla_inputs=replay.text_casilla_inputs,
        binding_values=replay.binding_values,
        enum_binding_values=replay.enum_binding_values,
        relation_values={},
        detail_rows=replay.detail_rows,
        borrador_snapshot_id=replay.borrador_snapshot_id,
        filing_instance_evidence=filing_instance_evidence,
        m210_official_tipo_renta_code=replay.m210_official_tipo_renta_code,
        m210_gross_income_source_mode=replay.m210_gross_income_source_mode,
        cleared_casilla_ids=replay.cleared_casilla_ids,
        record_operator_layer=caller_context.operator_layer_known,
    )


def calculate_prepared_modelo_work(
    prepared: PreparedModeloWorkCalculation, *, actor: str
) -> ModeloWorkCalculationServiceResult:
    """Run the one canonical calculation service for prepared worker inputs."""
    from .calculate_input import calculate_modelo_work_revision

    return calculate_modelo_work_revision(
        work_unit_id=prepared.work_unit.work_unit_id,
        actor=actor,
        inputs=prepared.inputs,
        ports=prepared.ports,
    )


def _ordinary_m303_filing_instance_evidence(
    *,
    payload: ModeloWorkCalculateRequest,
    work_unit: WorkUnit,
    operation: PinnedAuthorityOperation,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    replayed: FilingInstanceEvidence | None = None,
) -> FilingInstanceEvidence | None:
    """Author the one supported M303 envelope, or replay the head's, before calculation.

    Newly supplied facts are authored and win: the operator answered the
    questions again. Absent a new answer, the head's recorded evidence is
    replayed, because those are the operator's standing filing facts for this
    declaration. Only when neither exists is the evidence missing.
    """
    from ...core.modelo import Modelo

    supplied = payload.ordinary_m303_filing_evidence
    if work_unit.modelo != Modelo("303"):
        if supplied is None:
            return None
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "unsupported_modelo", {"modelo": str(work_unit.modelo), "evidence_present": True}
            )
        )
    if supplied is None and replayed is not None:
        return replayed
    if supplied is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing", {"modelo": str(work_unit.modelo), "evidence_present": False}
            )
        )
    return author_ordinary_m303_evidence_for_work(
        work_unit=work_unit,
        joint_return_elected=supplied.joint_return_elected,
        exonerado_390_attachment_id=supplied.m303_exonerado_390_attachment_id,
        exonerado_390_sha256=supplied.m303_exonerado_390_sha256,
        operation=operation,
        open_attachment_store=lambda: attachment_store_factory(work_unit.bucket_id),
    )


class ModeloWorkCalculateExecutor:
    """Recalculate a declaration from its ledger under the request's caller context.

    A replaying request is the workspace's Calculate action: it replays the
    caller context of the current calculation head -- the operator's own values
    and overrides, explicit clears, detail rows, Modelo 303 filing evidence,
    Modelo 210 selections and borrador snapshot -- so new ledger data reaches
    the declaration without discarding what the operator entered. A head stored
    before operator layers existed replays no values (they are unknown, not
    empty), and its recalculation records no layer either, so that uncertainty
    is carried rather than silently resolved. An explicit request, such as the
    CLI ``modelo work calculate`` command, keeps its full-specification
    semantics: exactly the inputs and detail rows it carries.
    """

    def __init__(
        self,
        *,
        calculation_action_ports_factory: CalculationActionPortsFactory,
        attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    ) -> None:
        """Retain the composition-owned calculation and encrypted-attachment factories."""
        self._calculation_action_ports_factory = calculation_action_ports_factory
        self._attachment_store_factory = attachment_store_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkCalculateRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate calculation without reinterpreting ledger or tax inputs."""
        await context.events.phase("modelo.work.calculate.ledger")
        payload = request.payload
        prepared = await prepare_modelo_work_calculation(
            payload=payload,
            operation=context.authority_operation,
            calculation_action_ports_factory=self._calculation_action_ports_factory,
            attachment_store_factory=self._attachment_store_factory,
        )

        async def publish() -> str:
            # The canonical service also owns migrations and IVA decisions.
            # Hold COMMIT across all of it, including cancellation settlement.
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(
                    calculate_prepared_modelo_work,
                    prepared,
                    actor=payload.actor,
                )
                # A revision no-op alone cannot establish that preparatory
                # migrations and IVA decisions also made no changes.
                if result.revision_published:
                    await context.events.effect(OperationEffect.UPDATED)
                public_result = await asyncio.to_thread(
                    calculation_public_result, result, operation=context.authority_operation
                )
                return await context.operands.put(public_result, written_at=_utc_now())

        return await await_cancellation_complete(publish(), task_name="modelo-work-calculate-publication")


def build_modelo_work_calculate_definition(
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> OperationDefinition:
    """Bind the canonical calculation service to the shared operation platform."""

    def build() -> ModeloWorkCalculateExecutor:
        return ModeloWorkCalculateExecutor(
            calculation_action_ports_factory=calculation_action_ports_factory,
            attachment_store_factory=attachment_store_factory,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkCalculateRequest,
        result_type=ModeloWorkCalculatePublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkCalculateRequest,
            executor_type=ModeloWorkCalculateExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.calculate.ledger",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_calculate_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind calculation to the exact refresh target carried by the receipt."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.request",
            schema_version=4,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.calculate.result",
            schema_version=2,
            model_type=ModeloWorkCalculatePublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


class ModeloWorkDiscardExecutor:
    """Run the existing discard writer against an exactly approved unit."""

    def __init__(self, *, work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory) -> None:
        """Bind the active-profile lifecycle authorities at the composition root."""
        self._work_lifecycle_ports_factory = work_lifecycle_ports_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkDiscardRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Verify the approval still holds, then delegate to the single writer.

        The approval check is about freshness, not lifecycle: whether a
        discarded unit may be discarded again is the writer's rule, and it
        refuses that itself with no effect. This only refuses acting on a unit
        the operator did not actually see.

        The declared phase is published before the approval check, so a
        REFUSED discard is still observably a discard that started. Emitting
        only on success would make a stale-approval refusal indistinguishable
        from an operation that never ran.
        """
        await context.events.phase(MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID)

        baseline = request.payload.baseline
        ports = self._work_lifecycle_ports_factory()

        def approved_unit() -> WorkUnit:
            current = get_work_unit(baseline.work_unit_id, ports=ports)
            if current.updated_at != baseline.observed_updated_at or current.name != baseline.name:
                raise ModeloWorkDiscardApprovalStaleError(
                    translated_message="errors.refused.modelo_work_discard_approval_stale",
                    context={"work_unit_id": baseline.work_unit_id},
                )
            return current

        current = await await_cancellation_complete(
            asyncio.to_thread(approved_unit), task_name="modelo-work-discard-approval"
        )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                discarded = await asyncio.to_thread(
                    discard_work_unit,
                    baseline.work_unit_id,
                    actor=request.payload.actor,
                    reason=request.payload.reason,
                    ports=ports,
                    expected=current,
                )
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    ModeloWorkDiscardPublicResultV2(
                        work_unit_id=discarded.work_unit_id,
                        bucket_id=discarded.bucket_id,
                        discarded=True,
                        unit=ModeloWorkMetadataSnapshot.from_work_unit(discarded),
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-discard-publication")


def build_modelo_work_discard_definition(
    *,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
) -> OperationDefinition:
    """Bind the discard writer to its registered operation contract."""

    def build() -> ModeloWorkDiscardExecutor:
        return ModeloWorkDiscardExecutor(work_lifecycle_ports_factory=work_lifecycle_ports_factory)

    return OperationDefinition(
        definition_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkDiscardRequest,
        result_type=ModeloWorkDiscardPublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkDiscardRequest,
            executor_type=ModeloWorkDiscardExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.discard",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_discard_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the discard definition to its stable public schemas and host reader."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.discard.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.discard.result",
            schema_version=2,
            model_type=ModeloWorkDiscardPublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


type ModeloWorkVerifyProfileResolver = Callable[[PinnedAuthorityOperation], TaxpayerProfile]


def _lifecycle_advisories(
    calculation_revision_id: str,
    *,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    workflow_profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> ModeloLifecycleAdvisories:
    """Capture presentation facts before the canonical writer can publish."""
    revision = calculation_repository.load(operation=operation).get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            translated_message="application.modelo.errors.calculation_revision_not_found",
            context={"calculation_revision_id": calculation_revision_id},
        )
    unit = work_unit_repository.load().get(revision.work_unit_id)
    if unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references "
            f"missing work_unit_id={revision.work_unit_id!r}",
        )
    return build_modelo_lifecycle_advisories(
        work_unit=unit, revision=revision, workflow_profile=workflow_profile, operation=operation
    )


def resolve_active_workflow_profile(operation: PinnedAuthorityOperation) -> TaxpayerProfile:
    """Resolve the active taxpayer profile when an operation actually runs.

    Injected as a strategy rather than a value: a definition composed into the
    production registry must not close over whichever profile happened to be
    active when the registry was built.
    """
    from ..wizard.status import load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    return load_active_taxpayer_profile(workflow_state_repository().load(), schema=operation.profile_schema())


# DELEGATED PHASE REPORTING, stated once for every executor in this module that
# delegates to an authority.
#
# Each such executor declares two phases -- an entry stage and an inner one --
# but hands the whole job to an authority that performs both inside a single
# call. The entry phase IS observable from here and is published before
# delegating. The inner phase is NOT: the transition to it happens inside the
# authority, invisible from outside, and emitting it after the call returns
# would mark ENTERING a stage that had already finished. An observer would read
# a phase that never bracketed any work, which is a worse report than silence.
#
# That leaves one declared code per such executor unbacked. It is a real gap,
# not an accepted one, and it closes in one of two ways: the authority receives
# the operation context and publishes the transition it can actually see, or
# the definition stops declaring a phase nobody can honestly emit. Both are
# decisions for the authority's owner rather than repairs to make from here.
#
# Effects follow the progression the other executor families use: UNKNOWN on
# entry, UPDATED once the write has landed. Reporting neither -- which this
# whole family did until 2026-08-31 -- makes the platform state that a filing
# operation changed nothing, which is a false claim rather than a silence.


_MODELO_WORK_VERIFY_GATES_PHASE = "modelo.work.verify.gates"
"""The one verify phase an executor outside the authority can honestly observe.

Declared here and used by both the definition's `phase_codes` and the emission,
so the code cannot be published under a spelling the definition does not
declare -- the execution context refuses an undeclared code, and a literal
repeated in two places is one typo away from that refusal at runtime.
"""


class ModeloWorkVerifyExecutor:
    """Run the existing verification authority under a recorded identity."""

    def __init__(
        self,
        *,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        profile_resolver: ModeloWorkVerifyProfileResolver,
        operator_scope_ports: OperatorScopePorts,
        verification_repository_bundle_factory: VerificationRepositoryBundleFactory,
    ) -> None:
        """Bind the live profile the gates are evaluated against."""
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._profile_resolver = profile_resolver
        self._operator_scope_ports = operator_scope_ports
        self._verification_repository_bundle_factory = verification_repository_bundle_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkVerifyRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the verification authority and return its report id.

        The authority owns the guarded persistence and the events it emits;
        nothing here writes a report or decides completeness.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase(_MODELO_WORK_VERIFY_GATES_PHASE)
        from ...core.bucket_pointer import require_active_bucket_id

        operation = context.authority_operation
        repositories = self._verification_repository_bundle_factory(require_active_bucket_id(), operation=operation)

        def prepare() -> tuple[TaxpayerProfile, ModeloLifecycleAdvisories]:
            profile = self._profile_resolver(operation)
            return profile, _lifecycle_advisories(
                request.payload.calculation_revision_id,
                calculation_repository=repositories.calculation,
                work_unit_repository=repositories.work_unit,
                workflow_profile=profile,
                operation=operation,
            )

        def verify_under_pinned_operation(profile: TaxpayerProfile):
            return verify_modelo_revision_with_preconditions(
                request.payload.calculation_revision_id,
                actor=request.payload.actor,
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                workflow_profile=profile,
                operator_scope_ports=self._operator_scope_ports,
                verification_repositories=repositories,
                operation=operation,
            )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                profile, advisories = await asyncio.to_thread(prepare)
                await context.events.effect(OperationEffect.UNKNOWN)
                outcome = await asyncio.to_thread(verify_under_pinned_operation, profile)
                report = outcome.report
                await context.events.effect(OperationEffect.UPDATED if outcome.published else OperationEffect.NONE)
                return await context.operands.put(
                    ModeloWorkVerifyPublicResultV2(
                        verification=ModeloVerificationSnapshot.from_verification(outcome),
                        advisories=advisories,
                        verification_report_id=report.verification_report_id,
                        calculation_revision_id=report.calculation_revision_id,
                        completeness_status=report.completeness_status.value,
                        granted_verificado_completo=report.granted_verificado_completo,
                        finding_count=len(report.findings),
                        missing_required_casilla_count=len(report.missing_required_casilla_ids),
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-verify-publication")


def build_modelo_work_verify_definition(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationDefinition:
    """Bind the verification authority to its registered operation contract."""

    def build() -> ModeloWorkVerifyExecutor:
        return ModeloWorkVerifyExecutor(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            verification_repository_bundle_factory=verification_repository_bundle_factory,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkVerifyRequest,
        result_type=ModeloWorkVerifyPublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkVerifyRequest,
            executor_type=ModeloWorkVerifyExecutor,
            build=build,
        ),
        phase_codes=(_MODELO_WORK_VERIFY_GATES_PHASE, "modelo.work.verify.persist"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.REQUEST_CANCEL,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_verify_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the verify definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.verify.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.verify.result",
            schema_version=2,
            model_type=ModeloWorkVerifyPublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


# SYNC DOMAIN CALLS RUN OFF THE EVENT LOOP
#
# The modelo authorities are synchronous, and two of them (`verify` and `file`)
# run a workflow preflight gate that calls `asyncio.run` internally. Calling
# them directly from an `async` executor is therefore not merely impolite, it
# RAISES: `asyncio.run()` cannot be called from a running event loop, and the
# supervisor records the resulting RuntimeError as an opaque diagnostic digest
# with no message. `verify` only reached that gate once its revision was
# verified-complete, so the defect stayed invisible while its fixture refused.
#
# `asyncio.to_thread` gives the callee a thread with no running loop, so its
# internal `asyncio.run` is legal again, and it copies the current context, so
# the bound repositories and profile resolve exactly as they do on the CLI. It
# also keeps a multi-second filing off the supervisor's loop, which a blocking
# bridge in the callee would not.


class ModeloWorkFileExecutor:
    """Record one local filing through the existing filing authority.

    This never submits to AEAT and never can: it calls the local filing
    authority and returns its record id. Live submission is prohibited, so the
    operation's whole output is a local record plus the operator's handoff.
    """

    def __init__(
        self,
        *,
        profile_resolver: ModeloWorkVerifyProfileResolver,
        operator_scope_ports: OperatorScopePorts,
        filing_action_ports_factory: FilingActionPortsFactory,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
    ) -> None:
        """Bind the live profile the filing gates are judged against."""
        self._profile_resolver = profile_resolver
        self._operator_scope_ports = operator_scope_ports
        self._filing_action_ports_factory = filing_action_ports_factory
        self._certificate_secret_backend_factory = certificate_secret_backend_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkFileRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the filing authority and return its record id.

        Every precondition - verification state, cross-period cleanliness,
        election legality - belongs to that authority and refuses there.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.work.file.preconditions")
        payload = request.payload
        from ...core.bucket_pointer import require_active_bucket_id

        filing_ports = self._filing_action_ports_factory(
            bucket_id=require_active_bucket_id(), operation=context.authority_operation
        )

        def prepare() -> tuple[TaxpayerProfile, ModeloLifecycleAdvisories]:
            profile = self._profile_resolver(context.authority_operation)
            return profile, _lifecycle_advisories(
                payload.approval.calculation_revision_id,
                calculation_repository=filing_ports.calculation_repository,
                work_unit_repository=filing_ports.work_unit_repository,
                workflow_profile=profile,
                operation=context.authority_operation,
            )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                profile, advisories = await asyncio.to_thread(prepare)
                await context.events.effect(OperationEffect.UNKNOWN)
                outcome = await asyncio.to_thread(
                    file_modelo_revision,
                    payload.approval.calculation_revision_id,
                    approved_verification_report_id=payload.approval.verification_report_id,
                    actor=payload.actor,
                    workflow_profile=profile,
                    certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                    operator_scope_ports=self._operator_scope_ports,
                    ports=filing_ports,
                    notes=payload.notes,
                    refund_election=payload.refund_election,
                    payment_election=payload.payment_election,
                    prior_domiciliation_election=payload.prior_domiciliation_election,
                    operation=context.authority_operation,
                )
                record = outcome.record
                await context.events.effect(OperationEffect.UPDATED if outcome.published else OperationEffect.NONE)
                return await context.operands.put(
                    ModeloWorkFilePublicResultV2(
                        record=ModeloFilingRecordSnapshot.from_record(record),
                        advisories=advisories,
                        published=outcome.published,
                        filing_record_id=record.filing_record_id,
                        work_unit_id=record.work_unit_id,
                        calculation_revision_id=record.calculation_revision_id,
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-file-publication")


def build_modelo_work_file_definition(
    *,
    operator_scope_ports: OperatorScopePorts,
    filing_action_ports_factory: FilingActionPortsFactory,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> OperationDefinition:
    """Bind the local filing authority to its registered operation contract."""

    def build() -> ModeloWorkFileExecutor:
        return ModeloWorkFileExecutor(
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            filing_action_ports_factory=filing_action_ports_factory,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkFileRequest,
        result_type=ModeloWorkFilePublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkFileRequest,
            executor_type=ModeloWorkFileExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.file.preconditions", "modelo.work.file.record"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_file_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the local filing definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.file.request",
            schema_version=2,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.file.result",
            schema_version=2,
            model_type=ModeloWorkFilePublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


#: The document format each calculation-report artefact serialises to. A member of
#: :class:`~cadrumo.core.modelo_export_artefact.ModeloExportArtefact` absent from
#: this table is not a report artefact, which is what keeps the fichero-BOE member
#: out of the report branch by construction rather than by a name comparison.
_REPORT_DOCUMENT_FORMATS: Mapping[ModeloExportArtefact, CalculationReportDocumentFormat] = MappingProxyType(
    {
        ModeloExportArtefact.CALCULATION_REPORT_CSV: CalculationReportDocumentFormat.CSV,
        ModeloExportArtefact.CALCULATION_REPORT_PDF: CalculationReportDocumentFormat.PDF,
    },
)


#: The same table read back, so a report receipt names the artefact that was asked for.
_REPORT_ARTEFACTS: Mapping[CalculationReportDocumentFormat, ModeloExportArtefact] = MappingProxyType(
    {document_format: artefact for artefact, document_format in _REPORT_DOCUMENT_FORMATS.items()},
)


def _require_export_terminal_receipt(
    receipt: ModeloExportResult | ModeloCalculationReportResult | None, terminal_receipt: OperationTerminalReceipt
) -> None:
    message = "export result contradicts its terminal receipt"
    if receipt is None:
        raise ValueError(message)
    require_terminal_receipt_match(
        terminal_receipt,
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=receipt.work_unit_id,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        message=message,
    )
    require_succeeded_receipt_references(terminal_receipt, message=message)


def _project_modelo_export_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the service's settled receipt into the public export result.

    Every fact is read from the receipt the export service returned; the only
    translation is from its field spelling into the closed public vocabulary.
    """
    settled = ModeloExportSettledResult.model_validate(result, strict=True)
    receipt = settled.fichero_boe if settled.fichero_boe is not None else settled.calculation_report
    _require_export_terminal_receipt(receipt, terminal_receipt)
    if settled.fichero_boe is not None:
        filing = settled.fichero_boe
        return ModeloExportPublicResultV3(
            calculation_revision_id=filing.calculation_revision_id,
            artefact=ModeloExportArtefact.FICHERO_BOE,
            export_format=filing.format,
            output_path=str(filing.output_path),
            byte_size=filing.byte_size,
            file_sha256=filing.file_sha256,
            software_identity_grade=filing.software_identity_grade,
            evidence_status=ModeloExportEvidenceStatus(filing.local_evidence_status),
            completeness=(
                ModeloExportCompleteness.UNVERIFIED
                if filing.completeness_unverified
                else ModeloExportCompleteness.NOT_FLAGGED
            ),
            fichero_boe=ModeloFicheroBoePublicReceipt.from_result(filing),
        )
    report = settled.calculation_report
    if report is None:
        raise ValueError("a settled export carries exactly one receipt")
    return ModeloExportPublicResultV3(
        calculation_revision_id=report.calculation_revision_id,
        artefact=_REPORT_ARTEFACTS[report.document_format],
        export_format=report.document_format.value,
        output_path=str(report.output_path),
        byte_size=report.byte_size,
        file_sha256=report.file_sha256,
        software_identity_grade=report.software_identity_grade,
        evidence_status=ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE,
        completeness=ModeloExportCompleteness.NOT_ASSESSED,
        calculation_report=ModeloCalculationReportPublicReceipt.from_result(report),
    )


class ModeloExportExecutor:
    """Export one revision through the existing authority, locally only.

    The authority is local by construction and never contacts AEAT; this
    enrolment adds no transport of its own, so an exported artefact reaches
    the tax authority only when a human carries it there.
    """

    def __init__(
        self,
        *,
        profile_resolver: ModeloWorkVerifyProfileResolver,
        export_ports_factory: ModeloExportPortsFactory,
        signing_keypair_capability_factory: ReviewPackageSigningKeypairCapabilityFactory,
        calculation_summary_pdf_writer: CalculationSummaryPdfWriter,
    ) -> None:
        """Bind the live profile the export gates are judged against, and the summary PDF writer.

        The writer is the outbound adapter the composition root supplies,
        because this layer cannot import it. It is handed to the report
        service on every report export and used only for the summary PDF.
        """
        self._profile_resolver = profile_resolver
        self._export_ports_factory = export_ports_factory
        self._signing_keypair_capability_factory = signing_keypair_capability_factory
        self._calculation_summary_pdf_writer = calculation_summary_pdf_writer

    async def execute(
        self,
        request: OperationRequest[ModeloExportRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the export authority and keep its receipt as the settled result.

        The command is built from the journalled request, so the identity an
        artefact is stamped with is the one this invocation recorded rather
        than whatever a closure happened to hold when the definition was built.

        The service's receipt is stored behind the secure operand boundary and
        its reference settles the operation, so a surface reads the evidence
        status, completeness and identity grade the service stated rather than
        a digest it would have to explain on its own.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.export.preconditions")
        payload = request.payload
        from ...core.bucket_pointer import require_active_bucket_id

        def export() -> ModeloExportSettledResult:
            with validating_governed_facts(context.authority_operation):
                workflow_profile = self._profile_resolver(context.authority_operation)
                active_bucket_id = require_active_bucket_id()
                export_ports = self._export_ports_factory(
                    bucket_id=active_bucket_id,
                    m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
                    operation=context.authority_operation,
                )
                if payload.artefact is ModeloExportArtefact.FICHERO_BOE:
                    return ModeloExportSettledResult(
                        fichero_boe=self._published_fichero_boe(
                            payload,
                            workflow_profile=workflow_profile,
                            export_ports=export_ports,
                            operation=context.authority_operation,
                        )
                    )
                return ModeloExportSettledResult(
                    calculation_report=self._published_calculation_report(
                        payload,
                        active_bucket_id=active_bucket_id,
                        export_ports=export_ports,
                        operation=context.authority_operation,
                    )
                )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                settled = await asyncio.to_thread(export)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(settled, written_at=_utc_now())

        return await await_cancellation_complete(publish(), task_name="modelo-export-publication")

    @staticmethod
    def _published_fichero_boe(
        payload: ModeloExportRequest,
        *,
        workflow_profile: TaxpayerProfile,
        export_ports: ModeloExportPorts,
        operation: PinnedAuthorityOperation,
    ) -> ModeloExportResult:
        """Publish the AEAT-compatible filing file and return the service's receipt."""
        return export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=payload.calculation_revision_id,
                output_path=Path(payload.output_path),
                actor=payload.actor,
                refund_election=payload.refund_election,
                payment_election=payload.payment_election,
                prior_domiciliation_election=payload.prior_domiciliation_election,
                replace_existing=payload.replace_existing,
            ),
            workflow_profile=workflow_profile,
            operation=operation,
            export_ports=export_ports,
        )

    def _published_calculation_report(
        self,
        payload: ModeloExportRequest,
        *,
        active_bucket_id: str,
        export_ports: ModeloExportPorts,
        operation: PinnedAuthorityOperation,
    ) -> ModeloCalculationReportResult:
        """Publish the calculation report and return the service's receipt.

        The declaration-shaping elections are not threaded here and their absence
        is not an omission: they decide the fichero's "Tipo de declaracion", and a
        calculation report declares nothing. The service the command line reaches
        is the one reached here, so the two surfaces cannot produce different
        reports for one revision.

        The report language is this invocation's own render language, so a
        full-screen session set to Catalan produces a Catalan report exactly as
        the command line does under ``--output-language ca``.

        The summary PDF is drawn by the writer this enrolment was composed with,
        the one the command line hands the same service. Where the optional
        ``pdf`` extra is absent the service refuses the PDF with its own typed
        error; nothing here substitutes another artefact.
        """
        return export_modelo_calculation_report(
            ModeloCalculationReportCommand(
                calculation_revision_id=payload.calculation_revision_id,
                document_format=_REPORT_DOCUMENT_FORMATS[payload.artefact],
                report_language=payload.report_language,
                output_path=Path(payload.output_path),
                replace_existing=payload.replace_existing,
            ),
            export_ports=export_ports,
            signing_keypair=self._signing_keypair_capability_factory(bucket_id=active_bucket_id),
            operation=operation,
            pdf_writer=self._calculation_summary_pdf_writer,
        )


def build_modelo_export_definition(
    *,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
    export_ports_factory: ModeloExportPortsFactory,
    signing_keypair_capability_factory: ReviewPackageSigningKeypairCapabilityFactory,
    calculation_summary_pdf_writer: CalculationSummaryPdfWriter,
) -> OperationDefinition:
    """Bind the export authority to its registered operation contract."""

    def build() -> ModeloExportExecutor:
        return ModeloExportExecutor(
            profile_resolver=profile_resolver,
            export_ports_factory=export_ports_factory,
            signing_keypair_capability_factory=signing_keypair_capability_factory,
            calculation_summary_pdf_writer=calculation_summary_pdf_writer,
        )

    return OperationDefinition(
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloExportRequest,
        result_type=ModeloExportSettledResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloExportRequest,
            executor_type=ModeloExportExecutor,
            build=build,
        ),
        phase_codes=("modelo.export.preconditions", "modelo.export.render"),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_export_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the export definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.request",
            schema_version=3,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.result",
            schema_version=3,
            model_type=ModeloExportPublicResultV3,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
        result_projector=_project_modelo_export_result,
    )


class ModeloWorkAmendExecutor:
    """Record one amendment through the existing amendment authority.

    Like the filing enrolment this is local: an amendment is built and
    recorded here, and the operator submits it themselves.
    """

    def __init__(self, *, amendment_action_ports_factory: AmendmentActionPortsFactory) -> None:
        """Bind the amendment authorities supplied by the composition root."""
        self._amendment_action_ports_factory = amendment_action_ports_factory

    async def execute(
        self,
        request: OperationRequest[ModeloWorkAmendRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the amendment authority and retain its encrypted result.

        Which overrides are legal, which kinds a modelo admits, and whether the
        baseline is AEAT-attested are all the authority's decisions.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.work.amend.baseline")
        payload = request.payload
        from ...core.bucket_pointer import require_active_bucket_id

        def amend() -> ModeloRecord:
            # Row hydration and every authority-backed read use the retained
            # operation. The outer guard covers the complete canonical writer.
            with validating_governed_facts(context.authority_operation):
                return amend_modelo_revision(
                    from_filing_record_id=payload.baseline.from_filing_record_id,
                    overrides={override.casilla_id: override.as_decimal() for override in payload.overrides},
                    amendment_kind=payload.amendment_kind,
                    m303_rectificativa_motive=payload.m303_rectificativa_motive,
                    detail_rows=(
                        None if payload.detail_rows is None else tuple(row.to_row() for row in payload.detail_rows)
                    ),
                    reason=payload.reason,
                    actor=payload.actor,
                    ports=self._amendment_action_ports_factory(
                        bucket_id=require_active_bucket_id(), operation=context.authority_operation
                    ),
                    operation=context.authority_operation,
                )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                record = await asyncio.to_thread(amend)
                await context.events.effect(OperationEffect.UPDATED)
                if record.amends_filing_record_id is None:
                    raise ValueError("amendment writer returned a record without its baseline")
                return await context.operands.put(
                    ModeloWorkAmendPublicResultV2(
                        record=ModeloFilingRecordSnapshot.from_record(record),
                        source_filing_record_id=payload.baseline.from_filing_record_id,
                        amended_from_filing_record_id=record.amends_filing_record_id,
                        amendment_kind=payload.amendment_kind,
                        corrected_casilla_count=len(payload.overrides),
                        m303_rectificativa_motive=payload.m303_rectificativa_motive,
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-work-amend-publication")


def build_modelo_work_amend_definition(
    *,
    amendment_action_ports_factory: AmendmentActionPortsFactory,
) -> OperationDefinition:
    """Bind the amendment authority to its registered operation contract."""

    def build() -> ModeloWorkAmendExecutor:
        return ModeloWorkAmendExecutor(amendment_action_ports_factory=amendment_action_ports_factory)

    return OperationDefinition(
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkAmendRequest,
        result_type=ModeloWorkAmendPublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkAmendRequest,
            executor_type=ModeloWorkAmendExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.amend.baseline", "modelo.work.amend.record"),
        # No REVIEW: the platform's review contract means the executor presents a
        # reviewed operand and settles on the operator's verdict. These run
        # straight through, so claiming REVIEW would declare an interaction that
        # never happens.
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_amend_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the amendment definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.amend.request",
            schema_version=2,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.amend.result",
            schema_version=2,
            model_type=ModeloWorkAmendPublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


class ModeloEditApplyExecutor:
    """Run the Edit Contract's guarded compare-and-swap apply under one recorded identity.

    apply_modelo_edit already owns the commit-point baseline recheck, the
    calculate/recalculate discrimination (recalculate refuses honestly, by
    design, until it is wired) and the co-committed result receipt; this only
    binds the running operation's own identity to that call and re-implements
    no lifecycle policy.
    """

    def __init__(
        self,
        *,
        calculation_action_ports_factory: CalculationActionPortsFactory,
        receipt_repository_factory: ModeloEditReceiptRepositoryFactory,
        prerequisite_observer: ModeloEditPrerequisiteObserver | None = None,
    ) -> None:
        """Bind the calculation authorities supplied by the composition root."""
        self._calculation_action_ports_factory = calculation_action_ports_factory
        self._receipt_repository_factory = receipt_repository_factory
        self._prerequisite_observer = prerequisite_observer

    async def execute(
        self,
        request: OperationRequest[ModeloEditApplyOperationRequestV1],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to apply_modelo_edit and return the settled receipt id.

        A refused edit (ModeloEditExecutionNoEffectV1) changed nothing: the
        effect is reported as NONE, then the refusal is raised as the
        registered refusal error of its family, which the supervisor settles
        as REFUSED under that error's code. Only the family travels; the
        typed refusal's addresses, facts, and evidence stay out of the
        operation's persisted record.

        Unlike its delegating siblings this executor declares ONE phase and
        publishes it, because there is no inner transition it cannot see.
        """
        await context.events.phase(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID)
        operation = context.authority_operation

        def apply() -> ModeloEditExecutionResultV1:
            with validating_governed_facts(operation):
                submission = request.payload.submission.to_submission()
                baseline = submission.baseline
                return apply_modelo_edit(
                    ModeloEditApplyRequestV1(operation_id=context.identity.operation_id, submission=submission),
                    ports=self._calculation_action_ports_factory(bucket_id=baseline.bucket_id, operation=operation),
                    receipt_repository=self._receipt_repository_factory(bucket_id=baseline.bucket_id),
                    now=_utc_now(),
                    result_destination=f"modelo/{baseline.modelo}/{baseline.filing_year}/{baseline.period}/edit-result",
                )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                outcome = await asyncio.to_thread(apply)
                if isinstance(outcome, ModeloEditExecutionNoEffectV1):
                    # A refused edit changed nothing, and NONE is the truthful report
                    # of that -- distinct from the UNKNOWN carried while the outcome
                    # was still open -- recorded before the refusal settles it.
                    await context.events.effect(OperationEffect.NONE)
                    self._deliver_prerequisite(
                        outcome.refusal,
                        operation_id=str(context.identity.operation_id),
                        baseline=request.payload.submission.baseline,
                    )
                    raise modelo_edit_refusal_error(outcome.refusal)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    ModeloEditApplyPublicResultV1(
                        receipt_id=outcome.receipt.receipt_id,
                        calculation_revision_id=outcome.receipt.calculation_revision_id,
                    ),
                    written_at=_utc_now(),
                )

        return await await_cancellation_complete(publish(), task_name="modelo-edit-apply-publication")

    def _deliver_prerequisite(
        self, refusal: ModeloEditRefusalV1, *, operation_id: str, baseline: ModeloEditApplyBaselineV1
    ) -> None:
        """Hand a calculation source the refused Apply named to the private observer, if any.

        Private diagnostics never enter the operation record, and delivery cannot
        change the truthful NONE effect or the refusal that settles the operation.
        """
        observer = self._prerequisite_observer
        if (
            observer is None
            or not isinstance(refusal, ModeloEditDomainRefusalV1)
            or not isinstance(refusal.address, ModeloEditScalarAddressV1)
            or "calculation_source_unresolved" not in refusal.facts
        ):
            return
        try:
            observer(
                ModeloEditCalculationPrerequisiteV1(
                    operation_id=operation_id,
                    work_unit_id=str(baseline.work_unit_id),
                    baseline_id=str(baseline.baseline_id),
                    calculation_revision_id=baseline.current_calculation_revision_id,
                    casilla_id=refusal.address.casilla_id,
                    binding_ids=refusal.evidence,
                )
            )
        except Exception:
            get_logger(__name__).warning("private edit diagnostic delivery was unavailable")


def build_modelo_edit_apply_definition(
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    receipt_repository_factory: ModeloEditReceiptRepositoryFactory,
    prerequisite_observer: ModeloEditPrerequisiteObserver | None = None,
) -> OperationDefinition:
    """Bind the Edit Contract's guarded apply path to its registered operation contract."""

    def build() -> ModeloEditApplyExecutor:
        return ModeloEditApplyExecutor(
            calculation_action_ports_factory=calculation_action_ports_factory,
            receipt_repository_factory=receipt_repository_factory,
            prerequisite_observer=prerequisite_observer,
        )

    return OperationDefinition(
        definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
        request_type=ModeloEditApplyOperationRequestV1,
        result_type=ModeloEditApplyPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloEditApplyOperationRequestV1,
            executor_type=ModeloEditApplyExecutor,
            build=build,
        ),
        phase_codes=("modelo.edit.apply",),
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_edit_apply_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the edit-apply definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.request",
            schema_version=1,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.edit.apply.result",
            schema_version=1,
            model_type=ModeloEditApplyPublicResultV1,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


def build_modelo_work_rename_definition(
    *,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
) -> OperationDefinition:
    """Bind the rename writer to its registered operation contract."""

    def build() -> ModeloWorkRenameExecutor:
        return ModeloWorkRenameExecutor(work_lifecycle_ports_factory=work_lifecycle_ports_factory)

    return OperationDefinition(
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRenameRequest,
        result_type=ModeloWorkRenamePublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkRenameRequest,
            executor_type=ModeloWorkRenameExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.rename",),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        public_error_detail=True,
    )


def build_modelo_work_rename_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the rename definition to its stable public schemas and host reader."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.request",
            schema_version=2,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.work.rename.result",
            schema_version=2,
            model_type=ModeloWorkRenamePublicResultV2,
        ),
        workspace_refresh_target_schema=_modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


def build_modelo_lifecycle_operation_definitions(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_scope_ports: OperatorScopePorts,
    export_ports_factory: ModeloExportPortsFactory,
    signing_keypair_capability_factory: ReviewPackageSigningKeypairCapabilityFactory,
    calculation_summary_pdf_writer: CalculationSummaryPdfWriter,
    calculation_action_ports_factory: CalculationActionPortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    amendment_action_ports_factory: AmendmentActionPortsFactory,
    filing_action_ports_factory: FilingActionPortsFactory,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
    receipt_repository_factory: ModeloEditReceiptRepositoryFactory,
    verification_repository_bundle_factory: VerificationRepositoryBundleFactory,
    edit_prerequisite_observer: ModeloEditPrerequisiteObserver | None = None,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
) -> tuple[OperationDefinition, ...]:
    """Return the one canonical modelo lifecycle operation population.

    Every definition this module exports belongs here. A definition that is
    exported and never composed is capacity nothing can reach, which is the
    shape this population exists to make impossible to ship.
    """
    population = (
        build_modelo_work_calculate_definition(
            calculation_action_ports_factory=calculation_action_ports_factory,
            attachment_store_factory=attachment_store_factory,
        ),
        build_modelo_edit_apply_definition(
            calculation_action_ports_factory=calculation_action_ports_factory,
            receipt_repository_factory=receipt_repository_factory,
            prerequisite_observer=edit_prerequisite_observer,
        ),
        build_modelo_export_definition(
            export_ports_factory=export_ports_factory,
            profile_resolver=profile_resolver,
            signing_keypair_capability_factory=signing_keypair_capability_factory,
            calculation_summary_pdf_writer=calculation_summary_pdf_writer,
        ),
        build_modelo_work_amend_definition(amendment_action_ports_factory=amendment_action_ports_factory),
        build_modelo_work_discard_definition(work_lifecycle_ports_factory=work_lifecycle_ports_factory),
        build_modelo_work_file_definition(
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            filing_action_ports_factory=filing_action_ports_factory,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
        ),
        build_modelo_work_rename_definition(work_lifecycle_ports_factory=work_lifecycle_ports_factory),
        build_modelo_work_verify_definition(
            profile_resolver=profile_resolver,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=operator_scope_ports,
            verification_repository_bundle_factory=verification_repository_bundle_factory,
        ),
    )
    # A registry holds its definitions in definition-id order, so the
    # population is returned in that order whatever order it is built in.
    return tuple(sorted(population, key=lambda definition: definition.definition_id))


def build_modelo_lifecycle_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
    *,
    metadata_access_resolver: OperationAccessResolver | None = None,
    revision_access_resolver: OperationAccessResolver | None = None,
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind each lifecycle definition to its stable public schemas."""
    builders = {
        MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID: build_modelo_edit_apply_registration,
        MODELO_EXPORT_OPERATION_DEFINITION_ID: build_modelo_export_registration,
        MODELO_WORK_AMEND_OPERATION_DEFINITION_ID: build_modelo_work_amend_registration,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID: build_modelo_work_calculate_registration,
        MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID: build_modelo_work_discard_registration,
        MODELO_WORK_FILE_OPERATION_DEFINITION_ID: build_modelo_work_file_registration,
        MODELO_WORK_RENAME_OPERATION_DEFINITION_ID: build_modelo_work_rename_registration,
        MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID: build_modelo_work_verify_registration,
    }
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        if definition.definition_id == MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_calculate_registration(
                definition, access_resolver=metadata_access_resolver
            )
        elif definition.definition_id == MODELO_WORK_RENAME_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_rename_registration(definition, access_resolver=metadata_access_resolver)
        elif definition.definition_id == MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_discard_registration(definition, access_resolver=metadata_access_resolver)
        elif definition.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_verify_registration(definition, access_resolver=revision_access_resolver)
        elif definition.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_file_registration(definition, access_resolver=revision_access_resolver)
        elif definition.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID:
            registration = build_modelo_work_amend_registration(definition, access_resolver=revision_access_resolver)
        elif definition.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID:
            registration = build_modelo_export_registration(definition, access_resolver=revision_access_resolver)
        elif definition.definition_id == MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID:
            registration = build_modelo_edit_apply_registration(definition, access_resolver=metadata_access_resolver)
        else:
            registration = builders[definition.definition_id](definition)
        registrations.append(registration)
    return tuple(registrations)


__all__ = [
    "MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID",
    "MODELO_EXPORT_OPERATION_DEFINITION_ID",
    "MODELO_WORK_AMEND_OPERATION_DEFINITION_ID",
    "MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID",
    "MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID",
    "MODELO_WORK_FILE_OPERATION_DEFINITION_ID",
    "MODELO_WORK_RENAME_OPERATION_DEFINITION_ID",
    "MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID",
    "ModeloEditApplyExecutor",
    "ModeloExportExecutor",
    "ModeloWorkAmendExecutor",
    "ModeloWorkCalculateExecutor",
    "ModeloWorkDiscardApprovalStaleError",
    "ModeloWorkDiscardExecutor",
    "ModeloWorkFileExecutor",
    "ModeloWorkRenameExecutor",
    "ModeloWorkVerifyExecutor",
    "PreparedModeloWorkCalculation",
    "build_modelo_edit_apply_definition",
    "build_modelo_edit_apply_registration",
    "build_modelo_export_definition",
    "build_modelo_export_registration",
    "build_modelo_lifecycle_operation_definitions",
    "build_modelo_lifecycle_operation_registrations",
    "build_modelo_work_amend_definition",
    "build_modelo_work_amend_registration",
    "build_modelo_work_calculate_definition",
    "build_modelo_work_calculate_registration",
    "build_modelo_work_discard_definition",
    "build_modelo_work_discard_registration",
    "build_modelo_work_file_definition",
    "build_modelo_work_file_registration",
    "build_modelo_work_rename_definition",
    "build_modelo_work_rename_registration",
    "build_modelo_work_verify_definition",
    "build_modelo_work_verify_registration",
    "calculate_prepared_modelo_work",
    "calculation_public_result",
    "prepare_modelo_work_calculation",
]
