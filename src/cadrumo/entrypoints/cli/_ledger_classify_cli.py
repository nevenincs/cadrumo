"""Bulk CSV transport helper for ``aeat app ledger classify``.

The file is read at the CLI boundary and submitted through the authenticated
profile worker; application parsing and writes stay in the ledger service.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, OutputSchema
from ...domain.transactions.enums import BusinessClassification, is_classified
from .common import bad, emit_envelope

if TYPE_CHECKING:
    from ...application.ledger.models import BulkClassifyResult


def _validate_bulk_classification_route(
    transaction_id: str | None,
    classification: BusinessClassification | None,
) -> None:
    """Reject single-row arguments before opening the bulk input file."""
    if transaction_id is not None or classification is not None:
        raise bad(
            tr("cli.ledger.classify.file_exclusive"),
        )


def _read_bulk_classification_file(file: str) -> str:
    """Read the operator-provided CSV after checking its transport path."""
    csv_path = Path(file)
    if not csv_path.exists():
        raise bad(
            tr("cli.ledger.classify.file_not_found", path=file),
        )
    return csv_path.read_text(encoding="utf-8")


def _bulk_classification_output(
    result: BulkClassifyResult,
) -> tuple[OutputSchema, list[str], list[Notice]]:
    """Build the canonical bulk payload, text lines, and all-failed warning."""
    from ._ledger_payloads import LedgerClassifyBulkResult

    lines = [
        tr(
            "cli.ledger.classify.bulk_summary",
            total=result.total,
            applied=result.applied,
            skipped=result.skipped,
            fail=len(result.failures),
        ),
    ]
    # MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE: tab-separated machine record (id, reason).
    lines.extend(f"  failed\t{failure.transaction_id}\t{failure.reason}" for failure in result.failures)
    classify_result = LedgerClassifyBulkResult.model_validate(
        {
            "total": result.total,
            "applied": result.applied,
            "skipped": result.skipped,
            "failures": [f.model_dump(mode="json") for f in result.failures],
        },
    )
    notices: list[Notice] = []
    if result.total > 0 and result.applied == 0 and result.failures:
        message = tr(
            "cli.ledger.classify.bulk_all_failed",
        )
        lines.insert(1, message)
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.classify.bulk_all_failed",
                message=message,
                context={
                    "total": str(result.total),
                    "failed": str(len(result.failures)),
                },
            ),
        )
    return classify_result, lines, notices


def ledger_classify_bulk_csv(
    ctx: typer.Context,
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str,
    actor: str | None,
) -> None:
    _validate_bulk_classification_route(transaction_id, classification)
    from .runtime_ledger_bulk_classify import run_ledger_bulk_classify

    projection = run_ledger_bulk_classify(
        ctx,
        csv_text=_read_bulk_classification_file(file),
        actor=actor,
    )
    if projection.outcome == "validation_error":
        details = "; ".join(projection.validation_messages)
        raise bad(
            tr(
                "cli.ledger.errors.command_input_invalid",
                details=details or tr("cli.ledger.errors.command_input_invalid_fallback"),
            ),
        )
    result = projection.result
    if result is None:
        from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    classify_result, lines, notices = _bulk_classification_output(result)
    emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines, notices=notices)
    if notices:
        raise typer.Exit(code=1)


def require_single_ledger_classification_request(
    *,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    reason: str | None,
) -> tuple[str, BusinessClassification]:
    """Validate and return the direct, operator-controlled classify target."""
    if transaction_id is None:
        raise bad(
            tr("cli.ledger.classify.id_required"),
        )
    if classification is None:
        raise bad(
            tr("cli.ledger.classify.classification_required"),
        )
    if not is_classified(classification):
        raise bad(
            tr("cli.ledger.classify.system_state_not_assignable", value=classification.value),
        )
    if reason is not None and not reason.strip():
        raise bad(
            tr("cli.ledger.classify.reason_empty"),
        )
    return transaction_id, classification


__all__ = ["ledger_classify_bulk_csv", "require_single_ledger_classification_request"]
