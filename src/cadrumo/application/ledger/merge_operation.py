"""Registered exact-profile execution of one manual ledger merge."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import HEX_ALPHABET
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import SplitRole, TransactionLifecycleState
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, terminal_receipt_matches
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import resolve_revision_guarded_transaction_repository
from .actions_split_merge import merge_transactions
from .id_resolution import resolve_transaction_id
from .models import MergeTransactionsResult
from .pinned_transaction_repository import PinnedRevisionedTransactionRepository
from .read_access import resolve_ledger_read_access

LEDGER_MERGE_OPERATION_DEFINITION_ID = "ledger.merge"
LEDGER_MERGE_PHASE = "ledger.merge"
_MAX_MERGE_CHILDREN = 128
_MAX_MERGE_RESULT_JSON_BYTES = 16_384
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_Reason = Annotated[str, Field(max_length=500)]
_Actor = Annotated[str, Field(min_length=1, max_length=64)]
_ChildPrefixes = Annotated[tuple[_TransactionPrefix, ...], Field(min_length=2, max_length=_MAX_MERGE_CHILDREN)]
_TransactionIds = Annotated[tuple[TransactionId, ...], Field(min_length=2, max_length=_MAX_MERGE_CHILDREN)]


class LedgerMergeRequest(BaseModel):
    """Exact-profile manual merge input, retaining only bounded id prefixes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    child_ids: _ChildPrefixes
    reason: _Reason = ""
    actor: _Actor | None = None

    @field_validator("child_ids")
    @classmethod
    def _canonical_child_prefixes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for value in values:
            prefix = value.strip().lower()
            if not prefix or len(prefix) > 64 or not HEX_ALPHABET.issuperset(prefix):
                raise ValueError("ledger merge child ids must be hexadecimal transaction prefixes")
            normalized.append(prefix)
        return tuple(normalized)

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("actor")
    @classmethod
    def _trim_actor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("ledger merge actor must not be blank")
        return trimmed

    @model_validator(mode="after")
    def _unique_child_prefixes(self) -> LedgerMergeRequest:
        if len(set(self.child_ids)) != len(self.child_ids):
            raise ValueError("ledger merge child ids must be unique")
        return self


class LedgerMergeOperationResult(BaseModel):
    """Bounded result needed by the existing merge CLI envelope."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    split_group_id: Hex64Str
    parent_transaction_id: TransactionId
    merged_transaction_id: TransactionId
    source_child_ids: _TransactionIds
    bucket_event_id: Hex64Str

    @model_validator(mode="after")
    def _unique_ids(self) -> LedgerMergeOperationResult:
        if (
            len(set(self.source_child_ids)) != len(self.source_child_ids)
            or self.parent_transaction_id in self.source_child_ids
            or self.merged_transaction_id in (self.parent_transaction_id, *self.source_child_ids)
        ):
            raise ValueError("ledger merge result ids must identify distinct transaction rows")
        return self


class LedgerMergeExecutionResult(BaseModel):
    """Private encrypted result wrapper for the manual merge worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerMergeOperationResult

    @model_validator(mode="after")
    def _same_profile(self) -> LedgerMergeExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("ledger merge execution result belongs to another profile")
        return self


class LedgerMergeExecutor:
    """Resolve every child prefix and merge against the same guarded snapshot."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile ledger port factory supplied by composition."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerMergeRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Resolve and merge the exact profile's complete current child cohort."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_MERGE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_MERGE_PHASE)

        def merge() -> LedgerMergeOperationResult:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            revisioned_repository = resolve_revision_guarded_transaction_repository(
                bucket_id=bucket_id,
                repository=ports.transaction_repository,
            )
            catalogue, revision_id = revisioned_repository.load_revisioned()
            child_ids = tuple(resolve_transaction_id(prefix, catalogue.transactions) for prefix in payload.child_ids)
            _preflight_result(profile_id=payload.profile_id, child_ids=child_ids)
            pinned_repository = PinnedRevisionedTransactionRepository(
                repository=revisioned_repository,
                catalogue=catalogue,
                revision_id=revision_id,
                action="merge",
            )
            pinned_ports = replace(ports, transaction_repository=pinned_repository)
            result = merge_transactions(
                bucket_id=bucket_id,
                child_transaction_ids=child_ids,
                actor=payload.actor or bucket_id or "operator",
                source_command="aeat app ledger merge",
                reason=payload.reason,
                ports=pinned_ports,
            )
            return _operation_result(
                profile_id=payload.profile_id,
                expected_child_ids=child_ids,
                result=result,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                projection = await asyncio.to_thread(merge)
                await context.events.effect(OperationEffect.UPDATED)
                execution = LedgerMergeExecutionResult(profile_id=payload.profile_id, result=projection)
                return await context.operands.put(execution, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-merge-commit")


def _preflight_result(*, profile_id: UUID, child_ids: tuple[str, ...]) -> None:
    """Exercise the bounded result shape and output size before persistence."""
    sorted_child_ids = tuple(sorted(child_ids))
    if len(set(sorted_child_ids)) != len(sorted_child_ids):
        raise TransactionValidationError("ledger merge child ids must resolve to unique transactions")
    occupied_ids = set(sorted_child_ids)

    def unused_transaction_id(seed: int) -> str:
        candidate = f"{seed:064x}"
        while candidate in occupied_ids:
            seed += 1
            candidate = f"{seed:064x}"
        occupied_ids.add(candidate)
        return candidate

    projection = LedgerMergeOperationResult(
        profile_id=profile_id,
        split_group_id="a" * 64,
        parent_transaction_id=unused_transaction_id(11),
        merged_transaction_id=unused_transaction_id(12),
        source_child_ids=sorted_child_ids,
        bucket_event_id="d" * 64,
    )
    _require_result_bound(projection)


def _require_result_bound(projection: LedgerMergeOperationResult) -> None:
    """Reject a result projection larger than its registered byte bound."""
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_MERGE_RESULT_JSON_BYTES:
        raise TransactionValidationError("ledger merge result exceeds its registered projection bound")


def _operation_result(
    *,
    profile_id: UUID,
    expected_child_ids: tuple[str, ...],
    result: MergeTransactionsResult,
) -> LedgerMergeOperationResult:
    """Correlate the merged row, parent lineage, child cohort, and event."""
    expected_sorted_children = tuple(sorted(expected_child_ids))
    parent_lineage = result.parent_transaction.split_lineage
    merged_lineage = result.merged_transaction.split_lineage
    if (
        result.bucket_id != str(profile_id)
        or result.source_child_ids != expected_sorted_children
        or len(set(expected_child_ids)) != len(expected_child_ids)
        or result.parent_transaction.transaction_id != result.parent_transaction_id
        or result.merged_transaction.transaction_id != result.merged_transaction_id
        or parent_lineage is None
        or parent_lineage.role is not SplitRole.PARENT
        or parent_lineage.split_group_id != result.split_group_id
        or parent_lineage.sibling_transaction_ids != expected_sorted_children
        or result.parent_transaction.lifecycle_state is not TransactionLifecycleState.ARCHIVED
        or merged_lineage is None
        or merged_lineage.role is not SplitRole.MERGED
        or merged_lineage.split_group_id != result.split_group_id
        or merged_lineage.sibling_transaction_ids != expected_sorted_children
        or result.merged_transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    projection = LedgerMergeOperationResult(
        profile_id=profile_id,
        split_group_id=result.split_group_id,
        parent_transaction_id=result.parent_transaction_id,
        merged_transaction_id=result.merged_transaction_id,
        source_child_ids=result.source_child_ids,
        bucket_event_id=result.bucket_event_id,
    )
    _require_result_bound(projection)
    return projection


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerMergeExecutionResult or not terminal_receipt_matches(
        receipt,
        definition_id=LEDGER_MERGE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
    ):
        raise ValueError("ledger merge result has an incompatible terminal receipt")
    return result.result


def build_ledger_merge_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare durable, exact-profile manual merge with a bounded result."""
    return OperationDefinition(
        definition_id=LEDGER_MERGE_OPERATION_DEFINITION_ID,
        request_type=LedgerMergeRequest,
        result_type=LedgerMergeExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerMergeRequest,
            executor_type=LedgerMergeExecutor,
            build=lambda: LedgerMergeExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_MERGE_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_ledger_merge_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-ledger consent and COMMIT for manual merge."""
    if request.definition_id != LEDGER_MERGE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload,
        LedgerMergeRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_merge_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll secure request/result schemas and the exact-profile access gate."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerMergeOperationResult,
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_merge_access,
    )


__all__ = [
    "LEDGER_MERGE_OPERATION_DEFINITION_ID",
    "LEDGER_MERGE_PHASE",
    "LedgerMergeExecutor",
    "LedgerMergeOperationResult",
    "LedgerMergeRequest",
    "build_ledger_merge_definition",
    "build_ledger_merge_registration",
    "resolve_ledger_merge_access",
]
