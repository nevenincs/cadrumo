"""Bank statement import through the installed TUI's retained runtime session.

A preview runs the registered import as a dry run and keeps, for every file it
parsed, the digest of the bytes it read. Applying submits exactly those files
with those digests, so the worker refuses a file whose bytes changed since the
operator saw its preview instead of importing something they never reviewed.
"""

from __future__ import annotations

from pathlib import Path

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.actions_import import plan_ledger_import_sources
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.transactions.errors import TransactionValidationError
from .ledger.models import (
    LedgerImportDoorV1,
    LedgerImportFileRefusalV1,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportSourceBindingV1,
    LedgerImportSourceKind,
)
from .operations.runtime_profile_session import RuntimeProfileSession


def _result_matches(
    result: LedgerImportResultProjection,
    request: LedgerImportRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether the result answers exactly the submitted files under its settled receipt."""
    expected_effect = OperationEffect.UPDATED if not request.dry_run and result.imported > 0 else OperationEffect.NONE
    indexes = [item.file_index for item in result.source_digests]
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is expected_effect
        and result.profile_id == request.profile_id
        and result.dry_run is request.dry_run
        and len(result.validations) + len(result.refused_files) == len(request.files)
        and len(indexes) == len(set(indexes))
        and all(index < len(request.files) for index in indexes)
    )


def _outcome(result: LedgerImportResultProjection, files: tuple[Path, ...]) -> LedgerImportOutcomeV1:
    """Project the allowlisted result into the screen's terms, keeping each parsed file's digest."""
    return LedgerImportOutcomeV1(
        source_kind=LedgerImportSourceKind.BANK_STATEMENT,
        dry_run=result.dry_run,
        files=len(files),
        rows=result.rows,
        imported=result.imported,
        skipped=result.skipped,
        likely_duplicates=result.likely_duplicates,
        diagnostics=tuple(tr(item.message) for item in result.diagnostics),
        refused_files=tuple(
            LedgerImportFileRefusalV1(
                file_name=item.file_name,
                reason=tr(f"tui.ledger.import.refusal.{item.reason_code}"),
            )
            for item in result.refused_files
        ),
        sources=tuple(
            LedgerImportSourceBindingV1(path=files[item.file_index], sha256=item.sha256)
            for item in result.source_digests
        ),
    )


class RuntimeLedgerImportTuiDoorV1:
    """Preview and apply bank statement imports for the exact TUI profile and session."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every import."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Read the planned files without writing and report what applying them would do."""
        _require_bank_statement(request)
        files = tuple(path.absolute() for path in plan_ledger_import_sources(request.path))
        return await self._run(request, files=files, expected=None, dry_run=True)

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Import exactly the files the preview read, each refused if its bytes changed since."""
        _require_bank_statement(request)
        sources = request.previewed_sources
        if sources is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if not sources:
            raise TransactionValidationError(translated_message="tui.ledger.import.nothing_previewed")
        files = tuple(item.path for item in sources)
        return await self._run(request, files=files, expected=tuple(item.sha256 for item in sources), dry_run=False)

    async def _run(
        self,
        request: LedgerImportRequestV1,
        *,
        files: tuple[Path, ...],
        expected: tuple[str, ...] | None,
        dry_run: bool,
    ) -> LedgerImportOutcomeV1:
        submitted = LedgerImportRequest(
            profile_id=self._session.profile_id,
            files=files,
            provider=request.provider,
            dry_run=dry_run,
            own_account_id=request.own_account_id,
            expected_source_sha256=expected,
        )

        def settle(
            result: LedgerImportResultProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not _result_matches(result, submitted, condition, terminal):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        result = await self._session.run_operation(
            submitted,
            definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
            result_type=LedgerImportResultProjection,
            settle=settle,
            explain_failure=True,
        )
        return _outcome(result, files)


def _require_bank_statement(request: LedgerImportRequestV1) -> None:
    """Invoice books have no registered preview, so this door reads bank statements only."""
    if request.source_kind is not LedgerImportSourceKind.BANK_STATEMENT:
        raise TransactionValidationError(translated_message="tui.ledger.import.invoice_book_unavailable")


def compose_runtime_ledger_import_door(*, client: RuntimeFrontendClient, profile_label: str) -> LedgerImportDoorV1:
    """Bind the import screen to the runtime client retained by its workbench."""
    return RuntimeLedgerImportTuiDoorV1(client, profile_label=profile_label)


__all__ = ["RuntimeLedgerImportTuiDoorV1", "compose_runtime_ledger_import_door"]
