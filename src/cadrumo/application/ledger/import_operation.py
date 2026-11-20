"""Exact-profile operation for importing local ledger statement files."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.severity import BaseSeverity
from ...core.hex import Hex64Str
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.optional_extras import MissingOptionalExtraError
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.currency.service import CurrencyNormalizationService
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import BucketTransactionRef
from ...domain.transactions.own_accounts import (
    OwnAccountHolding,
    OwnAccountId,
    OwnAccountRegister,
    OwnAccountRegisterValidationError,
)
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..operator_actions.projection import PreconditionVerdictSnapshot
from ..transactions.diagnostics import LedgerImportDiagnosticKind
from ..user_profile.access_errors import ProfileAccessRefusedError
from .actions_common import require_registered_own_account
from .actions_import import (
    OWN_ACCOUNT_MISMATCH_MESSAGE,
    LedgerProviderID,
    PreparedLedgerSourceImport,
    aggregate_ledger_import_results,
    bind_prepared_import_to_own_account,
    describe_statement_account,
    persist_prepared_ledger_source_import,
    plan_ledger_import_sources,
    prepare_ledger_source_import,
)
from .import_ports import LedgerImportPorts, LedgerImportReaderUnavailableError
from .models import LedgerSourceImportCommand, LedgerSourceImportResult
from .own_account_operation import LEDGER_OWN_ACCOUNT_LABEL_MAX, LedgerOwnAccountRequest, apply_own_account_request
from .own_account_ports import OwnAccountRepositoryProtocol
from .protocols import BucketEventHistoryCoCommitWriterProtocol, TransactionCatalogueCoCommitWriterProtocol
from .read_access import resolve_ledger_request_access

_FILE_NAME_MAX_LENGTH = 255

LEDGER_IMPORT_OPERATION_DEFINITION_ID = "ledger.import"
MAX_LEDGER_IMPORT_FILES = 128
MAX_LEDGER_IMPORT_REFUSALS = 2 * MAX_LEDGER_IMPORT_FILES
"""Every requested entry and every planned file can each be refused once."""
MAX_LEDGER_IMPORT_ROWS = 4_096
MAX_LEDGER_IMPORT_DIAGNOSTICS = MAX_LEDGER_IMPORT_ROWS + (2 * MAX_LEDGER_IMPORT_FILES)
MAX_LEDGER_IMPORT_EVENTS = 4 * MAX_LEDGER_IMPORT_ROWS

type LedgerImportDiagnosticMessage = Literal[
    "transactions.import.message_185962",
    "transactions.import.all_rows_already_in_ledger",
    "transactions.import.some_rows_already_in_ledger",
    "transactions.import.batch_id_collision",
    "transactions.import.message_053465",
    "transactions.import.message_829073",
    "transactions.import.verified",
    "transactions.import.unreadable",
]
# One canonical diagnostic per row already stored. The public result names the
# fact once, for the whole import, and says whether it holds for every row.
_STORED_DUPLICATE_MESSAGE = str(tr("transactions.import.message_082074"))
_ALL_ROWS_STORED_MESSAGE = str(tr("transactions.import.all_rows_already_in_ledger"))
_SOME_ROWS_STORED_MESSAGE = str(tr("transactions.import.some_rows_already_in_ledger"))
_DIAGNOSTIC_MESSAGE_KEYS: dict[str, LedgerImportDiagnosticMessage] = {
    "transactions.import.message_185962": "transactions.import.message_185962",
    "transactions.import.all_rows_already_in_ledger": "transactions.import.all_rows_already_in_ledger",
    "transactions.import.some_rows_already_in_ledger": "transactions.import.some_rows_already_in_ledger",
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


class LedgerImportAccountRegistration(BaseModel):
    """The operator's own words for the account a statement names, when the import registers it.

    The account number is never asked again: it is the one the statement names.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    label: str = Field(min_length=1, max_length=LEDGER_OWN_ACCOUNT_LABEL_MAX)
    holding: OwnAccountHolding


class LedgerImportRequest(BaseModel):
    """Sensitive local file references and import options for one profile.

    Each entry of ``files`` is a statement file or a directory. The operation
    plans a directory into its importable files itself, in a deterministic
    order, so every caller that names the same directory imports the same
    files. The planned files of all entries together are held to
    ``MAX_LEDGER_IMPORT_FILES``.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    files: tuple[Path, ...] = Field(min_length=1, max_length=MAX_LEDGER_IMPORT_FILES)
    provider: LedgerProviderID
    dry_run: bool = False
    verify: bool = False
    verify_source: Path | None = None
    period: PublicPeriod | None = None
    own_account_id: OwnAccountId | None = None
    expected_source_sha256: tuple[ContentDigest, ...] | None = None
    """The digest a preview reported for each file, in ``files`` order; a file whose
    parsed bytes now differ is refused rather than imported. A digest names one
    file's bytes, so an entry that is a directory is refused when paired with one."""
    register_statement_account: LedgerImportAccountRegistration | None = None
    """Register the account the one named file's statement names as an own account, then
    bind the file's rows to it. Only an import that writes takes it, for one file, with no
    own account chosen: the account is the statement's, not the operator's choice. A
    statement that names a registered account is bound to it and registers nothing."""

    @model_validator(mode="after")
    def _one_digest_per_file(self) -> LedgerImportRequest:
        if self.expected_source_sha256 is not None and len(self.expected_source_sha256) != len(self.files):
            raise ValueError("ledger import expects exactly one source digest per file")
        return self

    @model_validator(mode="after")
    def _registration_is_for_one_written_file(self) -> LedgerImportRequest:
        if self.register_statement_account is None:
            return self
        if self.dry_run:
            raise ValueError("a statement account is registered only by an import that writes")
        if self.own_account_id is not None:
            raise ValueError("a statement account is registered only when no own account is chosen")
        if len(self.files) != 1:
            raise ValueError("a statement account is registered from exactly one file")
        return self

    @model_validator(mode="after")
    def _absolute_paths(self) -> LedgerImportRequest:
        # A relative path would resolve against the runtime's working directory, not the caller's.
        named = self.files if self.verify_source is None else (*self.files, self.verify_source)
        if not all(path.is_absolute() for path in named):
            raise ValueError("ledger import paths must be absolute")
        return self


class LedgerImportFileRefusal(BaseModel):
    """Safe file-level refusal identity without parser context or file contents."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    file_name: str = Field(min_length=1, max_length=_FILE_NAME_MAX_LENGTH)
    reason_code: Literal[
        "transaction_validation",
        "own_account_mismatch",
        "result_limit",
        "source_changed",
        "empty_directory",
        "file_limit",
        "reader_unavailable",
        "format_not_installed",
        "statement_account_missing",
    ]
    """``empty_directory`` names a requested directory holding no importable file.
    ``file_limit`` names each requested entry of a request whose planned files
    exceed the registered count, of which none is read. ``reader_unavailable``
    names a file whose only reading lane needs a model that could not be asked.
    ``format_not_installed`` names a file of a format whose parser ships in an
    optional extra this installation lacks. ``statement_account_missing`` names
    a file whose statement names no valid account, when its account was to be
    registered from it."""
    precondition_verdict: PreconditionVerdictSnapshot | None = None
    """Present exactly for ``reader_unavailable``: the reader probe's verdict,
    naming the local AI setup when setting it up lets the file be read. One
    file of a folder can need it while the others import, so it rides on the
    file rather than refusing the operation."""

    @model_validator(mode="after")
    def _verdict_only_for_reader(self) -> LedgerImportFileRefusal:
        if (self.reason_code == "reader_unavailable") != (self.precondition_verdict is not None):
            raise ValueError("a ledger import file refusal carries a verdict exactly when its reader was unavailable")
        return self


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


class LedgerImportSourceDigest(BaseModel):
    """The SHA-256 of the bytes parsed from one planned file, by its position in the plan.

    The plan is the request's entries in order, each directory replaced by its
    importable files, so for a request that names files alone it is the request.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    file_index: NonNegativeInt
    sha256: ContentDigest


class LedgerImportStatementAccount(BaseModel):
    """The account one planned file's statement names, by mask only.

    ``own_account_id`` is the registered own account the statement names;
    ``registrable`` says the statement names a valid account that no registered
    account has. The full account number never leaves the secure request.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    file_index: NonNegativeInt
    masked_iban: str = Field(min_length=1, max_length=64)
    own_account_id: OwnAccountId | None = None
    registrable: bool

    @model_validator(mode="after")
    def _registrable_names_no_registered_account(self) -> LedgerImportStatementAccount:
        if self.registrable and self.own_account_id is not None:
            raise ValueError("a statement account that names a registered account is not registrable")
        return self


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
    refused_files: tuple[LedgerImportFileRefusal, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_REFUSALS)
    source_digests: tuple[LedgerImportSourceDigest, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    statement_accounts: tuple[LedgerImportStatementAccount, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    registered_own_account_id: OwnAccountId | None = None
    """The own account this import added to the register from its statement, when it did."""

    @property
    def settled_effect(self) -> OperationEffect:
        """The mutation effect a receipt must carry.

        A dry run writes nothing, and an import of no row that registered no account writes nothing.
        """
        wrote = self.imported > 0 or self.registered_own_account_id is not None
        return OperationEffect.UPDATED if not self.dry_run and wrote else OperationEffect.NONE

    @model_validator(mode="after")
    def _exact_profile(self) -> LedgerImportResultProjection:
        if self.bucket_id != str(self.profile_id):
            raise ValueError("ledger import result does not belong to its exact profile")
        if any(
            reference.bucket_id != self.bucket_id
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

    file_name: str = Field(min_length=1, max_length=_FILE_NAME_MAX_LENGTH)
    file_index: NonNegativeInt
    source_sha256: ContentDigest | None = None
    result: LedgerSourceImportResult = Field(repr=False)


class LedgerImportExecutionResult(BaseModel):
    """Private secure-operand result; only its allowlisted projection is public."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    dry_run: bool
    verify: bool
    period: PublicPeriod | None = None
    files: tuple[_LedgerImportExecutionFile, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    refused_files: tuple[LedgerImportFileRefusal, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_REFUSALS)
    statement_accounts: tuple[LedgerImportStatementAccount, ...] = Field(default=(), max_length=MAX_LEDGER_IMPORT_FILES)
    registered_own_account_id: OwnAccountId | None = None


def _safe_file_name(path: Path) -> str:
    name = path.name or "(unnamed)"
    bounded = "".join("_" if ord(character) < 32 or ord(character) == 127 else character for character in name)
    return bounded[:_FILE_NAME_MAX_LENGTH] or "(unnamed)"


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
    stored_duplicates = 0
    stored_duplicates_at: int | None = None
    for report in result.diagnostics:
        if report.message == _STORED_DUPLICATE_MESSAGE:
            stored_duplicates += 1
            if stored_duplicates_at is None:
                stored_duplicates_at = len(diagnostics)
            continue
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
    if stored_duplicates_at is not None:
        diagnostics.insert(
            stored_duplicates_at,
            LedgerImportDiagnosticProjection(
                kind=LedgerImportDiagnosticKind.DUPLICATE,
                severity=BaseSeverity.INFO,
                message=_DIAGNOSTIC_MESSAGE_KEYS[
                    _ALL_ROWS_STORED_MESSAGE if stored_duplicates == result.rows else _SOME_ROWS_STORED_MESSAGE
                ],
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
    if execution.dry_run:
        return OperationEffect.NONE
    if execution.registered_own_account_id is not None or (aggregate is not None and aggregate.imported > 0):
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
        source_digests=tuple(
            LedgerImportSourceDigest(file_index=item.file_index, sha256=item.source_sha256)
            for item in result.files
            if item.source_sha256 is not None
        ),
        statement_accounts=result.statement_accounts,
        registered_own_account_id=result.registered_own_account_id,
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
    actor: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    own_accounts: OwnAccountRegister,
    remaining_row_capacity: int,
    expected_sha256: str | None,
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
        actor=actor,
        source_command="aeat app ledger import",
    )
    try:
        prepared = prepare_ledger_source_import(command, ports=ports.import_ports, own_accounts=own_accounts)
    except LedgerImportReaderUnavailableError as exc:
        verdict = exc.terminal_precondition_verdict
        return LedgerImportFileRefusal(
            file_name=_safe_file_name(path),
            reason_code="transaction_validation" if verdict is None else "reader_unavailable",
            precondition_verdict=None if verdict is None else PreconditionVerdictSnapshot.from_verdict(verdict),
        )
    except MissingOptionalExtraError:
        return LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="format_not_installed")
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
    if expected_sha256 is not None and parsed_source_sha256(prepared) != expected_sha256:
        return LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="source_changed")
    if payload.register_statement_account is not None and prepared.source.statement_account is None:
        return LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="statement_account_missing")
    return prepared


def parsed_source_sha256(prepared: PreparedLedgerSourceImport) -> str | None:
    """The digest of the bytes the rows were parsed from, or ``None`` when no row carries one."""
    digests = {row.raw.provenance.source_sha256 for row in prepared.source.parsed_rows}
    return digests.pop() if len(digests) == 1 else None


type _StagedImport = tuple[int, Path, PreparedLedgerSourceImport]
"""One parsed statement with its position in the plan and its path."""

type _PlannedFile = tuple[Path, str | None]
"""One file to read, with the digest the request expects of it, if any."""


def _plan_requested_files(
    payload: LedgerImportRequest,
) -> tuple[tuple[_PlannedFile, ...], list[LedgerImportFileRefusal]]:
    """Expand each requested entry into the files to read, in request order.

    A directory is planned by the one function every frontend's import uses,
    so the files chosen and their order do not depend on who submitted. An
    over-long plan is refused whole: reading a part of it would import a
    selection the caller never named.
    """
    planned: list[_PlannedFile] = []
    refusals: list[LedgerImportFileRefusal] = []
    for position, entry in enumerate(payload.files):
        expected = None if payload.expected_source_sha256 is None else payload.expected_source_sha256[position]
        try:
            files = plan_ledger_import_sources(entry)
        except TransactionValidationError:
            refusals.append(LedgerImportFileRefusal(file_name=_safe_file_name(entry), reason_code="empty_directory"))
            continue
        if expected is not None and files != (entry,):
            refusals.append(LedgerImportFileRefusal(file_name=_safe_file_name(entry), reason_code="source_changed"))
            continue
        planned.extend((path, expected) for path in files)
    if len(planned) > MAX_LEDGER_IMPORT_FILES:
        return (), [
            LedgerImportFileRefusal(file_name=_safe_file_name(entry), reason_code="file_limit")
            for entry in payload.files
        ]
    return tuple(planned), refusals


def _compose_staged_imports(
    *,
    bucket_id: str,
    actor: str,
    payload: LedgerImportRequest,
    operation: PinnedAuthorityOperation,
    ports_factory: LedgerImportOperationPortsFactory,
) -> tuple[
    LedgerImportOperationPorts,
    list[_StagedImport],
    list[LedgerImportFileRefusal],
]:
    """Compose exact-profile ports and stage admissible source files in plan order."""
    ports = ports_factory(bucket_id=bucket_id, operation=operation)
    if ports.transaction_repository.bucket_id != bucket_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    planned, refusals = _plan_requested_files(payload)
    if payload.register_statement_account is not None and len(planned) > 1:
        # One account is registered from one statement; a folder is not one statement.
        refusals.extend(
            LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="transaction_validation")
            for path, _ in planned
        )
        planned = ()
    own_accounts = ports.own_accounts.load()
    if payload.own_account_id is not None:
        require_registered_own_account(own_accounts, payload.own_account_id)
    staged: list[_StagedImport] = []
    staged_rows = 0
    for index, (path, expected_sha256) in enumerate(planned):
        outcome = _prepare_import_file(
            path,
            bucket_id=bucket_id,
            actor=actor,
            payload=payload,
            ports=ports,
            own_accounts=own_accounts,
            remaining_row_capacity=MAX_LEDGER_IMPORT_ROWS - staged_rows,
            expected_sha256=expected_sha256,
        )
        if isinstance(outcome, LedgerImportFileRefusal):
            refusals.append(outcome)
            continue
        staged_rows += len(outcome.source.parsed_rows)
        staged.append((index, path, outcome))
    return ports, staged, refusals


def _register_statement_account(
    prepared: PreparedLedgerSourceImport,
    *,
    payload: LedgerImportRequest,
    bucket_id: str,
    ports: LedgerImportOperationPorts,
) -> tuple[PreparedLedgerSourceImport, OwnAccountId | None] | None:
    """Bind ``prepared`` to the account its statement names, registering the account when it has none.

    Returns the prepared import with its rows bound and the id of an account this call added, or
    ``None`` when the account could not be registered, in which case nothing was written.
    """
    registration = payload.register_statement_account
    statement_account = prepared.source.statement_account
    if registration is None or statement_account is None:
        return prepared, None
    fact = describe_statement_account(prepared, ports.own_accounts.load())
    if fact is not None and fact.own_account_id is not None:
        # Registered since staging, by this operator elsewhere: the statement names that account.
        return bind_prepared_import_to_own_account(prepared, fact.own_account_id), None
    try:
        with validating_governed_facts(ports.operation):
            added = apply_own_account_request(
                LedgerOwnAccountRequest(
                    profile_id=payload.profile_id,
                    action="add",
                    label=registration.label,
                    holding=registration.holding,
                    iban=statement_account,
                ),
                bucket_id=bucket_id,
                repository=ports.own_accounts,
            )
    except OwnAccountRegisterValidationError:
        return None
    if added.own_account_id is None:
        return None
    return bind_prepared_import_to_own_account(prepared, added.own_account_id), added.own_account_id


def _statement_account_facts(
    staged: list[_StagedImport],
    *,
    ports: LedgerImportOperationPorts,
) -> tuple[LedgerImportStatementAccount, ...]:
    """The account each staged statement names, against the register as it now stands."""
    register = ports.own_accounts.load()
    facts = ((index, describe_statement_account(prepared, register)) for index, _, prepared in staged)
    return tuple(
        LedgerImportStatementAccount(
            file_index=index,
            masked_iban=fact.masked_iban,
            own_account_id=fact.own_account_id,
            registrable=fact.registrable,
        )
        for index, fact in facts
        if fact is not None
    )


def _persist_staged_imports(
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    staged: list[_StagedImport],
    refusals: list[LedgerImportFileRefusal],
) -> LedgerImportExecutionResult:
    """Persist staged imports in order and append persistence refusals afterward."""
    files: list[_LedgerImportExecutionFile] = []
    registered_own_account_id: OwnAccountId | None = None
    persisted: list[_StagedImport] = []
    for index, path, prepared in staged:
        if payload.register_statement_account is not None:
            registered = _register_statement_account(prepared, payload=payload, bucket_id=bucket_id, ports=ports)
            if registered is None:
                refusals.append(
                    LedgerImportFileRefusal(file_name=_safe_file_name(path), reason_code="transaction_validation"),
                )
                continue
            prepared, registered_own_account_id = registered
        persisted.append((index, path, prepared))
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
        files.append(
            _LedgerImportExecutionFile(
                file_name=_safe_file_name(path),
                file_index=index,
                source_sha256=parsed_source_sha256(prepared),
                result=result,
            )
        )
    return LedgerImportExecutionResult(
        profile_id=payload.profile_id,
        dry_run=payload.dry_run,
        verify=payload.verify,
        period=payload.period,
        files=tuple(files),
        refused_files=tuple(refusals),
        statement_accounts=_statement_account_facts(persisted, ports=ports),
        registered_own_account_id=registered_own_account_id,
    )


async def _publish_staged_imports(
    context: OperationExecutorContext,
    *,
    bucket_id: str,
    payload: LedgerImportRequest,
    ports: LedgerImportOperationPorts,
    staged: list[_StagedImport],
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
    staged: list[_StagedImport],
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
            if execution.registered_own_account_id is not None
            or any(item.result.imported > 0 for item in execution.files)
            else OperationEffect.NONE
        )
        reference = await context.operands.put(execution, written_at=now())
        await context.events.effect(effect)
        return reference


class LedgerImportExecutor:
    """Stage source bytes first, then persist pinned parsed rows under COMMIT."""

    def __init__(
        self,
        ports: LedgerImportOperationPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Retain the explicit profile-aware composition capability."""
        self._ports = ports
        self._execution_caller_reader = execution_caller_reader

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
            actor=execution_actor_label(self._execution_caller_reader, context, supplied=bucket_id),
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


def build_ledger_import_definition(
    ports: LedgerImportOperationPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare a durable, exact-profile local import with honest effects."""
    return build_single_phase_definition(
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        request_type=LedgerImportRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerImportExecutionResult,
        executor_type=LedgerImportExecutor,
        build=lambda: LedgerImportExecutor(ports, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    )


def resolve_ledger_import_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile read access and COMMIT only for a persisted import."""
    return resolve_ledger_request_access(
        request,
        context,
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        request_type=LedgerImportRequest,
        commits=lambda payload: not payload.dry_run,
    )


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
    "LedgerImportAccountRegistration",
    "LedgerImportDiagnosticProjection",
    "LedgerImportExecutor",
    "LedgerImportFileRefusal",
    "LedgerImportOperationPorts",
    "LedgerImportOperationPortsFactory",
    "LedgerImportRequest",
    "LedgerImportResultProjection",
    "LedgerImportSourceProjection",
    "LedgerImportStatementAccount",
    "LedgerImportValidationProjection",
    "build_ledger_import_definition",
    "build_ledger_import_registration",
    "project_ledger_import_result",
    "resolve_ledger_import_access",
]
