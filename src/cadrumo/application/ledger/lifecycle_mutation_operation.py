"""Exact-profile registered mutations of ledger lifecycle and review state."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
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
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_lifecycle import (
    archive_manual_transaction,
    mark_transaction_reviewed_excluded,
    restore_manual_transaction,
    stash_manual_transaction,
)
from .id_resolution import resolve_transaction_id
from .lifecycle_contracts import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleExecutionResult,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
    LedgerLifecycleValidationProjection,
)
from .lifecycle_projections import (
    lifecycle_validation_result,
    project_lifecycle_mutation_from_action,
    project_lifecycle_operation_result,
    project_lifecycle_validation_from_error,
    require_lifecycle_result_size,
)
from .models import ManualLedgerTransactionResult
from .protocols import TransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_commit_access


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


class _PreparedLifecycleMutation(BaseModel):
    """Resolved exact-profile service ports and full transaction identifier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_id: LedgerLifecycleOperationId
    transaction_id: Hex64Str


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
            refused = lifecycle_validation_result(
                payload.profile_id,
                self._operation_id,
                project_lifecycle_validation_from_error(error, transaction_id=None),
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
                    return project_lifecycle_validation_from_error(error, transaction_id=prepared.transaction_id)
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
            require_lifecycle_result_size(detail)
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        projection = project_lifecycle_mutation_from_action(payload.profile_id, self._operation_id, settled)
        result = LedgerLifecycleOperationResult(
            outcome="updated",
            profile_id=payload.profile_id,
            operation_id=self._operation_id,
            result=projection,
        )
        execution_result = LedgerLifecycleExecutionResult(result=result)
        require_lifecycle_result_size(execution_result)
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


async def _publish_refusal(
    context: OperationExecutorContext,
    result: LedgerLifecycleOperationResult,
) -> OperationRefusalEvidence:
    await context.events.effect(OperationEffect.NONE)
    execution_result = LedgerLifecycleExecutionResult(result=result)
    require_lifecycle_result_size(execution_result)
    detail_ref = await context.operands.put(execution_result, written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


def _build_definition(
    *,
    operation_id: LedgerLifecycleOperationId,
    executor_type: type[_LedgerLifecycleExecutor],
    ports_factory: LedgerActionPortsFactory,
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=operation_id,
        request_type=LedgerLifecycleMutationRequest,
        result_type=LedgerLifecycleExecutionResult,
        executor_type=executor_type,
        build=lambda: executor_type(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
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
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


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
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerLifecycleOperationResult,
        result_projector=project_lifecycle_operation_result,
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
    "LedgerArchiveExecutor",
    "LedgerExcludeExecutor",
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
