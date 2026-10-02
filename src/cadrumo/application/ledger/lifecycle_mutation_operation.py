"""Exact-profile registered mutations of ledger lifecycle and review state."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.filing_year import FilingYear
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
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import (
    TransactionIdPrefixError,
    TransactionNotFoundError,
    TransactionValidationError,
)
from ...domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ..operations.access_port import OperationAccessResolver
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
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_lifecycle import (
    archive_manual_transaction,
    mark_transaction_reviewed_excluded,
    restore_manual_transaction,
    stash_manual_transaction,
)
from .actions_manual import ledger_transaction_result_payload
from .id_resolution import resolve_transaction_id
from .models import LedgerRemovalBlocker, LedgerTransactionResultPayload, ManualLedgerTransactionResult
from .protocols import TransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_ARCHIVE_OPERATION_DEFINITION_ID = "ledger.archive"
LEDGER_STASH_OPERATION_DEFINITION_ID = "ledger.stash"
LEDGER_RESTORE_OPERATION_DEFINITION_ID = "ledger.restore"
LEDGER_EXCLUDE_OPERATION_DEFINITION_ID = "ledger.exclude"
LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE = "REFUSED_LEDGER_LIFECYCLE_VALIDATION"
LedgerLifecycleOperationId = Literal["ledger.archive", "ledger.stash", "ledger.restore", "ledger.exclude"]

_MAX_RESULT_BYTES = 256 * 1024
_MAX_VALIDATION_MESSAGE_LENGTH = 2048
_MAX_RECOVERY_TRANSACTION_IDS = 256
_HexId = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_Actor = Annotated[str, Field(min_length=1, max_length=64)]
_Reason = Annotated[str, Field(max_length=500)]
_EventIds = Annotated[tuple[_HexId, ...], Field(min_length=1, max_length=1)]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=_MAX_VALIDATION_MESSAGE_LENGTH)]
_RecoveryTransactionIds = Annotated[tuple[_HexId, ...], Field(max_length=_MAX_RECOVERY_TRANSACTION_IDS)]


class LedgerLifecycleValidationRefusedError(CadrumoError):
    """A lifecycle action was canonically refused before its co-commit began."""

    def __init__(self, validation: LedgerLifecycleValidationProjection) -> None:
        """Expose only the bounded message and allowlisted canonical recovery facts."""
        context: dict[str, object] = {"validation_messages": list(validation.messages)}
        if validation.transaction_id is not None:
            context["transaction_id"] = validation.transaction_id
        if validation.transaction_ids:
            context["transaction_ids"] = ",".join(validation.transaction_ids)
        if validation.transaction_ids_omitted_count:
            context["transaction_ids_omitted_count"] = str(validation.transaction_ids_omitted_count)
        if validation.blocking_reference is not None:
            blocker = validation.blocking_reference
            context.update(
                {
                    "work_unit_id": blocker.work_unit_id,
                    "calculation_revision_id": blocker.calculation_revision_id,
                    "modelo": blocker.modelo,
                    "filing_year": str(blocker.filing_year),
                    "period": blocker.period,
                },
            )
            if blocker.revision_state is not None:
                context["revision_state"] = blocker.revision_state
        if validation.blocking_reference_count is not None:
            context["blocking_reference_count"] = str(validation.blocking_reference_count)
        super().__init__(context=context)


class LedgerLifecycleMutationRequest(BaseModel):
    """Private exact-profile request shared by the four lifecycle operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    actor: _Actor | None = None
    reason: _Reason = ""


class LedgerLifecycleBlockerProjection(BaseModel):
    """The first finalized reference and recovery facts published by its guard."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    work_unit_id: _HexId
    calculation_revision_id: _HexId
    revision_state: str | None = Field(default=None, min_length=1, max_length=64)
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: str = Field(min_length=1, max_length=16)

    @classmethod
    def from_blocker(cls, blocker: LedgerRemovalBlocker) -> LedgerLifecycleBlockerProjection:
        """Retain the canonical blocker without widening its recovery facts."""
        return cls(
            work_unit_id=blocker.work_unit_id,
            calculation_revision_id=blocker.calculation_revision_id,
            revision_state=blocker.revision_state,
            modelo=blocker.modelo,
            filing_year=blocker.filing_year,
            period=blocker.period,
        )


class LedgerLifecycleValidationProjection(BaseModel):
    """Bounded canonical refusal details, including available safe recovery keys."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    messages: Annotated[tuple[_ValidationMessage, ...], Field(min_length=1, max_length=16)]
    transaction_id: _HexId | None = None
    transaction_ids: _RecoveryTransactionIds = ()
    transaction_ids_omitted_count: int = Field(default=0, ge=0)
    blocking_reference: LedgerLifecycleBlockerProjection | None = None
    blocking_reference_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _coherent_blocker_facts(self) -> LedgerLifecycleValidationProjection:
        if self.blocking_reference is None and self.blocking_reference_count is not None:
            raise ValueError("lifecycle refusal blocker count requires its canonical blocker")
        if self.blocking_reference is not None and self.blocking_reference_count is None:
            raise ValueError("lifecycle refusal blocker requires the canonical reference count")
        return self


class LedgerLifecycleMutationProjection(BaseModel):
    """Full canonical transaction, review classification, and appended event."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    bucket_event_ids: _EventIds


class LedgerLifecycleOperationResult(BaseModel):
    """Success projection or a typed, guaranteed pre-write refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    result: LedgerLifecycleMutationProjection | None = None
    validation: LedgerLifecycleValidationProjection | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerLifecycleOperationResult:
        if self.outcome == "updated":
            if (
                self.result is None
                or self.result.profile_id != self.profile_id
                or self.result.operation_id != self.operation_id
                or self.validation is not None
            ):
                raise ValueError("lifecycle success projection is incomplete or mismatched")
        elif self.result is not None or self.validation is None:
            raise ValueError("lifecycle refusal requires only bounded validation evidence")
        return self


class LedgerLifecycleExecutionResult(BaseModel):
    """Private encrypted operand whose projection is checked against its receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerLifecycleOperationResult


class _PreparedLifecycleMutation(BaseModel):
    """Resolved exact-profile service ports and full transaction identifier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    transaction_id: _HexId


class _TrackedTransactionRepository:
    """Observe entry to the canonical co-commit writer without replacing it."""

    def __init__(self, repository: TransactionCatalogueCoCommitWriterProtocol) -> None:
        self._repository = repository
        self.write_started = threading.Event()

    @property
    def bucket_id(self) -> str:
        return self._repository.bucket_id

    def exists(self) -> bool:
        return self._repository.exists()

    def load(self) -> TransactionCatalogue:
        return self._repository.load()

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return self._repository.load_for_date_range(start, end)

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        return self._repository.load_by_ids(transaction_ids)

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return self._repository.partition_by_date_range(start, end)

    def save(self, catalogue: TransactionCatalogue) -> None:
        self.write_started.set()
        self._repository.save(catalogue)

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self.write_started.set()
        self._repository.save_with_secure_object_writes(catalogue, extra_writes)

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self.write_started.set()
        self._repository.replace_if_current_with_secure_object_writes(current, replacement, extra_writes)


class _LedgerLifecycleExecutor:
    """Run one canonical lifecycle service under a retained profile worker."""

    _operation_id: LedgerLifecycleOperationId

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        payload = request.payload
        if not isinstance(payload, LedgerLifecycleMutationRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != self._operation_id
            or context.identity.definition_id != self._operation_id
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._operation_id)

        operation: PinnedAuthorityOperation = context.authority_operation
        ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
        _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
        try:
            catalogue = await asyncio.to_thread(ports.transaction_repository.load)
            transaction_id = await asyncio.to_thread(
                resolve_transaction_id,
                payload.transaction_id,
                catalogue.transactions,
            )
        except (TransactionIdPrefixError, TransactionNotFoundError, TransactionValidationError) as error:
            refused = _validation_result(
                payload.profile_id,
                self._operation_id,
                _validation_projection(error, transaction_id=None),
            )
            return await _publish_refusal(context, refused)

        prepared = _PreparedLifecycleMutation(
            profile_id=payload.profile_id,
            operation_id=self._operation_id,
            transaction_id=transaction_id,
        )
        tracked = _TrackedTransactionRepository(ports.transaction_repository)
        commit_ports = replace(ports, transaction_repository=tracked)

        async def commit() -> ManualLedgerTransactionResult | LedgerLifecycleValidationProjection:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        self._apply,
                        payload=payload,
                        ports=commit_ports,
                        bucket_id=bucket_id,
                        transaction_id=prepared.transaction_id,
                    )
                except (TransactionIdPrefixError, TransactionNotFoundError, TransactionValidationError) as error:
                    if tracked.write_started.is_set():
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return _validation_projection(error, transaction_id=prepared.transaction_id)
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE,
                )
                return result

        settled = await await_cancellation_complete(commit(), task_name=self._operation_id)
        if isinstance(settled, LedgerLifecycleValidationProjection):
            refused = LedgerLifecycleOperationResult(
                outcome="validation_error",
                profile_id=payload.profile_id,
                operation_id=self._operation_id,
                validation=settled,
            )
            detail = LedgerLifecycleExecutionResult(result=refused)
            _check_result_size(detail)
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        projection = _operation_projection(payload.profile_id, self._operation_id, settled)
        result = LedgerLifecycleOperationResult(
            outcome="updated",
            profile_id=payload.profile_id,
            operation_id=self._operation_id,
            result=projection,
        )
        execution_result = LedgerLifecycleExecutionResult(result=result)
        _check_result_size(execution_result)
        return await context.operands.put(execution_result, written_at=now())

    def _apply(
        self,
        *,
        payload: LedgerLifecycleMutationRequest,
        ports: LedgerActionPorts,
        bucket_id: str,
        transaction_id: str,
    ) -> ManualLedgerTransactionResult:
        actor = payload.actor or bucket_id or "operator"
        source_command = f"aeat app {self._operation_id.replace('.', ' ')}"
        if self._operation_id == LEDGER_ARCHIVE_OPERATION_DEFINITION_ID:
            return archive_manual_transaction(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                actor=actor,
                reason=payload.reason,
                source_command=source_command,
                ports=ports,
            )
        if self._operation_id == LEDGER_STASH_OPERATION_DEFINITION_ID:
            return stash_manual_transaction(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                actor=actor,
                reason=payload.reason,
                source_command=source_command,
                ports=ports,
            )
        if self._operation_id == LEDGER_RESTORE_OPERATION_DEFINITION_ID:
            return restore_manual_transaction(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                actor=actor,
                reason=payload.reason,
                source_command=source_command,
                ports=ports,
            )
        return mark_transaction_reviewed_excluded(
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            actor=actor,
            reason=payload.reason,
            source_command=source_command,
            transaction_repository=ports.transaction_repository,
            bucket_event_repository=ports.bucket_event_repository,
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
        )


class LedgerArchiveExecutor(_LedgerLifecycleExecutor):
    """Execute canonical ``ledger.archive``."""

    _operation_id: LedgerLifecycleOperationId = LEDGER_ARCHIVE_OPERATION_DEFINITION_ID


class LedgerStashExecutor(_LedgerLifecycleExecutor):
    """Execute canonical ``ledger.stash``."""

    _operation_id: LedgerLifecycleOperationId = LEDGER_STASH_OPERATION_DEFINITION_ID


class LedgerRestoreExecutor(_LedgerLifecycleExecutor):
    """Execute canonical ``ledger.restore``."""

    _operation_id: LedgerLifecycleOperationId = LEDGER_RESTORE_OPERATION_DEFINITION_ID


class LedgerExcludeExecutor(_LedgerLifecycleExecutor):
    """Execute canonical ``ledger.exclude``."""

    _operation_id: LedgerLifecycleOperationId = LEDGER_EXCLUDE_OPERATION_DEFINITION_ID


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


def _operation_projection(
    profile_id: UUID,
    operation_id: LedgerLifecycleOperationId,
    result: ManualLedgerTransactionResult,
) -> LedgerLifecycleMutationProjection:
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.transaction.transaction_id != canonical.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerLifecycleMutationProjection(
        profile_id=profile_id,
        operation_id=operation_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
    )


def _validation_result(
    profile_id: UUID,
    operation_id: LedgerLifecycleOperationId,
    validation: LedgerLifecycleValidationProjection,
) -> LedgerLifecycleOperationResult:
    return LedgerLifecycleOperationResult(
        outcome="validation_error",
        profile_id=profile_id,
        operation_id=operation_id,
        validation=validation,
    )


def _validation_projection(
    error: Exception,
    *,
    transaction_id: str | None,
) -> LedgerLifecycleValidationProjection:
    raw_message = str(error).strip()
    message = raw_message[:_MAX_VALIDATION_MESSAGE_LENGTH] or (
        "ledger lifecycle values did not satisfy canonical validation"
    )
    context = error.context if isinstance(error, CadrumoError) else None
    transaction_ids: tuple[str, ...] = ()
    omitted_count = 0
    raw_transaction_ids = context.get("transaction_ids") if context is not None else None
    if isinstance(raw_transaction_ids, str):
        all_transaction_ids = tuple(value for value in raw_transaction_ids.split(",") if value)
        transaction_ids = all_transaction_ids[:_MAX_RECOVERY_TRANSACTION_IDS]
        omitted_count = max(0, len(all_transaction_ids) - len(transaction_ids))

    blocker: LedgerLifecycleBlockerProjection | None = None
    blocker_count: int | None = None
    if context is not None:
        required = (
            "work_unit_id",
            "calculation_revision_id",
            "modelo",
            "filing_year",
            "period",
        )
        if all(key in context for key in required):
            filing_year = context["filing_year"]
            count = context.get("blocking_reference_count")
            if isinstance(filing_year, str) and filing_year.isdigit() and isinstance(count, str) and count.isdigit():
                # The canonical lifecycle guard publishes blocker locators and count,
                # but not its revision state. Preserve that value when supplied by
                # another canonical guard without requiring or inventing it here.
                blocker = LedgerLifecycleBlockerProjection.model_validate(
                    {
                        "work_unit_id": context["work_unit_id"],
                        "calculation_revision_id": context["calculation_revision_id"],
                        "modelo": context["modelo"],
                        "filing_year": int(filing_year),
                        "period": context["period"],
                        **(
                            {"revision_state": context["revision_state"]}
                            if isinstance(context.get("revision_state"), str)
                            else {}
                        ),
                    },
                )
                blocker_count = int(count)

    return LedgerLifecycleValidationProjection(
        messages=(message,),
        transaction_id=transaction_id,
        transaction_ids=transaction_ids,
        transaction_ids_omitted_count=omitted_count,
        blocking_reference=blocker,
        blocking_reference_count=blocker_count,
    )


async def _publish_refusal(
    context: OperationExecutorContext,
    result: LedgerLifecycleOperationResult,
) -> OperationRefusalEvidence:
    await context.events.effect(OperationEffect.NONE)
    execution_result = LedgerLifecycleExecutionResult(result=result)
    _check_result_size(execution_result)
    detail_ref = await context.operands.put(execution_result, written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


def _check_result_size(result: LedgerLifecycleExecutionResult) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES - 128:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerLifecycleExecutionResult:
        raise ValueError("invalid ledger lifecycle execution result")
    projected = result.result
    if (
        receipt.identity.definition_id != projected.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projected.profile_id))
    ):
        raise ValueError("ledger lifecycle result belongs to another operation or profile")
    if projected.outcome == "validation_error":
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref != LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
            or receipt.effect is not OperationEffect.NONE
        ):
            raise ValueError("lifecycle refusal has an incompatible terminal receipt")
        return projected
    expected_effect = OperationEffect.UPDATED
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
        raise ValueError("lifecycle success has an incompatible terminal receipt")
    return projected


def _build_definition(
    *,
    operation_id: LedgerLifecycleOperationId,
    executor_type: type[_LedgerLifecycleExecutor],
    ports_factory: LedgerActionPortsFactory,
) -> OperationDefinition:
    return OperationDefinition(
        definition_id=operation_id,
        request_type=LedgerLifecycleMutationRequest,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerLifecycleMutationRequest,
            executor_type=executor_type,
            build=lambda: executor_type(ports_factory),
        ),
        result_type=LedgerLifecycleExecutionResult,
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
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE}),
    )


def build_ledger_archive_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the receipt-backed canonical archive mutation."""
    return _build_definition(
        operation_id=LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
        executor_type=LedgerArchiveExecutor,
        ports_factory=ports_factory,
    )


def build_ledger_stash_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the receipt-backed canonical stash mutation."""
    return _build_definition(
        operation_id=LEDGER_STASH_OPERATION_DEFINITION_ID,
        executor_type=LedgerStashExecutor,
        ports_factory=ports_factory,
    )


def build_ledger_restore_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the receipt-backed canonical restore mutation."""
    return _build_definition(
        operation_id=LEDGER_RESTORE_OPERATION_DEFINITION_ID,
        executor_type=LedgerRestoreExecutor,
        ports_factory=ports_factory,
    )


def build_ledger_exclude_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare the receipt-backed canonical review-exclusion mutation."""
    return _build_definition(
        operation_id=LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
        executor_type=LedgerExcludeExecutor,
        ports_factory=ports_factory,
    )


def _resolve_lifecycle_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    operation_id: LedgerLifecycleOperationId,
) -> ResolvedOperationAccess:
    if request.definition_id != operation_id or not isinstance(request.payload, LedgerLifecycleMutationRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def resolve_ledger_archive_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile disclosure and COMMIT for archive."""
    return _resolve_lifecycle_access(request, context, operation_id=LEDGER_ARCHIVE_OPERATION_DEFINITION_ID)


def resolve_ledger_stash_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile disclosure and COMMIT for stash."""
    return _resolve_lifecycle_access(request, context, operation_id=LEDGER_STASH_OPERATION_DEFINITION_ID)


def resolve_ledger_restore_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile disclosure and COMMIT for restore."""
    return _resolve_lifecycle_access(request, context, operation_id=LEDGER_RESTORE_OPERATION_DEFINITION_ID)


def resolve_ledger_exclude_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile disclosure and COMMIT for review exclusion."""
    return _resolve_lifecycle_access(request, context, operation_id=LEDGER_EXCLUDE_OPERATION_DEFINITION_ID)


def _build_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerLifecycleMutationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerLifecycleOperationResult,
        ),
        result_projector=_project_result,
        access_resolver=access_resolver,
    )


def build_ledger_archive_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind archive's strict version-one schemas and exact-profile resolver."""
    return _build_registration(definition, access_resolver=resolve_ledger_archive_access)


def build_ledger_stash_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind stash's strict version-one schemas and exact-profile resolver."""
    return _build_registration(definition, access_resolver=resolve_ledger_stash_access)


def build_ledger_restore_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind restore's strict version-one schemas and exact-profile resolver."""
    return _build_registration(definition, access_resolver=resolve_ledger_restore_access)


def build_ledger_exclude_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind exclusion's strict version-one schemas and exact-profile resolver."""
    return _build_registration(definition, access_resolver=resolve_ledger_exclude_access)


__all__ = [
    "LEDGER_ARCHIVE_OPERATION_DEFINITION_ID",
    "LEDGER_EXCLUDE_OPERATION_DEFINITION_ID",
    "LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE",
    "LEDGER_RESTORE_OPERATION_DEFINITION_ID",
    "LEDGER_STASH_OPERATION_DEFINITION_ID",
    "LedgerArchiveExecutor",
    "LedgerExcludeExecutor",
    "LedgerLifecycleBlockerProjection",
    "LedgerLifecycleExecutionResult",
    "LedgerLifecycleMutationProjection",
    "LedgerLifecycleMutationRequest",
    "LedgerLifecycleOperationId",
    "LedgerLifecycleOperationResult",
    "LedgerLifecycleValidationProjection",
    "LedgerLifecycleValidationRefusedError",
    "LedgerRestoreExecutor",
    "LedgerStashExecutor",
    "build_ledger_archive_definition",
    "build_ledger_archive_registration",
    "build_ledger_exclude_definition",
    "build_ledger_exclude_registration",
    "build_ledger_restore_definition",
    "build_ledger_restore_registration",
    "build_ledger_stash_definition",
    "build_ledger_stash_registration",
    "resolve_ledger_archive_access",
    "resolve_ledger_exclude_access",
    "resolve_ledger_restore_access",
    "resolve_ledger_stash_access",
]
