"""Exact-profile operation for importing local ledger statement files."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.severity import BaseSeverity
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.currency.service import CurrencyNormalizationService
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import BucketTransactionRef
from ...domain.transactions.own_accounts import OwnAccountId, OwnAccountRegister
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..transactions.diagnostics import LedgerImportDiagnosticKind
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_import import (
    OWN_ACCOUNT_MISMATCH_MESSAGE,
    LedgerProviderID,
    PreparedLedgerSourceImport,
    aggregate_ledger_import_results,
    persist_prepared_ledger_source_import,
    prepare_ledger_source_import,
)
from .import_ports import LedgerImportPorts
from .models import LedgerSourceImportCommand, LedgerSourceImportResult
from .own_account_ports import OwnAccountRepositoryProtocol
from .protocols import BucketEventHistoryCoCommitWriterProtocol, TransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_commit_access, resolve_ledger_read_access

LEDGER_IMPORT_OPERATION_DEFINITION_ID = "ledger.import"
MAX_LEDGER_IMPORT_FILES = 128
MAX_LEDGER_IMPORT_ROWS = 4_096
MAX_LEDGER_IMPORT_DIAGNOSTICS = MAX_LEDGER_IMPORT_ROWS + (2 * MAX_LEDGER_IMPORT_FILES)
MAX_LEDGER_IMPORT_EVENTS = 4 * MAX_LEDGER_IMPORT_ROWS

type LedgerImportDiagnosticMessage = Literal[
    "transactions.import.message_185962",
    "transactions.import.message_082074",
    "transactions.import.batch_id_collision",
    "transactions.import.message_053465",
    "transactions.import.message_829073",
    "transactions.import.verified",
    "transactions.import.unreadable",
]
_DIAGNOSTIC_MESSAGE_KEYS: dict[str, LedgerImportDiagnosticMessage] = {
    "transactions.import.message_185962": "transactions.import.message_185962",
    "transactions.import.message_082074": "transactions.import.message_082074",
    "transactions.import.batch_id_collision": "transactions.import.batch_id_collision",
    "transactions.import.message_053465": "transactions.import.message_053465",
    "transactions.import.message_829073": "transactions.import.message_829073",
    "transactions.import.verified": "transactions.import.verified",
    "transactions.import.unreadable": "transactions.import.unreadable",
}


@dataclass(frozen=True, slots=True)
class LedgerImportOperationPorts:
    """The exact-profile services needed by the source-import action."""

    import_ports: LedgerImportPorts
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol
    currency_normalizer: CurrencyNormalizationService
    operation: PinnedAuthorityOperation
    own_accounts: OwnAccountRepositoryProtocol


class LedgerImportOperationPortsFactory(Protocol):
    """Compose import adapters and persistence ports for one profile worker."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerImportOperationPorts:
        """Return the source and persistence ports bound to ``bucket_id``."""
        ...


class LedgerImportRequest(BaseModel):
    """Sensitive local file references and import options for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    files: tuple[Path, ...] = Field(min_length=1, max_length=MAX_LEDGER_IMPORT_FILES)
    provider: LedgerProviderID
    dry_run: bool = False
    verify: bool = False
    verify_source: Path | None = None
    period: PublicPeriod | None = None
    own_account_id: OwnAccountId | None = None


class LedgerImportFileRefusal(BaseModel):
    """Safe file-level refusal identity without parser context or file contents."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    file_name: str = Field(min_length=1, max_length=255)
    reason_code: Literal["transaction_validation", "own_account_mismatch", "result_limit"]


class LedgerImportValidationProjection(BaseModel):
    """Bounded validation facts, with provider warning prose withheld."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    valid: bool
    warning_count: NonNegativeInt
    encoding: str | None = Field(default=None, max_length=32)


class LedgerImportSourceProjection(BaseModel):
    """Safe source verification facts without a caller-controlled path."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    requested: bool
    sha256: ContentDigest | None = None


class LedgerImportDiagnosticProjection(BaseModel):
    """Allowlisted diagnostic category, translation key, and optional ids."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: LedgerImportDiagnosticKind
    severity: BaseSeverity
    message: LedgerImportDiagnosticMessage
    affected_transaction_ids: tuple[str, ...] = Field(default=(), max_length=1)


class LedgerImportResultProjection(BaseModel):
    """Allowlisted aggregate for the CLI; backend paths and prose stay private."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: NonNegativeInt
    imported: NonNegativeInt
    skipped: NonNegativeInt
    likely_duplicates: NonNegativeInt
    dry_run: bool
    verify: bool
    period: PublicPeriod | None = None
    bucket_id: str
    import_batch_id: Hex64Str | None = None
    bucket_event_ids: tuple[str, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_EVENTS)
    imported_transaction_refs: tuple[BucketTransactionRef, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_ROWS)
    skipped_transaction_refs: tuple[BucketTransactionRef, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_ROWS)
    likely_duplicate_transaction_refs: tuple[BucketTransactionRef, ...] = Field(
        default=(), max_length=MAX_LEDGER_IMPORT_ROWS
    )
    validations: tuple[LedgerImportValidationProjection, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    sources: tuple[LedgerImportSourceProjection, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    diagnostics: tuple[LedgerImportDiagnosticProjection, ...] = Field(
        default=(), max_length=MAX_LEDGER_IMPORT_DIAGNOSTICS
    )
    refused_files: tuple[LedgerImportFileRefusal, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)

    @model_validator(mode="after")
    def _exact_profile(self) -> LedgerImportResultProjection:
        if self.bucket_id != str(self.profile_id):
            raise ValueError("ledger import result does not belong to its exact profile")
        if any(
            str(reference.bucket_id) != self.bucket_id
            for reference in (
                *self.imported_transaction_refs,
                *self.skipped_transaction_refs,
                *self.likely_duplicate_transaction_refs,
            )
        ):
            raise ValueError("ledger import transaction references do not belong to their exact profile")
        return self


@dataclass(frozen=True, slots=True)
class _LedgerImportResultFacts:
    """Typed, allowlisted facts extracted from canonical source results."""

    rows: int
    imported: int
    skipped: int
    likely_duplicates: int
    bucket_id: str
    import_batch_id: str | None
    bucket_event_ids: tuple[str, ...]
    imported_transaction_refs: tuple[BucketTransactionRef, ...]
    skipped_transaction_refs: tuple[BucketTransactionRef, ...]
    likely_duplicate_transaction_refs: tuple[BucketTransactionRef, ...]
    validations: tuple[LedgerImportValidationProjection, ...]
    sources: tuple[LedgerImportSourceProjection, ...]
    diagnostics: tuple[LedgerImportDiagnosticProjection, ...]


class _LedgerImportExecutionFile(BaseModel):
    """Private stored result for one successfully parsed statement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    file_name: str = Field(min_length=1, max_length=255)
    result: LedgerSourceImportResult = Field(repr=False)


class LedgerImportExecutionResult(BaseModel):
    """Private secure-operand result; only its allowlisted projection is public."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    dry_run: bool
    verify: bool
    period: PublicPeriod | None = None
    files: tuple[_LedgerImportExecutionFile, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    refused_files: tuple[LedgerImportFileRefusal, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)


def _safe_file_name(path: Path) -> str:
    name = path.name or "(unnamed)"
    bounded = "".join("_" if ord(character) < 32 or ord(character) == 127 else character for character in name)
    return bounded[:255] or "(unnamed)"


def _safe_encoding(value: str | None) -> str | None:
    if value is None or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", value) is None:
        return None
    return value


def _project_result_facts(
    result: LedgerSourceImportResult,
    *,
    bucket_id: str,
) -> _LedgerImportResultFacts:
    """Copy the explicitly public portions of one canonical backend result."""
    diagnostics: list[LedgerImportDiagnosticProjection] = []
    for report in result.diagnostics:
        try:
            message = _DIAGNOSTIC_MESSAGE_KEYS[report.message]
            kind = LedgerImportDiagnosticKind(report.kind)
            severity = BaseSeverity(report.severity)
        except (KeyError, ValueError):
            # A new canonical diagnostic value must be deliberately enrolled
            # in this safe public vocabulary before it can cross the boundary.
            raise ValueError("unregistered ledger import diagnostic projection value") from None
        diagnostics.append(
            LedgerImportDiagnosticProjection(
                kind=kind,
                severity=severity,
                message=message,
                affected_transaction_ids=report.affected_transaction_ids,
            ),
        )
    return _LedgerImportResultFacts(
        rows=result.rows,
        imported=result.imported,
        skipped=result.skipped,
        likely_duplicates=result.likely_duplicates,
        bucket_id=bucket_id,
        import_batch_id=result.import_batch_id,
        bucket_event_ids=result.bucket_event_ids,
        imported_transaction_refs=result.imported_transaction_refs,
        skipped_transaction_refs=result.skipped_transaction_refs,
        likely_duplicate_transaction_refs=result.likely_duplicate_transaction_refs,
        validations=tuple(
            LedgerImportValidationProjection(
                valid=report.valid,
                warning_count=len(report.warnings),
                encoding=_safe_encoding(report.encoding),
            )
            for report in result.validations
        ),
        sources=tuple(
            LedgerImportSourceProjection(requested=report.requested, sha256=report.sha256) for report in result.sources
        ),
        diagnostics=tuple(diagnostics),
    )


def _aggregate_import_file_results(
    execution: LedgerImportExecutionResult,
) -> LedgerSourceImportResult | None:
    """Return no result, the single source result, or its canonical aggregate."""
    backend_results = tuple(item.result for item in execution.files)
    if not backend_results:
        return None
    if len(backend_results) == 1:
        return backend_results[0]
    return aggregate_ledger_import_results(backend_results)


def _expected_import_effect(
    execution: LedgerImportExecutionResult,
    aggregate: LedgerSourceImportResult | None,
) -> OperationEffect:
    """Derive the public effect from persisted import facts, not the request alone."""
    if not execution.dry_run and aggregate is not None and aggregate.imported > 0:
        return OperationEffect.UPDATED
    return OperationEffect.NONE


def _empty_import_result_facts(bucket_id: str) -> _LedgerImportResultFacts:
    """Represent an all-refused or empty result without inventing a source row."""
    return _LedgerImportResultFacts(
        rows=0,
        imported=0,
        skipped=0,
        likely_duplicates=0,
        bucket_id=bucket_id,
        import_batch_id=None,
        bucket_event_ids=(),
        imported_transaction_refs=(),
        skipped_transaction_refs=(),
        likely_duplicate_transaction_refs=(),
        validations=(),
        sources=(),
        diagnostics=(),
    )


def _project_import_result_facts(
    aggregate: LedgerSourceImportResult | None,
    *,
    bucket_id: str,
) -> _LedgerImportResultFacts:
    """Apply the safe source-result allowlist or its truthful empty state."""
    if aggregate is None:
        return _empty_import_result_facts(bucket_id)
    return _project_result_facts(aggregate, bucket_id=bucket_id)


def project_ledger_import_result(
    result: BaseModel,
    terminal_receipt: OperationTerminalReceipt,
    /,
) -> LedgerImportResultProjection:
    """Project one settled private import without paths or provider prose."""
    if not isinstance(result, LedgerImportExecutionResult):
        raise ValueError("unexpected ledger import execution result")
    if (
        terminal_receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or terminal_receipt.identity.definition_id != LEDGER_IMPORT_OPERATION_DEFINITION_ID
        or terminal_receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
    ):
        raise ValueError("ledger import terminal receipt does not match its exact operation")
    bucket_id = str(result.profile_id)
    aggregate = _aggregate_import_file_results(result)
    expected_effect = _expected_import_effect(result, aggregate)
    if terminal_receipt.effect is not expected_effect:
        raise ValueError("ledger import effect does not match its settled import result")
    facts = _project_import_result_facts(aggregate, bucket_id=bucket_id)
    return LedgerImportResultProjection(
        profile_id=result.profile_id,
        rows=facts.rows,
        imported=facts.imported,
        skipped=facts.skipped,
        likely_duplicates=facts.likely_duplicates,
        dry_run=result.dry_run,
        verify=result.verify,
        period=result.period,
        refused_files=result.refused_files,
        bucket_id=facts.bucket_id,
        import_batch_id=facts.import_batch_id,
        bucket_event_ids=facts.bucket_event_ids,
        imported_transaction_refs=facts.imported_transaction_refs,
        skipped_transaction_refs=facts.skipped_transaction_refs,
        likely_duplicate_transaction_refs=facts.likely_duplicate_transaction_refs,
        validations=facts.validations,
        sources=facts.sources,
        diagnostics=facts.diagnostics,
    )


def _prepare_import_file(
    path: Path,
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    own_accounts: OwnAccountRegister,
    remaining_row_capacity: int,
) -> PreparedLedgerSourceImport | LedgerImportFileRefusal:
    """Stage one source, or return its safe refusal before persistence."""
    command = LedgerSourceImportCommand(
        bucket_id=bucket_id,
        path=path,
        provider=payload.provider.value,
        dry_run=payload.dry_run,
        verify=payload.verify,
        source=payload.verify_source,
        period=payload.period.to_period() if payload.period is not None else None,
        own_account_id=payload.own_account_id,
        actor=bucket_id,
        source_command="aeat app ledger import",
    )
    try:
        prepared = prepare_ledger_source_import(command, ports=ports.import_ports, own_accounts=own_accounts)
    except TransactionValidationError as exc:
        return LedgerImportFileRefusal(
            file_name=_safe_file_name(path),
            reason_code=(
                "own_account_mismatch"
                if exc.translated_message == OWN_ACCOUNT_MISMATCH_MESSAGE
                else "transaction_validation"
            ),
        )
    if len(prepared.source.parsed_rows) > remaining_row_capacity:
        return LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="result_limit")
    return prepared


def _compose_staged_imports(
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    operation: PinnedAuthorityOperation,
    ports_factory: LedgerImportOperationPortsFactory,
) -> tuple[
    LedgerImportOperationPorts,
    list[tuple[Path, PreparedLedgerSourceImport]],
    list[LedgerImportFileRefusal],
]:
    """Compose exact-profile ports and stage admissible source files in request order."""
    ports = ports_factory(bucket_id=bucket_id, operation=operation)
    if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    own_accounts = ports.own_accounts.load()
    if payload.own_account_id is not None and payload.own_account_id not in {
        account.own_account_id for account in own_accounts.accounts
    }:
        raise TransactionValidationError(
            translated_message="errors.transaction.ledger_import_own_account_unknown",
            context={"own_account_id": payload.own_account_id},
        )
    staged: list[tuple[Path, PreparedLedgerSourceImport]] = []
    refusals: list[LedgerImportFileRefusal] = []
    staged_rows = 0
    for path in payload.files:
        outcome = _prepare_import_file(
            path,
            bucket_id=bucket_id,
            payload=payload,
            ports=ports,
            own_accounts=own_accounts,
            remaining_row_capacity=MAX_LEDGER_IMPORT_ROWS - staged_rows,
        )
        if isinstance(outcome, LedgerImportFileRefusal):
            refusals.append(outcome)
            continue
        staged_rows += len(outcome.source.parsed_rows)
        staged.append((path, outcome))
    return ports, staged, refusals


def _persist_staged_imports(
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    staged: list[tuple[Path, PreparedLedgerSourceImport]],
    refusals: list[LedgerImportFileRefusal],
) -> LedgerImportExecutionResult:
    """Persist staged imports in order and append persistence refusals afterward."""
    files: list[_LedgerImportExecutionFile] = []
    for path, prepared in staged:
        try:
            result = persist_prepared_ledger_source_import(
                prepared,
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                currency_normalizer=ports.currency_normalizer,
            )
        except TransactionValidationError:
            refusals.append(
                LedgerImportFileRefusal(
                    file_name=_safe_file_name(path),
                    reason_code="transaction_validation",
                ),
            )
            continue
        files.append(_LedgerImportExecutionFile(file_name=_safe_file_name(path), result=result))
    return LedgerImportExecutionResult(
        profile_id=payload.profile_id,
        dry_run=payload.dry_run,
        verify=payload.verify,
        period=payload.period,
        files=tuple(files),
        refused_files=tuple(refusals),
    )


async def _publish_staged_imports(
    context: OperationExecutorContext,
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    staged: list[tuple[Path, PreparedLedgerSourceImport]],
    refusals: list[LedgerImportFileRefusal],
) -> str:
    """Publish a dry-run or all-refused result without entering COMMIT."""
    execution = await asyncio.to_thread(
        _persist_staged_imports,
        bucket_id=bucket_id,
        payload=payload,
        ports=ports,
        staged=staged,
        refusals=refusals,
    )
    reference = await context.operands.put(execution, written_at=now())
    await context.events.effect(OperationEffect.NONE)
    return reference


async def _commit_staged_imports(
    context: OperationExecutorContext,
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    staged: list[tuple[Path, PreparedLedgerSourceImport]],
    refusals: list[LedgerImportFileRefusal],
) -> str:
    """Settle the irreversible import with UNKNOWN then its measured final effect."""
    async with context.cancellation.irreversible_section():
        await context.events.effect(OperationEffect.UNKNOWN)
        execution = await asyncio.to_thread(
            _persist_staged_imports,
            bucket_id=bucket_id,
            payload=payload,
            ports=ports,
            staged=staged,
            refusals=refusals,
        )
        effect = (
            OperationEffect.UPDATED
            if any(item.result.imported > 0 for item in execution.files)
            else OperationEffect.NONE
        )
        reference = await context.operands.put(execution, written_at=now())
        await context.events.effect(effect)
        return reference


class LedgerImportExecutor:
    """Stage source bytes first, then persist pinned parsed rows under COMMIT."""

    def __init__(self, ports: LedgerImportOperationPortsFactory) -> None:
        """Retain the explicit profile-aware composition capability."""
        self._ports = ports

    async def execute(self, request: OperationRequest[LedgerImportRequest], context: OperationExecutorContext) -> str:
        """Parse before the fresh local-write guard and publish a private result."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_IMPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_IMPORT_OPERATION_DEFINITION_ID)
        ports, staged, refusals = await asyncio.to_thread(
            _compose_staged_imports,
            bucket_id=bucket_id,
            payload=payload,
            operation=context.authority_operation,
            ports_factory=self._ports,
        )
        if payload.dry_run or not staged:
            return await await_cancellation_complete(
                _publish_staged_imports(
                    context,
                    bucket_id=bucket_id,
                    payload=payload,
                    ports=ports,
                    staged=staged,
                    refusals=refusals,
                ),
                task_name="ledger-import-preview" if payload.dry_run else "ledger-import-refusals",
            )
        return await await_cancellation_complete(
            _commit_staged_imports(
                context,
                bucket_id=bucket_id,
                payload=payload,
                ports=ports,
                staged=staged,
                refusals=refusals,
            ),
            task_name="ledger-import-publication",
        )


def build_ledger_import_definition(ports: LedgerImportOperationPortsFactory) -> OperationDefinition:
    """Declare a durable, exact-profile local import with honest effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        request_type=LedgerImportRequest,
        result_type=LedgerImportExecutionResult,
        executor_type=LedgerImportExecutor,
        build=lambda: LedgerImportExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_ledger_import_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile read access and COMMIT only for a persisted import."""
    if request.definition_id != LEDGER_IMPORT_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerImportRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolve = resolve_ledger_read_access if request.payload.dry_run else resolve_ledger_commit_access
    return resolve(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_import_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the private request and its allowlisted public result projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerImportResultProjection,
        result_projector=project_ledger_import_result,
        access_resolver=resolve_ledger_import_access,
    )


__all__ = [
    "LEDGER_IMPORT_OPERATION_DEFINITION_ID",
    "LedgerImportDiagnosticProjection",
    "LedgerImportExecutor",
    "LedgerImportFileRefusal",
    "LedgerImportOperationPorts",
    "LedgerImportOperationPortsFactory",
    "LedgerImportRequest",
    "LedgerImportResultProjection",
    "LedgerImportSourceProjection",
    "LedgerImportValidationProjection",
    "build_ledger_import_definition",
    "build_ledger_import_registration",
    "project_ledger_import_result",
    "resolve_ledger_import_access",
]
