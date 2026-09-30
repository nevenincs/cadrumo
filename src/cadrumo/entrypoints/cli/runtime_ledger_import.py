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
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.transactions.errors import TransactionValidationError
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


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
            files=files,
            provider=provider,
            dry_run=dry_run,
            verify=verify,
            verify_source=verify_source,
            period=PublicPeriod.from_period(period) if period is not None else None,
        ),
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerImportResultProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    expected_effect = OperationEffect.UPDATED if not dry_run and result.imported > 0 else OperationEffect.NONE
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or result.profile_id != client.profile_id
        or result.bucket_id != str(client.profile_id)
        or result.dry_run is not dry_run
        or result.verify is not verify
        or result.period != (PublicPeriod.from_period(period) if period is not None else None)
        or len(result.validations) != len(result.sources)
        or len(result.validations) + len(result.refused_files) != len(files)
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return completed


__all__ = ["import_ledger_sources_for_cli"]
