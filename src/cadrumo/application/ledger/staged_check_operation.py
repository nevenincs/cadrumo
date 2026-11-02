"""Registered read that answers staged ledger work; it writes nothing."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.transactions.models import TransactionCatalogue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .read_access import resolve_ledger_request_read_access
from .staged_check import check_staged_work
from .staged_check_contracts import (
    LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
    LedgerStagedCheckExecutionResult,
    LedgerStagedCheckRequest,
    LedgerStagedCheckResult,
)
from .transaction_repository import transaction_catalogue_repository


def _named_rows(request: LedgerStagedCheckRequest, *, bucket_id: str) -> TransactionCatalogue | None:
    """Decrypt only the rows the request names; an unknown id is simply absent."""
    if not request.rows:
        return None
    repository = transaction_catalogue_repository(bucket_id=bucket_id)
    return repository.load_by_ids(row.transaction_id for row in request.rows)


class LedgerStagedCheckExecutor:
    """Answer staged work inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[LedgerStagedCheckRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer from its stored rows and the pinned authority."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID)

        def answer() -> LedgerStagedCheckResult:
            catalogue = _named_rows(payload, bucket_id=bucket_id)
            return check_staged_work(
                payload,
                dict(catalogue.transactions) if catalogue is not None else {},
                operation=context.authority_operation,
                profile_id=payload.profile_id,
            )

        result = await asyncio.to_thread(answer)
        return await context.operands.put(LedgerStagedCheckExecutionResult(result=result), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerStagedCheckExecutionResult:
        raise ValueError("invalid ledger staged check result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger staged check has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_staged_check_definition() -> OperationDefinition:
    """Declare the exact-profile read of staged ledger work."""
    return build_single_phase_definition(
        definition_id=LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
        request_type=LedgerStagedCheckRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerStagedCheckExecutionResult,
        executor_type=LedgerStagedCheckExecutor,
        build=LedgerStagedCheckExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_staged_check_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
        request_type=LedgerStagedCheckRequest,
    )


def build_ledger_staged_check_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerStagedCheckResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_staged_check_access,
    )


__all__ = [
    "LedgerStagedCheckExecutor",
    "build_ledger_staged_check_definition",
    "build_ledger_staged_check_registration",
    "resolve_ledger_staged_check_access",
]
