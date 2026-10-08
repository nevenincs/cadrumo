"""Execute and register one exact-profile manual ledger classification.

Core types: :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
"""

from __future__ import annotations

import asyncio

from pydantic import (
    BaseModel,
)

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.models import BucketTransactionRef, TransactionCatalogue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_manual import update_manual_transaction_fields
from .classify_patch import build_manual_classification_patch
from .classify_requests import (
    LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
    LEDGER_CLASSIFY_PHASE,
    LedgerClassifyRequest,
)
from .classify_result_contracts import (
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerClassifyExecutionResult,
    LedgerClassifyOperationResult,
)
from .classify_result_projection import classification_result_from_action, project_classify_operation_result
from .classify_validation import (
    LEDGER_CLASSIFY_VALIDATION_ERRORS,
    classify_validation_kind,
    classify_validation_messages,
)
from .id_resolution import resolve_transaction_id
from .models import (
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from .read_access import resolve_ledger_commit_access


class LedgerClassifyExecutor:
    """Apply one manual classify through the canonical ledger action."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile ledger service composition."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerClassifyRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve current state, validate, and commit inside one COMMIT section."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_CLASSIFY_PHASE)

        def prepare() -> tuple[LedgerActionPorts, TransactionCatalogue, str, ManualLedgerTransactionPatch]:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            catalogue = ports.transaction_repository.load()
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            current = catalogue.transactions[transaction_id]
            patch = build_manual_classification_patch(
                payload,
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                current=current,
                operation=operation,
                catalogue=catalogue,
            )
            # Validate the full pre-write projection now. Every request value that
            # can change the projection is bounded by the request schema and its
            # canonical domain validator, so the same projection cannot first fail
            # after the durable update.
            classification_result_from_action(
                payload.profile_id,
                ManualLedgerTransactionResult(
                    ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction_id),
                    transaction=current,
                    bucket_event_ids=(),
                ),
            )
            return ports, catalogue, transaction_id, patch

        async def refuse(error: Exception) -> OperationRefusalEvidence:
            detail = LedgerClassifyExecutionResult(
                outcome="validation_error",
                profile_id=payload.profile_id,
                validation_kind=classify_validation_kind(error),
                validation_messages=classify_validation_messages(error),
            )
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                try:
                    ports, catalogue, transaction_id, patch = await asyncio.to_thread(prepare)
                except LEDGER_CLASSIFY_VALIDATION_ERRORS as exc:
                    return await refuse(exc)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        update_manual_transaction_fields,
                        bucket_id=bucket_id,
                        transaction_id=transaction_id,
                        patch=patch,
                        actor=payload.actor or bucket_id or "operator",
                        source_command="aeat app ledger classify",
                        reaffirm=payload.reaffirm,
                        ports=ports,
                        catalogue=catalogue,
                        expected_current=catalogue.transactions[transaction_id],
                    )
                except LEDGER_CLASSIFY_VALIDATION_ERRORS as exc:
                    # The action validates its replacement before its atomic
                    # catalogue/event commit, so this caught input refusal has
                    # a known no-write effect.
                    await context.events.effect(OperationEffect.NONE)
                    return await refuse(exc)
                projection = classification_result_from_action(payload.profile_id, result)
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                execution_result = LedgerClassifyExecutionResult(
                    outcome="classified",
                    profile_id=payload.profile_id,
                    result=projection,
                )
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-classify-commit")


def build_ledger_classify_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare a durable exact-profile classification with bounded secure result."""
    return build_single_phase_definition(
        definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        request_type=LedgerClassifyRequest,
        result_type=LedgerClassifyExecutionResult,
        executor_type=LedgerClassifyExecutor,
        build=lambda: LedgerClassifyExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_classify_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and COMMIT for single classify."""
    if request.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerClassifyRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_classify_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact classify request, bounded result, and access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerClassifyOperationResult,
        result_projector=project_classify_operation_result,
        access_resolver=resolve_ledger_classify_access,
    )


__all__ = [
    "LedgerClassifyExecutor",
    "build_ledger_classify_definition",
    "build_ledger_classify_registration",
    "resolve_ledger_classify_access",
]
