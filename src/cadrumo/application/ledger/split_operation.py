"""Registered exact-profile execution of one manual ledger split."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import HEX_ALPHABET
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
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import BusinessClassification, SplitRole
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
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
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_common import display_decimal, resolve_revision_guarded_transaction_repository
from .actions_split_merge import split_transaction
from .id_resolution import resolve_transaction_id
from .models import SplitChildCommand, SplitTransactionResult
from .persistence_ports import LedgerPersistenceConflictError
from .protocols import RevisionGuardedTransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_read_access

LEDGER_SPLIT_OPERATION_DEFINITION_ID = "ledger.split.manual"
LEDGER_SPLIT_PHASE = "ledger.split.manual"
_MAX_SPLIT_CHILDREN = 128
_MAX_SPLIT_RESULT_JSON_BYTES = 16_384
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_Description = Annotated[str, Field(min_length=1, max_length=1024)]
_Reason = Annotated[str, Field(max_length=500)]
_Actor = Annotated[str, Field(min_length=1, max_length=64)]
_TransactionIdText = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
_Hex64Text = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


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
    parent_transaction_id: _TransactionIdText
    split_group_id: _Hex64Text
    child_transaction_ids: Annotated[
        tuple[_TransactionIdText, ...],
        Field(min_length=2, max_length=_MAX_SPLIT_CHILDREN),
    ]
    bucket_event_id: _Hex64Text
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


@dataclass(frozen=True, slots=True)
class _PinnedRevisionedTransactionRepository:
    """Forward one already-loaded catalogue/revision to the canonical split action."""

    repository: RevisionGuardedTransactionCatalogueCoCommitWriterProtocol
    catalogue: TransactionCatalogue
    revision_id: str

    @property
    def bucket_id(self) -> str:
        return self.repository.bucket_id

    def exists(self) -> bool:
        return self.repository.exists()

    def load(self) -> TransactionCatalogue:
        return self.catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return self.repository.load_for_date_range(start, end)

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        return self.repository.load_by_ids(transaction_ids)

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return self.repository.partition_by_date_range(start, end)

    def save(self, catalogue: TransactionCatalogue) -> None:
        _ = catalogue
        raise LedgerPersistenceConflictError("ledger split requires the pinned catalogue revision")

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        _ = catalogue, extra_writes
        raise LedgerPersistenceConflictError("ledger split requires the pinned catalogue revision")

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement_transaction: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        _ = current, replacement_transaction, extra_writes
        raise LedgerPersistenceConflictError("ledger split requires the pinned catalogue revision")

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        return self.catalogue, self.revision_id

    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if expected_revision_id != self.revision_id:
            raise LedgerPersistenceConflictError("ledger split attempted to write against another snapshot")
        self.repository.save_if_revision_with_secure_object_writes(
            catalogue,
            expected_revision_id=self.revision_id,
            extra_writes=extra_writes,
        )


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
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_SPLIT_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_SPLIT_PHASE)

        def split() -> LedgerSplitOperationResult:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
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
            pinned_repository = _PinnedRevisionedTransactionRepository(
                repository=revisioned_repository,
                catalogue=catalogue,
                revision_id=revision_id,
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
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_SPLIT_RESULT_JSON_BYTES:
        raise TransactionValidationError("ledger split result exceeds its registered projection bound")


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
    if (
        result.bucket_id != str(profile_id)
        or result.parent_transaction_id != expected_parent_id
        or parent.transaction_id != expected_parent_id
        or len(child_ids) != len(expected_children)
        or len(child_transactions) != len(expected_children)
        or tuple(child.transaction_id for child in child_transactions) != child_ids
        or len(set(child_ids)) != len(child_ids)
        or parent.split_lineage is None
        or parent.split_lineage.role is not SplitRole.PARENT
        or parent.split_lineage.split_group_id != result.split_group_id
        or parent.split_lineage.sibling_transaction_ids != tuple(sorted(child_ids))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for child, command, child_id in zip(child_transactions, expected_children, child_ids, strict=True):
        lineage = child.split_lineage
        expected_siblings = (
            expected_parent_id,
            *(other for other in child_ids if other != child_id),
        )
        if (
            child.transaction_id != child_id
            or child.raw.amount != command.amount
            or child.raw.description != command.description
            or child.direction is not parent.direction
            or lineage is None
            or lineage.role is not SplitRole.CHILD
            or lineage.split_group_id != result.split_group_id
            or lineage.sibling_transaction_ids != tuple(sorted(expected_siblings))
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    projection = LedgerSplitOperationResult(
        profile_id=profile_id,
        parent_transaction_id=result.parent_transaction_id,
        split_group_id=result.split_group_id,
        child_transaction_ids=child_ids,
        bucket_event_id=result.bucket_event_id,
        parent_business_classification=parent.business_classification,
    )
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_SPLIT_RESULT_JSON_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return projection


def _require_exact_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> None:
    if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (ports.invoice_repository, ports.work_unit_repository, ports.calculation_repository):
        if getattr(repository, "bucket_id", None) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if (
        type(result) is not LedgerSplitExecutionResult
        or receipt.identity.definition_id != LEDGER_SPLIT_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.UPDATED
    ):
        raise ValueError("ledger split result has an incompatible terminal receipt")
    return result.result


def build_ledger_split_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the secure exact-profile manual split mutation."""
    return OperationDefinition(
        definition_id=LEDGER_SPLIT_OPERATION_DEFINITION_ID,
        request_type=LedgerSplitRequest,
        result_type=LedgerSplitExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerSplitRequest,
            executor_type=LedgerSplitExecutor,
            build=lambda: LedgerSplitExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_SPLIT_PHASE,),
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
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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


def build_ledger_split_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll secure request/result schemas and their exact-profile access gate."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerSplitRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerSplitOperationResult,
        ),
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
