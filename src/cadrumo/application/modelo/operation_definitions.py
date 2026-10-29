"""Register modelo lifecycle operations using their canonical writers and public contracts.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from .action_errors import (
    CalculationRevisionNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from .amendment_action_ports import AmendmentActionPortsFactory
from .amendment_actions import amend_modelo_revision
from .amendment_projection import ModeloWorkAmendPublicResultV2
from .calculation_action_ports import CalculationActionPortsFactory
from .calculation_operation import build_modelo_work_calculate_definition, build_modelo_work_calculate_registration
from .edit_operation import build_modelo_edit_apply_definition, build_modelo_edit_apply_registration
from .edit_receipt_ports import ModeloEditReceiptRepositoryFactory
from .edit_refusal_projection import ModeloEditPrerequisiteObserver
from .export_operation import build_modelo_export_definition, build_modelo_export_registration
from .export_ports import ModeloExportPortsFactory
from .filing_action_ports import FilingActionPortsFactory
from .filing_actions import file_modelo_revision
from .filing_projection import ModeloFilingRecordSnapshot
from .lifecycle_advisories import ModeloLifecycleAdvisories, build_modelo_lifecycle_advisories
from .metadata_projection import ModeloWorkMetadataSnapshot
from .operation_shared import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloWorkVerifyProfileResolver,
    modelo_workspace_refresh_target_binding,
    resolve_active_workflow_profile,
    resolve_modelo_work_unit_refresh_target,
)
from .review_package_signing_ports import ReviewPackageSigningKeypairCapabilityFactory
from .verification_actions import verify_modelo_revision_with_preconditions
from .verification_projection import ModeloVerificationSnapshot
from .work_amend_contracts import ModeloWorkAmendRequest
from .work_change_contracts import (
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from .work_filing_contracts import ModeloWorkFilePublicResultV2, ModeloWorkFileRequest
from .work_lifecycle import discard_work_unit, get_work_unit, rename_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory
from .work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ...domain.deadlines.models import TaxpayerProfile
    from ...domain.modelos.filing_record import ModeloRecord
    from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
    from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
    from ..auth.operator_scope_ports import OperatorScopePorts
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext
    from .calculation_summary_pdf_ports import CalculationSummaryPdfWriter
    from .verification_repository_ports import VerificationRepositoryBundleFactory


#: Suffix appended to a definition id to name that enrolment's refresh-target
#: schema. Every Modelo enrolment binds the SAME target model, but each needs
#: its own schema identity: the registry resolves a schema binding by scanning
#: every registration and taking the first identity match, so one id shared
#: across enrolments would stop that lookup being definition-scoped.


class ModeloWorkRenameExecutor:
    """Run the existing rename writer under one recorded operation identity."""

    def __init__(
        self,
        *,
        work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the active-profile lifecycle authorities at the composition root."""
        self._work_lifecycle_ports_factory = work_lifecycle_ports_factory
        self._execution_caller_reader = execution_caller_reader

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
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=request.payload.actor)
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
                    actor=actor,
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


class ModeloWorkDiscardExecutor:
    """Run the existing discard writer against an exactly approved unit."""

    def __init__(
        self,
        *,
        work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the active-profile lifecycle authorities at the composition root."""
        self._work_lifecycle_ports_factory = work_lifecycle_ports_factory
        self._execution_caller_reader = execution_caller_reader

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
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=request.payload.actor)
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
                    actor=actor,
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
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the discard writer to its registered operation contract."""

    def build() -> ModeloWorkDiscardExecutor:
        return ModeloWorkDiscardExecutor(
            work_lifecycle_ports_factory=work_lifecycle_ports_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkDiscardRequest,
        subject_reference=OperationSubjectReferenceV1.payload_field("baseline", "work_unit_id"),
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
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


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
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the live profile the gates are evaluated against."""
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._profile_resolver = profile_resolver
        self._operator_scope_ports = operator_scope_ports
        self._verification_repository_bundle_factory = verification_repository_bundle_factory
        self._execution_caller_reader = execution_caller_reader

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

        actor = execution_actor_label(self._execution_caller_reader, context, supplied=request.payload.actor)
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
                actor=actor,
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
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the verification authority to its registered operation contract."""

    def build() -> ModeloWorkVerifyExecutor:
        return ModeloWorkVerifyExecutor(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            verification_repository_bundle_factory=verification_repository_bundle_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkVerifyRequest,
        subject_reference=OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id"),
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
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
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
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the live profile the filing gates are judged against."""
        self._profile_resolver = profile_resolver
        self._operator_scope_ports = operator_scope_ports
        self._filing_action_ports_factory = filing_action_ports_factory
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._execution_caller_reader = execution_caller_reader

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
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=payload.actor)
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
                    actor=actor,
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
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the local filing authority to its registered operation contract."""

    def build() -> ModeloWorkFileExecutor:
        return ModeloWorkFileExecutor(
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            filing_action_ports_factory=filing_action_ports_factory,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkFileRequest,
        subject_reference=OperationSubjectReferenceV1.stored_work_unit("approval", "calculation_revision_id"),
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
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


#: The document format each calculation-report artefact serialises to. A member of
#: :class:`~cadrumo.core.modelo_export_artefact.ModeloExportArtefact` absent from
#: this table is not a report artefact, which is what keeps the fichero-BOE member
#: out of the report branch by construction rather than by a name comparison.


#: The same table read back, so a report receipt names the artefact that was asked for.


class ModeloWorkAmendExecutor:
    """Record one amendment through the existing amendment authority.

    Like the filing enrolment this is local: an amendment is built and
    recorded here, and the operator submits it themselves.
    """

    def __init__(
        self,
        *,
        amendment_action_ports_factory: AmendmentActionPortsFactory,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the amendment authorities supplied by the composition root."""
        self._amendment_action_ports_factory = amendment_action_ports_factory
        self._execution_caller_reader = execution_caller_reader

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
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=payload.actor)
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
                    actor=actor,
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
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the amendment authority to its registered operation contract."""

    def build() -> ModeloWorkAmendExecutor:
        return ModeloWorkAmendExecutor(
            amendment_action_ports_factory=amendment_action_ports_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkAmendRequest,
        subject_reference=OperationSubjectReferenceV1.stored_work_unit("baseline", "from_filing_record_id"),
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
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
    )


def build_modelo_work_rename_definition(
    *,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the rename writer to its registered operation contract."""

    def build() -> ModeloWorkRenameExecutor:
        return ModeloWorkRenameExecutor(
            work_lifecycle_ports_factory=work_lifecycle_ports_factory,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRenameRequest,
        subject_reference=OperationSubjectReferenceV1.payload_field("work_unit_id"),
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
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
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
    execution_caller_reader: OperationExecutionCallerReader | None = None,
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
            execution_caller_reader=execution_caller_reader,
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
            execution_caller_reader=execution_caller_reader,
        ),
        build_modelo_work_amend_definition(
            amendment_action_ports_factory=amendment_action_ports_factory,
            execution_caller_reader=execution_caller_reader,
        ),
        build_modelo_work_discard_definition(
            work_lifecycle_ports_factory=work_lifecycle_ports_factory,
            execution_caller_reader=execution_caller_reader,
        ),
        build_modelo_work_file_definition(
            profile_resolver=profile_resolver,
            operator_scope_ports=operator_scope_ports,
            filing_action_ports_factory=filing_action_ports_factory,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            execution_caller_reader=execution_caller_reader,
        ),
        build_modelo_work_rename_definition(
            work_lifecycle_ports_factory=work_lifecycle_ports_factory,
            execution_caller_reader=execution_caller_reader,
        ),
        build_modelo_work_verify_definition(
            profile_resolver=profile_resolver,
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_scope_ports=operator_scope_ports,
            verification_repository_bundle_factory=verification_repository_bundle_factory,
            execution_caller_reader=execution_caller_reader,
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
