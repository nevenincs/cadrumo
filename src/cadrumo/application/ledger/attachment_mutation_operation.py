"""Exact-profile registered attachment and detachment of ledger evidence."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.identity.transaction_ids import TransactionId
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
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import (
    TransactionIdPrefixError,
    TransactionNotFoundError,
    TransactionValidationError,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..review.filter import LedgerReviewStatus
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_manual import (
    attach_manual_transaction_evidence,
    detach_manual_transaction_attachments,
    ledger_transaction_result_payload,
)
from .id_resolution import resolve_transaction_id
from .models import LedgerRemovalBlocker, ManualLedgerTransactionResult
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_ATTACH_OPERATION_DEFINITION_ID = "ledger.attach"
LEDGER_DETACH_OPERATION_DEFINITION_ID = "ledger.detach"
LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE = "REFUSED_LEDGER_ATTACHMENT_VALIDATION"
LedgerAttachmentOperationId = Literal["ledger.attach", "ledger.detach"]

_MAX_ATTACHMENT_IDS = 256
_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096
_MAX_VALIDATION_MESSAGES = 16
_MAX_VALIDATION_MESSAGE_LENGTH = 2048
_AttachmentId = Annotated[str, Field(min_length=1, max_length=64)]
_AttachmentIds = Annotated[tuple[_AttachmentId, ...], Field(max_length=_MAX_ATTACHMENT_IDS)]
_EvidenceId = Annotated[str, Field(min_length=1, max_length=64)]
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=64)]
_Actor = Annotated[str, Field(min_length=1, max_length=64)]
_EventId = Annotated[str, Field(min_length=1, max_length=64)]
# One invoice-evidence event may accompany each of the 256 attachment-link
# events accepted by a single attach request.
_EventIds = Annotated[tuple[_EventId, ...], Field(max_length=_MAX_ATTACHMENT_IDS + 1)]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=_MAX_VALIDATION_MESSAGE_LENGTH)]


class LedgerAttachmentValidationRefusedError(CadrumoError):
    """A canonical attachment mutation rejected before its transaction/event commit."""

    def __init__(self, validation_messages: tuple[str, ...]) -> None:
        """Retain bounded canonical validation facts for the CLI error envelope."""
        super().__init__(context={"validation_messages": list(validation_messages)})


class LedgerAttachRequest(BaseModel):
    """Private exact-profile request matching ``ledger attach``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    purchase_invoice_evidence_id: _EvidenceId | None = None
    attachment_ids: _AttachmentIds = ()
    actor: _Actor | None = None


class LedgerDetachRequest(BaseModel):
    """Private exact-profile request matching ``ledger detach``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    attachment_ids: Annotated[tuple[_AttachmentId, ...], Field(min_length=1, max_length=256)]
    actor: _Actor | None = None


class LedgerAttachmentStaleRevisionProjection(BaseModel):
    """Every finalized revision that will not receive the changed evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    revision_state: str = Field(min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)

    @classmethod
    def from_blocker(cls, blocker: LedgerRemovalBlocker) -> LedgerAttachmentStaleRevisionProjection:
        """Preserve all canonical blocker facts for the operator notice."""
        return cls(
            work_unit_id=blocker.work_unit_id,
            calculation_revision_id=blocker.calculation_revision_id,
            revision_state=blocker.revision_state,
            modelo=blocker.modelo,
            filing_year=blocker.filing_year,
            period=blocker.period,
        )


class LedgerAttachmentProjection(BaseModel):
    """Full public transaction projection, mutation events, and stale revisions."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerAttachmentOperationId
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: _EventIds
    stale_finalized_revisions: Annotated[
        tuple[LedgerAttachmentStaleRevisionProjection, ...],
        Field(max_length=4096),
    ] = ()


class LedgerAttachmentOperationResult(BaseModel):
    """Success projection or field-safe pre-write refusal detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    operation_id: LedgerAttachmentOperationId
    result: LedgerAttachmentProjection | None = None
    validation_messages: Annotated[
        tuple[_ValidationMessage, ...],
        Field(max_length=_MAX_VALIDATION_MESSAGES),
    ] = ()

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerAttachmentOperationResult:
        if self.outcome == "updated":
            if (
                self.result is None
                or self.result.profile_id != self.profile_id
                or self.result.operation_id != self.operation_id
                or self.validation_messages
            ):
                raise ValueError("attachment success result is incomplete or mismatched")
        elif self.result is not None or not self.validation_messages:
            raise ValueError("attachment validation refusal requires only bounded messages")
        return self


class LedgerAttachmentExecutionResult(BaseModel):
    """Private encrypted wrapper whose public result is checked against its receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerAttachmentOperationResult


class _PreparedAttachmentMutation(BaseModel):
    """Resolved exact-profile ports and full transaction id before commit entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerAttachmentOperationId
    transaction_id: TransactionId


class _LedgerAttachmentExecutor:
    """Shared canonical-service boundary used by the attach and detach executors."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        *,
        operation_id: LedgerAttachmentOperationId,
    ) -> None:
        """Bind one action identity and the existing profile-bound ledger ports."""
        self._ports_factory = ports_factory
        self._operation_id: LedgerAttachmentOperationId = operation_id

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve exact-profile inputs, call one canonical action, and record its effect."""
        payload = request.payload
        bucket_id = str(getattr(payload, "profile_id", ""))
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != self._operation_id
            or context.identity.definition_id != self._operation_id
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
            or not isinstance(payload, (LedgerAttachRequest, LedgerDetachRequest))
            or (
                self._operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID
                and not isinstance(payload, LedgerAttachRequest)
            )
            or (
                self._operation_id == LEDGER_DETACH_OPERATION_DEFINITION_ID
                and not isinstance(payload, LedgerDetachRequest)
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._operation_id)

        operation: PinnedAuthorityOperation = context.authority_operation
        ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
        _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
        try:
            catalogue = await asyncio.to_thread(ports.transaction_repository.load)
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
        except TransactionIdPrefixError as error:
            refused = _validation_result(payload.profile_id, self._operation_id, error)
            return await _publish_refusal(context, refused)

        prepared = _PreparedAttachmentMutation(
            profile_id=payload.profile_id,
            operation_id=self._operation_id,
            transaction_id=transaction_id,
        )

        async def commit() -> LedgerAttachmentOperationResult:
            async with context.cancellation.irreversible_section():
                # The canonical action co-commits transaction + bucket event.
                # Attach then writes one or more manifests. A later manifest
                # failure is known partial; other post-entry failures stay unknown.
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        self._apply,
                        payload=payload,
                        ports=ports,
                        bucket_id=bucket_id,
                        transaction_id=prepared.transaction_id,
                    )
                except (TransactionValidationError, TransactionNotFoundError) as error:
                    await context.events.effect(OperationEffect.NONE)
                    return _validation_result(payload.profile_id, self._operation_id, error)
                except (AttachmentNotFoundError, AttachmentValidationError):
                    # The canonical attach action translates these errors during
                    # its read-only preflight. If they escape the service, its
                    # transaction/event commit has already completed and a
                    # reverse manifest update was the failing later step.
                    if self._operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID:
                        await context.events.effect(OperationEffect.PARTIAL)
                    raise

                # The canonical service has now returned after its transaction,
                # event, and any attachment-manifest writes completed. Record
                # that durable outcome before building a frontend projection;
                # projection or size errors cannot make the write uncertain.
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                projection = _operation_projection(
                    payload.profile_id,
                    self._operation_id,
                    result,
                )
                operation_result = LedgerAttachmentOperationResult(
                    outcome="updated",
                    profile_id=payload.profile_id,
                    operation_id=self._operation_id,
                    result=projection,
                )
                _check_result_size(LedgerAttachmentExecutionResult(result=operation_result))
                return operation_result

        settled = await await_cancellation_complete(commit(), task_name=self._operation_id)
        execution_result = LedgerAttachmentExecutionResult(result=settled)
        if settled.outcome == "validation_error":
            detail_ref = await context.operands.put(execution_result, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )
        return await context.operands.put(execution_result, written_at=now())

    def _apply(
        self,
        *,
        payload: LedgerAttachRequest | LedgerDetachRequest,
        ports: LedgerActionPorts,
        bucket_id: str,
        transaction_id: str,
    ) -> ManualLedgerTransactionResult:
        actor = payload.actor or bucket_id or "operator"
        if self._operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID:
            if not isinstance(payload, LedgerAttachRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return attach_manual_transaction_evidence(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                purchase_invoice_evidence_id=payload.purchase_invoice_evidence_id,
                attachment_ids=payload.attachment_ids,
                actor=actor,
                source_command="aeat app ledger attach",
                ports=ports,
            )
        if not isinstance(payload, LedgerDetachRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return detach_manual_transaction_attachments(
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            attachment_ids=payload.attachment_ids,
            actor=actor,
            source_command="aeat app ledger detach",
            ports=ports,
        )


async def _publish_refusal(
    context: OperationExecutorContext,
    result: LedgerAttachmentOperationResult,
) -> OperationRefusalEvidence:
    """Store one field-safe pre-write refusal and settle its known empty effect."""
    await context.events.effect(OperationEffect.NONE)
    execution_result = LedgerAttachmentExecutionResult(result=result)
    _check_result_size(execution_result)
    detail_ref = await context.operands.put(execution_result, written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


class LedgerAttachExecutor(_LedgerAttachmentExecutor):
    """Execute the existing canonical evidence attach action."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Bind this executor to the profile-specific ledger ports factory."""
        super().__init__(ports_factory, operation_id=LEDGER_ATTACH_OPERATION_DEFINITION_ID)


class LedgerDetachExecutor(_LedgerAttachmentExecutor):
    """Execute the existing canonical attachment detach action."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Bind this executor to the profile-specific ledger ports factory."""
        super().__init__(ports_factory, operation_id=LEDGER_DETACH_OPERATION_DEFINITION_ID)


def _require_exact_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse service ports that escaped the requested profile or registry pin."""
    if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (ports.invoice_repository, ports.work_unit_repository, ports.calculation_repository):
        if getattr(repository, "bucket_id", None) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _operation_projection(
    profile_id: UUID,
    operation_id: LedgerAttachmentOperationId,
    result: ManualLedgerTransactionResult,
) -> LedgerAttachmentProjection:
    """Copy the full canonical transaction result and all finalized-revision facts."""
    canonical = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.transaction.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerAttachmentProjection(
        profile_id=profile_id,
        operation_id=operation_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        stale_finalized_revisions=tuple(
            LedgerAttachmentStaleRevisionProjection.from_blocker(blocker)
            for blocker in result.stale_finalized_revisions
        ),
    )


def _validation_result(
    profile_id: UUID,
    operation_id: LedgerAttachmentOperationId,
    error: Exception,
) -> LedgerAttachmentOperationResult:
    """Retain bounded domain refusal text without exposing raw request objects."""
    message = str(error).strip()[:_MAX_VALIDATION_MESSAGE_LENGTH]
    if not message:
        message = "ledger attachment values did not satisfy canonical validation"
    return LedgerAttachmentOperationResult(
        outcome="validation_error",
        profile_id=profile_id,
        operation_id=operation_id,
        validation_messages=(message,),
    )


def _check_result_size(result: LedgerAttachmentExecutionResult) -> None:
    """Keep encrypted receipts within the bounded operation-result budget."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the result whose profile, definition, and effect match receipt."""
    if type(result) is not LedgerAttachmentExecutionResult:
        raise ValueError("invalid ledger attachment execution result")
    projected = result.result
    if (
        receipt.identity.definition_id != projected.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projected.profile_id))
    ):
        raise ValueError("ledger attachment result belongs to another operation or profile")
    if projected.outcome == "validation_error":
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref != LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
            or receipt.effect is not OperationEffect.NONE
        ):
            raise ValueError("ledger attachment refusal has an incompatible terminal receipt")
        return projected
    expected_effect = (
        OperationEffect.UPDATED if projected.result and projected.result.bucket_event_ids else OperationEffect.NONE
    )
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or projected.result is None
        or receipt.effect is not expected_effect
    ):
        raise ValueError("ledger attachment success has an incompatible terminal receipt")
    return projected


def _build_definition(
    *,
    operation_id: LedgerAttachmentOperationId,
    request_type: type[BaseModel],
    executor_type: type[LedgerAttachExecutor] | type[LedgerDetachExecutor],
    ports_factory: LedgerActionPortsFactory,
) -> OperationDefinition:
    """Declare one receipt-backed exact-profile attachment action."""
    permitted_effects = {
        OperationEffect.NONE,
        OperationEffect.UPDATED,
        OperationEffect.UNKNOWN,
    }
    if operation_id == LEDGER_ATTACH_OPERATION_DEFINITION_ID:
        permitted_effects.add(OperationEffect.PARTIAL)
    return OperationDefinition(
        definition_id=operation_id,
        request_type=request_type,
        result_type=LedgerAttachmentExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=lambda: executor_type(ports_factory),
        ),
        phase_codes=(operation_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(permitted_effects),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE}),
    )


def build_ledger_attach_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare canonical ``ledger.attach`` for CLI execution."""
    return _build_definition(
        operation_id=LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        request_type=LedgerAttachRequest,
        executor_type=LedgerAttachExecutor,
        ports_factory=ports_factory,
    )


def build_ledger_detach_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare canonical ``ledger.detach`` for CLI execution."""
    return _build_definition(
        operation_id=LEDGER_DETACH_OPERATION_DEFINITION_ID,
        request_type=LedgerDetachRequest,
        executor_type=LedgerDetachExecutor,
        ports_factory=ports_factory,
    )


def _resolve_attachment_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    operation_id: LedgerAttachmentOperationId,
    request_type: type[BaseModel],
    profile_id: UUID,
) -> ResolvedOperationAccess:
    """Require full-profile read access and COMMIT for the canonical mutation."""
    if request.definition_id != operation_id or not isinstance(request.payload, request_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def resolve_ledger_attach_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile access plus COMMIT for attach."""
    if not isinstance(request.payload, LedgerAttachRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _resolve_attachment_access(
        request,
        context,
        operation_id=LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        request_type=LedgerAttachRequest,
        profile_id=request.payload.profile_id,
    )


def resolve_ledger_detach_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile access plus COMMIT for detach."""
    if not isinstance(request.payload, LedgerDetachRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _resolve_attachment_access(
        request,
        context,
        operation_id=LEDGER_DETACH_OPERATION_DEFINITION_ID,
        request_type=LedgerDetachRequest,
        profile_id=request.payload.profile_id,
    )


def build_ledger_attach_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind attach's closed schemas and exact-profile resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerAttachmentOperationResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_attach_access,
    )


def build_ledger_detach_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind detach's closed schemas and exact-profile resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerAttachmentOperationResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_detach_access,
    )


__all__ = [
    "LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE",
    "LEDGER_ATTACH_OPERATION_DEFINITION_ID",
    "LEDGER_DETACH_OPERATION_DEFINITION_ID",
    "LedgerAttachExecutor",
    "LedgerAttachRequest",
    "LedgerAttachmentExecutionResult",
    "LedgerAttachmentOperationId",
    "LedgerAttachmentOperationResult",
    "LedgerAttachmentProjection",
    "LedgerAttachmentStaleRevisionProjection",
    "LedgerAttachmentValidationRefusedError",
    "LedgerDetachExecutor",
    "LedgerDetachRequest",
    "build_ledger_attach_definition",
    "build_ledger_attach_registration",
    "build_ledger_detach_definition",
    "build_ledger_detach_registration",
    "resolve_ledger_attach_access",
    "resolve_ledger_detach_access",
]
