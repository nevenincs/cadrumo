"""Registered exact-profile CSV classification through canonical batch custody."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core.errors.hierarchy import InternalInvariantError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_classification import bulk_classify_from_csv
from .commit_fence import (
    LedgerCommitAttemptTracker,
    RevisionGuardedTrackedLedgerTransactionRepository,
    run_with_ledger_commit_fence,
)
from .models import BulkClassifyResult
from .protocols import RevisionGuardedTransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_read_access

LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID = "ledger.classify.bulk"
LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
_VALIDATION_ERRORS = (TransactionValidationError, RegistryValidationError, ValidationError, ValueError)


def _require_complete_result(result: BulkClassifyResult) -> None:
    if result.total != result.applied + result.skipped + len(result.failures):
        raise ValueError("CSV classification result counts do not cover every row")
    if bool(result.applied) != bool(result.bucket_event_ids):
        raise ValueError("CSV classification applied rows and canonical events disagree")


def _require_validation_messages(messages: tuple[str, ...]) -> None:
    if not messages or any(not message for message in messages):
        raise ValueError("CSV classification validation refusal requires only its messages")


class LedgerBulkClassifyRequest(BaseModel):
    """Transient CSV operand retained only through encrypted request custody.

    The shared submission protocol bounds the complete encoded UTF-8 request.
    CSV rows remain governed by the canonical classification service.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    csv_text: Annotated[str, Field(max_length=SUBMISSION_PAYLOAD_MAX_BYTES, repr=False)]
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None


class LedgerBulkClassifyProjection(BaseModel):
    """Complete private batch result or a guaranteed pre-write input refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["classified", "validation_error"]
    result: BulkClassifyResult | None = None
    validation_messages: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerBulkClassifyProjection:
        if self.outcome == "classified":
            if self.result is None or self.validation_messages:
                raise ValueError("CSV classification success requires its complete canonical result")
            _require_complete_result(self.result)
        elif self.result is not None:
            raise ValueError("CSV classification validation refusal requires only its messages")
        else:
            _require_validation_messages(self.validation_messages)
        return self


class LedgerBulkClassifyExecutionResult(BaseModel):
    """Encrypted worker result, including the exact-profile private projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: LedgerBulkClassifyProjection


def _require_revision_guarded_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> RevisionGuardedTransactionCatalogueCoCommitWriterProtocol:
    require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
    if not isinstance(ports.transaction_repository, RevisionGuardedTransactionCatalogueCoCommitWriterProtocol):
        raise InternalInvariantError("CSV classification requires revision-guarded catalogue custody")
    return ports.transaction_repository


class LedgerBulkClassifyExecutor:
    """Run one canonical CSV batch with authority only at concrete writer entry."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the trusted exact-profile ledger composition."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerBulkClassifyRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Preserve batch row outcomes and classify effects from persistence receipts."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID)
        operation = context.authority_operation
        ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
        repository = _require_revision_guarded_ports(ports, bucket_id=bucket_id, operation=operation)
        tracker = LedgerCommitAttemptTracker()
        tracked_ports = replace(
            ports,
            transaction_repository=RevisionGuardedTrackedLedgerTransactionRepository(repository, tracker),
        )
        try:
            result = await run_with_ledger_commit_fence(
                lambda: bulk_classify_from_csv(
                    bucket_id=bucket_id,
                    csv_text=payload.csv_text,
                    actor=payload.actor or bucket_id,
                    source_command="aeat app ledger classify --file",
                    ports=tracked_ports,
                ),
                tracker=tracker,
                context=context,
                task_name=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
            )
        except _VALIDATION_ERRORS as error:
            if tracker.attempt_count or tracker.has_possible_write:
                raise
            await context.events.effect(OperationEffect.NONE)
            projection = LedgerBulkClassifyProjection(
                profile_id=payload.profile_id,
                outcome="validation_error",
                validation_messages=(str(error) or "CSV classification input is invalid",),
            )
            detail_ref = await context.operands.put(
                LedgerBulkClassifyExecutionResult(projection=projection), written_at=now()
            )
            return OperationRefusalEvidence(
                refusal_code=LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref
            )
        if tracker.has_uncertain_write or bool(result.bucket_event_ids) != tracker.confirmed_write:
            raise InternalInvariantError("CSV classification writer receipt disagrees with its canonical result")
        effect = OperationEffect.UPDATED if tracker.confirmed_write else OperationEffect.NONE
        await context.events.effect(effect)
        projection = LedgerBulkClassifyProjection(profile_id=payload.profile_id, outcome="classified", result=result)
        return await context.operands.put(LedgerBulkClassifyExecutionResult(projection=projection), written_at=now())


def _require_matching_result_identity(
    result: BaseModel, receipt: OperationTerminalReceipt
) -> LedgerBulkClassifyProjection:
    if (
        type(result) is not LedgerBulkClassifyExecutionResult
        or receipt.identity.definition_id != LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid CSV classification result or terminal definition")
    projection = result.projection
    if receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id)):
        raise ValueError("CSV classification result belongs to another profile")
    return projection


def _require_success_receipt(receipt: OperationTerminalReceipt, expected_effect: OperationEffect) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.diagnostic_ref is not None
        or receipt.effect is not expected_effect
    ):
        raise ValueError("CSV classification success has an incompatible terminal receipt")


def _require_refusal_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("CSV classification validation refusal has an incompatible terminal receipt")


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    projection = _require_matching_result_identity(result, receipt)
    if projection.outcome == "classified":
        expected_effect = (
            OperationEffect.UPDATED
            if projection.result and projection.result.bucket_event_ids
            else OperationEffect.NONE
        )
        _require_success_receipt(receipt, expected_effect)
    else:
        _require_refusal_receipt(receipt)
    return projection


def build_ledger_bulk_classify_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare exact-profile CLI classification with protected request and result."""
    return OperationDefinition(
        definition_id=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
        request_type=LedgerBulkClassifyRequest,
        result_type=LedgerBulkClassifyExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerBulkClassifyRequest,
            executor_type=LedgerBulkClassifyExecutor,
            build=lambda: LedgerBulkClassifyExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_bulk_classify_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require the exact profile, all-period disclosure and mutation authority."""
    if (
        request.definition_id != LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID
        or context.frontend is not OperationFrontendProjection.CLI
        or not isinstance(request.payload, LedgerBulkClassifyRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_bulk_classify_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll complete CSV row outcomes through the protected CLI projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerBulkClassifyProjection,
        result_projector=_project_result,
        access_resolver=resolve_ledger_bulk_classify_access,
    )
