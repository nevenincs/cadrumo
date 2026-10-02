"""Run the existing five-stage quickfile chain under exact-profile worker authority."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import override

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import M303FilingEvidenceError
from .calculate_input import WorkCalculateInputBundle
from .m303_filing_evidence import m303_filing_evidence_failure
from .m303_ordinary_filing_evidence_authoring import author_ordinary_m303_evidence_for_work
from .quickfile import QuickfileCommand, QuickfileStage, run_modelo_quickfile
from .quickfile_operation_contracts import QuickfileProjection, QuickfileRequest
from .quickfile_operation_ports import QuickfileOperationPorts, QuickfileOperationPortsFactory

QUICKFILE_OPERATION_DEFINITION_ID = "modelo.quickfile"


class QuickfileExecutionResult(BaseModel):
    """Retain the encrypted chain completion separately from its reviewed public schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: QuickfileProjection


class _Writes(LedgerCommitAttemptTracker):
    """Count completed concrete writes while preserving canonical uncertain outcomes."""

    def __init__(self) -> None:
        """Retain concrete confirmed writes independently of failed attempts."""
        super().__init__()
        self._count = 0
        self._count_lock = threading.Lock()

    @property
    def count(self) -> int:
        """Return the number of complete prepared writers that returned."""
        with self._count_lock:
            return self._count

    @override
    def call_writer(self, write: Callable[[], None]) -> None:
        """Count a confirmed writer after its complete commit boundary settles."""
        super().call_writer(write)
        with self._count_lock:
            self._count += 1

    def effect(self, *, incomplete: bool) -> OperationEffect:
        """Retain earlier writes when a later stage refuses or becomes uncertain."""
        if self.has_uncertain_write:
            return OperationEffect.UNKNOWN
        if self.confirmed_write:
            return OperationEffect.PARTIAL if incomplete else OperationEffect.UPDATED
        return OperationEffect.NONE


def _require_profile(request: OperationRequest[QuickfileRequest], context: OperationExecutorContext) -> None:
    payload = request.payload
    if (
        request.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
        or request.subject_ref != profile_operation_subject(str(payload.profile_id))
        or require_active_bucket_id() != str(payload.profile_id)
        or (payload.bucket_id is not None and payload.bucket_id != payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_ports(
    ports: QuickfileOperationPorts, request: QuickfileRequest, context: OperationExecutorContext
) -> None:
    profile_id = str(request.profile_id)
    if (
        ports.profile_id != request.profile_id
        or ports.operation is not context.authority_operation
        or str(ports.profile.record.profile_id) != profile_id
        or ports.calculation.operation is not context.authority_operation
        or ports.calculation.work_unit_repository.bucket_id != profile_id
        or ports.export.work_unit.bucket_id != profile_id
        or ports.verification.work_unit.bucket_id != profile_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _inputs(payload: QuickfileRequest, ports: QuickfileOperationPorts, work_unit_id: str) -> WorkCalculateInputBundle:
    unit = ports.calculation.work_unit_repository.load().get(work_unit_id)
    if unit is None or unit.bucket_id != str(payload.profile_id) or unit.period != payload.period.to_period():
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    supplied = payload.ordinary_m303_filing_evidence
    evidence = None
    if payload.modelo == "303":
        if supplied is None:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "missing", {"modelo": "303", "evidence_present": False}
                )
            )
        evidence = author_ordinary_m303_evidence_for_work(
            work_unit=unit,
            joint_return_elected=supplied.joint_return_elected,
            exonerado_390_attachment_id=supplied.m303_exonerado_390_attachment_id,
            exonerado_390_sha256=supplied.m303_exonerado_390_sha256,
            operation=ports.operation,
            open_attachment_store=lambda: ports.attachments,
            profile=ports.profile,
        )
    return payload.inputs.to_calculation_fields().build_bundle(
        work_unit_id=work_unit_id,
        ports=ports.calculation,
        profile=ports.profile,
        detail_rows=tuple(row.to_row() for row in payload.detail_rows),
        filing_instance_evidence=evidence,
    )


class QuickfileExecutor:
    """Own actual mutation fences and cancellation settlement without copying any stage."""

    def __init__(self, factory: QuickfileOperationPortsFactory) -> None:
        """Retain the exact-profile capabilities factory without resolving storage."""
        self._factory = factory

    async def execute(self, request: OperationRequest[QuickfileRequest], context: OperationExecutorContext) -> str:
        """Join the canonical synchronous chain and settle all admitted local writes."""
        _require_profile(request, context)
        payload = request.payload
        writes = _Writes()
        loop = asyncio.get_running_loop()
        admission_failure: BaseException | None = None
        await context.events.phase(QUICKFILE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        async def admit() -> None:
            nonlocal admission_failure
            if admission_failure is not None:
                raise admission_failure
            try:
                # Refresh authority briefly; no readiness, model, provider or
                # domain preparation runs while this boundary is held.
                async with context.cancellation.irreversible_section():
                    _require_profile(request, context)
            except BaseException as error:
                admission_failure = error
                writes.abort()
                raise

        def before_stage(_stage: QuickfileStage) -> None:
            asyncio.run_coroutine_threadsafe(admit(), loop).result()

        def work() -> QuickfileProjection:
            before_stage(QuickfileStage.READINESS)
            with validating_governed_facts(context.authority_operation):
                ports = self._factory(
                    profile_id=payload.profile_id,
                    operation=context.authority_operation,
                    mutation_writer=writes.call_writer,
                )
                _require_ports(ports, payload, context)
                result = run_modelo_quickfile(
                    QuickfileCommand(
                        bucket_id=str(payload.profile_id),
                        modelo=payload.modelo,
                        filing_year=payload.period.to_period().filing_year,
                        period=payload.period.to_period(),
                        registry_revision_id=payload.revision_id,
                        output_path=Path(payload.output_path),
                        actor=payload.actor,
                        refund_election=payload.refund_election,
                        payment_election=payload.payment_election,
                        prior_domiciliation_election=payload.prior_domiciliation_election,
                    ),
                    certificate_secret_backend_factory=ports.certificate_secret_backend_factory,
                    operator_probe_ports=ports.operator_probe_ports,
                    operator_scope_ports=ports.operator_scope_ports,
                    operation=ports.operation,
                    verification_repositories=ports.verification,
                    calculation_action_ports=ports.calculation,
                    modelo_export_ports=ports.export,
                    read_ports=ports.read,
                    workflow_profile=ports.workflow_profile,
                    build_calculation_inputs=lambda work_unit_id: _inputs(payload, ports, work_unit_id),
                    profile=ports.profile,
                    before_stage=before_stage,
                    mutation_writer=writes.call_writer,
                )
                if admission_failure is not None:
                    raise admission_failure
                _require_profile(request, context)
                if result.modelo != payload.modelo or result.period != payload.period.to_period():
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                return QuickfileProjection.from_result(
                    result,
                    profile_id=payload.profile_id,
                    write_count=writes.count,
                    effect=writes.effect(incomplete=not result.completed),
                )

        async def settle() -> str:
            try:
                result = await run_with_ledger_commit_fence(
                    work, tracker=writes, context=context, task_name=QUICKFILE_OPERATION_DEFINITION_ID
                )
                retained = QuickfileExecutionResult(projection=result)
                if len(canonical_json_bytes(retained.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                reference = await context.operands.put(retained, written_at=now())
                await context.events.effect(result.effect)
                return reference
            except BaseException:
                await context.events.effect(writes.effect(incomplete=True))
                raise

        return await await_cancellation_complete(settle(), task_name=QUICKFILE_OPERATION_DEFINITION_ID)


def project_quickfile_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> QuickfileProjection:
    """A stopped chain is result data; its confirmed and uncertain effects remain authoritative."""
    if not isinstance(result, QuickfileExecutionResult) or type(result) is not QuickfileExecutionResult:
        raise ValueError("invalid quickfile result")
    projection = result.projection
    if (
        receipt.identity.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not projection.effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("quickfile result contradicts its terminal receipt")
    return projection


def build_quickfile_definition(factory: QuickfileOperationPortsFactory) -> OperationDefinition:
    """Register the existing local human chain with encrypted inputs and full effect settlement."""
    return OperationDefinition(
        definition_id=QUICKFILE_OPERATION_DEFINITION_ID,
        request_type=QuickfileRequest,
        result_type=QuickfileExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=QuickfileRequest, executor_type=QuickfileExecutor, build=lambda: QuickfileExecutor(factory)
        ),
        phase_codes=(QUICKFILE_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.COOPERATIVE,
            deadline=OperationDeadline.COOPERATIVE,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.REQUEST_CANCEL,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_quickfile_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the human destination, both value categories and exact natural filing period."""
    if (
        definition.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        or definition.request_type is not QuickfileRequest
        or definition.result_type is not QuickfileExecutionResult
    ):
        raise ValueError("invalid quickfile definition")

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if (
            request.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
            or not isinstance(payload, QuickfileRequest)
            or context.frontend is not OperationFrontendProjection.CLI
            or context.authority_operation is None
            or context.contract.definition_id != QUICKFILE_OPERATION_DEFINITION_ID
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if (
            payload.profile_id != context.profile_id
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or (payload.bucket_id is not None and payload.bucket_id != payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        periods = frozenset({payload.period.to_period()})
        admitted = context.admitted_request
        if admitted is not None and (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != request.definition_id
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods != periods
            or admitted.period_independent
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset[DisclosurePermission]()
        if context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                DisclosurePermission(
                    destination_id=context.destination_id, projection_id=schema.schema_id, category=category
                )
                for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
            )
        elif context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=False,
                destination_id=context.destination_id,
            ),
            policy=OperationAccessPolicy(
                definition_id=request.definition_id,
                definition_contract_digest=context.contract.definition_contract_digest,
                actions=frozenset(
                    {
                        AccessAction.SUBMIT,
                        AccessAction.START,
                        AccessAction.RESUME,
                        AccessAction.RESULT,
                        AccessAction.OBSERVE,
                        AccessAction.COMMIT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                ),
                disclosures=disclosures,
                periods=periods,
                allow_period_independent=False,
                requires_all_periods=False,
                requires_human=True,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                # Write authority is checked at each admitted transaction seam;
                # this flag would unconditionally refuse ordinary operation access.
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=QuickfileRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=QuickfileProjection
        ),
        access_resolver=resolve,
        result_projector=project_quickfile_result,
    )
