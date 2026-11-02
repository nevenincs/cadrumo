"""Registered read that tries an unsaved rule pattern with the rule engine; it writes nothing."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.transactions.classification_rule import description_pattern_error, description_pattern_matches
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_classification import classification_rule_in_scope
from .read_access import resolve_ledger_read_access
from .transaction_repository import transaction_catalogue_repository

LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID: Final = "ledger.rule.trial"

_MAX_TRANSACTIONS: Final = 50_000

RuleTrialOutcome = Literal["matched", "empty_pattern", "invalid_pattern"]


class LedgerRuleTrialRequest(BaseModel):
    """A pattern not yet saved, and the movements to try it on."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    description_pattern: str
    transaction_ids: Annotated[tuple[str, ...], Field(max_length=_MAX_TRANSACTIONS)] = ()


class LedgerRuleTrialResult(BaseModel):
    """Whether the engine reads the pattern, which active movements it finds, and which it would classify now."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: RuleTrialOutcome
    hits: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()


class LedgerRuleTrialExecutionResult(BaseModel):
    """Worker-side envelope of the answer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerRuleTrialResult


def try_rule_pattern(
    profile_id: UUID,
    description_pattern: str,
    transactions: Mapping[str, Transaction],
) -> LedgerRuleTrialResult:
    """Answer as saving and applying the pattern would: refused the same way, matched by the same engine."""
    if not description_pattern.strip():
        return LedgerRuleTrialResult(profile_id=profile_id, outcome="empty_pattern")
    if description_pattern_error(description_pattern) is not None:
        return LedgerRuleTrialResult(profile_id=profile_id, outcome="invalid_pattern")
    found = {
        transaction_id: transaction
        for transaction_id, transaction in transactions.items()
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and description_pattern_matches(description_pattern, transaction.raw.description)
    }
    return LedgerRuleTrialResult(
        profile_id=profile_id,
        outcome="matched",
        hits=tuple(found),
        pending=tuple(
            transaction_id
            for transaction_id, transaction in found.items()
            if classification_rule_in_scope(transaction, reaffirm=False)
        ),
    )


class LedgerRuleTrialExecutor:
    """Try a pattern inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[LedgerRuleTrialRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then decrypt only the named movements and try the pattern on them."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID
            or context.identity.definition_id != LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID)

        def answer() -> LedgerRuleTrialResult:
            repository = transaction_catalogue_repository(bucket_id=bucket_id)
            transactions = (
                repository.load_by_ids(payload.transaction_ids).transactions if payload.transaction_ids else {}
            )
            return try_rule_pattern(payload.profile_id, payload.description_pattern, transactions)

        result = await asyncio.to_thread(answer)
        return await context.operands.put(LedgerRuleTrialExecutionResult(result=result), written_at=now())


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerRuleTrialExecutionResult:
        raise ValueError("invalid ledger rule trial result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="ledger rule trial has an incompatible terminal receipt",
    )
    return result.result


def build_ledger_rule_trial_definition() -> OperationDefinition:
    """Declare the exact-profile read that tries a pattern."""
    return build_single_phase_definition(
        definition_id=LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
        request_type=LedgerRuleTrialRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerRuleTrialExecutionResult,
        executor_type=LedgerRuleTrialExecutor,
        build=LedgerRuleTrialExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_ledger_rule_trial_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every ledger read is."""
    if request.definition_id != LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerRuleTrialRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_rule_trial_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerRuleTrialResult,
        result_projector=_project_result,
        access_resolver=resolve_ledger_rule_trial_access,
    )


__all__ = [
    "LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID",
    "LedgerRuleTrialExecutionResult",
    "LedgerRuleTrialExecutor",
    "LedgerRuleTrialRequest",
    "LedgerRuleTrialResult",
    "RuleTrialOutcome",
    "build_ledger_rule_trial_definition",
    "build_ledger_rule_trial_registration",
    "resolve_ledger_rule_trial_access",
    "try_rule_pattern",
]
