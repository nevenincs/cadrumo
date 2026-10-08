"""Registered exact-profile execution of one manual ledger split."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import HEX_ALPHABET
from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import BusinessClassification, SplitRole
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, terminal_receipt_matches
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import display_decimal, resolve_revision_guarded_transaction_repository
from .actions_split_merge import split_transaction
from .id_resolution import resolve_transaction_id
from .models import SplitChildCommand, SplitTransactionResult
from .pinned_transaction_repository import PinnedRevisionedTransactionRepository
from .read_access import resolve_ledger_commit_access

LEDGER_SPLIT_OPERATION_DEFINITION_ID = "ledger.split.manual"
LEDGER_SPLIT_PHASE = "ledger.split.manual"
_MAX_SPLIT_CHILDREN = 128
_MAX_SPLIT_RESULT_JSON_BYTES = 16_384
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_Description = Annotated[str, Field(min_length=1, max_length=1024)]
_Reason = Annotated[str, Field(max_length=500)]
_Actor = Annotated[str, Field(min_length=1, max_length=64)]


class LedgerSplitChildRequest(BaseModel):
    """Wire-safe values for one split child."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    amount: _DecimalText
    description: _Description

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        parsed = try_parse_canonical_decimal(value, signed=True)
        if parsed is None:
            raise ValueError("split child amount must be canonical decimal text")
        if display_decimal(parsed) != value:
            raise ValueError("split child amount must use canonical decimal text")
        return value

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("split child description must not be blank")
        return trimmed


_Children = Annotated[tuple[LedgerSplitChildRequest, ...], Field(min_length=2, max_length=_MAX_SPLIT_CHILDREN)]


class LedgerSplitRequest(BaseModel):
    """Exact-profile manual split input with canonical JSON wire values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    children: _Children
    reason: _Reason = ""
    actor: _Actor | None = None

    @field_validator("transaction_id")
    @classmethod
    def _canonical_prefix(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or len(normalized) > 64 or not HEX_ALPHABET.issuperset(normalized):
            raise ValueError("ledger split transaction id must be a hexadecimal prefix")
        return normalized

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
            raise ValueError("ledger split actor must not be blank")
        return trimmed


class LedgerSplitOperationResult(BaseModel):
    """Bounded successful split projection retained by the CLI bridge."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    parent_transaction_id: TransactionId
    split_group_id: Hex64Str
    child_transaction_ids: Annotated[
        tuple[TransactionId, ...],
        Field(min_length=2, max_length=_MAX_SPLIT_CHILDREN),
    ]
    bucket_event_id: Hex64Str
    parent_business_classification: BusinessClassification

    @model_validator(mode="after")
    def _unique_child_ids(self) -> LedgerSplitOperationResult:
        if len(set(self.child_transaction_ids)) != len(self.child_transaction_ids):
            raise ValueError("ledger split result must not repeat a child transaction id")
        return self


class LedgerSplitExecutionResult(BaseModel):
    """Private encrypted result wrapper for the manual split worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    result: LedgerSplitOperationResult

    @model_validator(mode="after")
    def _same_profile(self) -> LedgerSplitExecutionResult:
        if self.result.profile_id != self.profile_id:
            raise ValueError("ledger split execution result belongs to another profile")
        return self


class LedgerSplitExecutor:
    """Resolve the prefix and commit its split under one pinned full-catalogue revision."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile port factory supplied by composition."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerSplitRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Resolve and mutate the exact profile's current split cohort."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_SPLIT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_SPLIT_PHASE)

        def split() -> LedgerSplitOperationResult:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            revisioned_repository = resolve_revision_guarded_transaction_repository(
                bucket_id=bucket_id,
                repository=ports.transaction_repository,
            )
            catalogue, revision_id = revisioned_repository.load_revisioned()
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            current = catalogue.transactions[transaction_id]
            children = tuple(
                SplitChildCommand(
                    amount=_decode_decimal(child.amount),
                    description=child.description,
                )
                for child in payload.children
            )
            _preflight_result(
                profile_id=payload.profile_id,
                parent_transaction_id=transaction_id,
                child_count=len(children),
                parent_business_classification=current.business_classification,
            )
            pinned_repository = PinnedRevisionedTransactionRepository(
                repository=revisioned_repository,
                catalogue=catalogue,
                revision_id=revision_id,
                action="split",
            )
            pinned_ports = replace(ports, transaction_repository=pinned_repository)
            result = split_transaction(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                children=children,
                actor=payload.actor or bucket_id or "operator",
                source_command="aeat app ledger split",
                reason=payload.reason,
                ports=pinned_ports,
            )
            return _operation_result(
                profile_id=payload.profile_id,
                expected_parent_id=transaction_id,
                expected_children=children,
                result=result,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                projection = await asyncio.to_thread(split)
                await context.events.effect(OperationEffect.UPDATED)
                execution = LedgerSplitExecutionResult(profile_id=payload.profile_id, result=projection)
                return await context.operands.put(execution, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-split-commit")


def _decode_decimal(value: str) -> Decimal:
    parsed = try_parse_canonical_decimal(value, signed=True)
    if parsed is None:
        raise TransactionValidationError("split child amount must be canonical decimal text")
    return parsed


def _preflight_result(
    *,
    profile_id: UUID,
    parent_transaction_id: str,
    child_count: int,
    parent_business_classification: BusinessClassification,
) -> None:
    """Exercise the bounded result model and size ceiling before the durable action."""
    placeholder_ids = tuple(f"{index:064x}" for index in range(1, child_count + 1))
    projection = LedgerSplitOperationResult(
        profile_id=profile_id,
        parent_transaction_id=parent_transaction_id,
        split_group_id="a" * 64,
        child_transaction_ids=placeholder_ids,
        bucket_event_id="b" * 64,
        parent_business_classification=parent_business_classification,
    )
    _require_result_bound(projection)


def _require_result_bound(projection: LedgerSplitOperationResult) -> None:
    """Reject a result projection larger than its registered byte bound."""
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_SPLIT_RESULT_JSON_BYTES:
        raise TransactionValidationError("ledger split result exceeds its registered projection bound")


def _require_split_action_identity(
    *,
    profile_id: UUID,
    expected_parent_id: str,
    expected_child_count: int,
    result: SplitTransactionResult,
    child_ids: tuple[str, ...],
    child_transactions: tuple[Transaction, ...],
) -> None:
    parent = result.parent_transaction
    if (
        result.bucket_id != str(profile_id)
        or result.parent_transaction_id != expected_parent_id
        or parent.transaction_id != expected_parent_id
        or len(child_ids) != expected_child_count
        or len(child_transactions) != expected_child_count
        or tuple(child.transaction_id for child in child_transactions) != child_ids
        or len(set(child_ids)) != len(child_ids)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_parent_split_lineage(
    parent: Transaction,
    *,
    split_group_id: str,
    child_ids: tuple[str, ...],
) -> None:
    lineage = parent.split_lineage
    if (
        lineage is None
        or lineage.role is not SplitRole.PARENT
        or lineage.split_group_id != split_group_id
        or lineage.sibling_transaction_ids != tuple(sorted(child_ids))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_child_split_action(
    child: Transaction,
    command: SplitChildCommand,
    *,
    child_id: str,
    parent: Transaction,
) -> None:
    if (
        child.transaction_id != child_id
        or child.raw.amount != command.amount
        or child.raw.description != command.description
        or child.direction is not parent.direction
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_child_split_lineage(
    child: Transaction,
    *,
    child_id: str,
    child_ids: tuple[str, ...],
    expected_parent_id: str,
    split_group_id: str,
) -> None:
    lineage = child.split_lineage
    expected_siblings = (
        expected_parent_id,
        *(other for other in child_ids if other != child_id),
    )
    if (
        lineage is None
        or lineage.role is not SplitRole.CHILD
        or lineage.split_group_id != split_group_id
        or lineage.sibling_transaction_ids != tuple(sorted(expected_siblings))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _operation_result(
    *,
    profile_id: UUID,
    expected_parent_id: str,
    expected_children: tuple[SplitChildCommand, ...],
    result: SplitTransactionResult,
) -> LedgerSplitOperationResult:
    """Correlate every returned child against the action's exact committed split."""
    parent = result.parent_transaction
    child_ids = tuple(result.child_transaction_ids)
    child_transactions = tuple(result.child_transactions)
    _require_split_action_identity(
        profile_id=profile_id,
        expected_parent_id=expected_parent_id,
        expected_child_count=len(expected_children),
        result=result,
        child_ids=child_ids,
        child_transactions=child_transactions,
    )
    _require_parent_split_lineage(parent, split_group_id=result.split_group_id, child_ids=child_ids)
    for child, command, child_id in zip(child_transactions, expected_children, child_ids, strict=True):
        _require_child_split_action(
            child,
            command,
            child_id=child_id,
            parent=parent,
        )
        _require_child_split_lineage(
            child,
            child_id=child_id,
            child_ids=child_ids,
            expected_parent_id=expected_parent_id,
            split_group_id=result.split_group_id,
        )
    projection = LedgerSplitOperationResult(
        profile_id=profile_id,
        parent_transaction_id=result.parent_transaction_id,
        split_group_id=result.split_group_id,
        child_transaction_ids=child_ids,
        bucket_event_id=result.bucket_event_id,
        parent_business_classification=parent.business_classification,
    )
    _require_result_bound(projection)
    return projection


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerSplitExecutionResult or not terminal_receipt_matches(
        receipt,
        definition_id=LEDGER_SPLIT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
    ):
        raise ValueError("ledger split result has an incompatible terminal receipt")
    return result.result


def build_ledger_split_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the secure exact-profile manual split mutation."""
    return build_single_phase_definition(
        definition_id=LEDGER_SPLIT_OPERATION_DEFINITION_ID,
        request_type=LedgerSplitRequest,
        result_type=LedgerSplitExecutionResult,
        executor_type=LedgerSplitExecutor,
        build=lambda: LedgerSplitExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_ledger_split_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile whole-ledger consent and COMMIT for manual split."""
    if request.definition_id != LEDGER_SPLIT_OPERATION_DEFINITION_ID or not isinstance(
        request.payload,
        LedgerSplitRequest,
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_split_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll secure request/result schemas and their exact-profile access gate."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerSplitOperationResult,
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_split_access,
    )


__all__ = [
    "LEDGER_SPLIT_OPERATION_DEFINITION_ID",
    "LEDGER_SPLIT_PHASE",
    "LedgerSplitChildRequest",
    "LedgerSplitExecutor",
    "LedgerSplitOperationResult",
    "LedgerSplitRequest",
    "build_ledger_split_definition",
    "build_ledger_split_registration",
    "resolve_ledger_split_access",
]
