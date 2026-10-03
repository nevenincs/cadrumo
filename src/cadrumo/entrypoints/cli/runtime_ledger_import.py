"""Run ledger statement imports through exact-profile runtime custody."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer

from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    MAX_LEDGER_IMPORT_FILES,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ...application.operations.public_period import PublicPeriod
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.transactions.errors import TransactionValidationError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def require_ledger_import_correlation(
    completed: RegisteredOperationCompletion[LedgerImportResultProjection],
    profile_id: UUID,
    files: tuple[Path, ...],
    dry_run: bool,
    verify: bool,
    period: Period | None,
) -> None:
    """Require ledger import correlation."""
    result = completed.projection
    expected_effect = OperationEffect.UPDATED if not dry_run and result.imported > 0 else OperationEffect.NONE
    invalid = (
        invalid_ledger_import_receipt(completed, result, profile_id, expected_effect)
        or invalid_ledger_import_selection(result, dry_run, verify, period)
        or len(result.validations) != len(result.sources)
        or (len(result.validations) + len(result.refused_files) != len(files))
    )
    if invalid:
        raise invalid_completion_error(completed)


def import_ledger_sources_for_cli(
    ctx: typer.Context,
    *,
    files: tuple[Path, ...],
    provider: LedgerProviderID,
    dry_run: bool,
    verify: bool,
    verify_source: Path | None,
    period: Period | None,
) -> RegisteredOperationCompletion[LedgerImportResultProjection]:
    """Submit staged source paths to the exact profile and correlate the result."""
    if not files or len(files) > MAX_LEDGER_IMPORT_FILES:
        raise TransactionValidationError("ledger import source file count is outside the registered operation limit")
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerImportRequest(
            profile_id=client.profile_id,
            # The worker has its own storage-root cwd. Anchor the caller's
            # paths without resolving symlinks or changing source labels.
            files=tuple(path.absolute() for path in files),
            provider=provider,
            dry_run=dry_run,
            verify=verify,
            verify_source=verify_source.absolute() if verify_source is not None else None,
            period=PublicPeriod.from_period(period) if period is not None else None,
        ),
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerImportResultProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    require_ledger_import_correlation(completed, client.profile_id, files, dry_run, verify, period)
    return completed


__all__ = ["import_ledger_sources_for_cli"]


def invalid_ledger_import_receipt(
    completed: RegisteredOperationCompletion[LedgerImportResultProjection],
    result: LedgerImportResultProjection,
    profile_id: UUID,
    expected_effect: OperationEffect,
) -> bool:
    """Invalid ledger import receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (result.profile_id != profile_id)
        or (result.bucket_id != str(profile_id))
    )


def invalid_ledger_import_selection(
    result: LedgerImportResultProjection, dry_run: bool, verify: bool, period: Period | None
) -> bool:
    """Invalid ledger import selection."""
    return (
        result.dry_run is not dry_run
        or result.verify is not verify
        or result.period != (PublicPeriod.from_period(period) if period is not None else None)
    )
