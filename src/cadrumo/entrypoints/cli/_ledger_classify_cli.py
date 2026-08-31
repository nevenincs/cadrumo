"""Bulk CSV transport helper for ``aeat app ledger classify``.

Bulk classification writes through :class:`TransactionCatalogueRepository` when
the caller supplies the concrete repository, preserving the active ledger
catalogue path.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.ledger.actions_classification import bulk_classify_from_csv as _bulk_classify
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n._render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.transactions.enums import BusinessClassification, is_classified
from ._common import _bad, emit_envelope
from ._ledger_support import _TransactionRepo


def ledger_classify_bulk_csv(
    ctx: typer.Context,
    *,
    transaction_repository: _TransactionRepo,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    file: str,
    actor: str | None,
) -> None:
    if transaction_id is not None or classification is not None:
        raise _bad(
            tr("cli.ledger.classify.file_exclusive"),
        )
    csv_path = Path(file)
    if not csv_path.exists():
        raise _bad(
            tr("cli.ledger.classify.file_not_found", path=file),
        )
    csv_text = csv_path.read_text(encoding="utf-8")
    result = _bulk_classify(
        bucket_id=transaction_repository.bucket_id,
        csv_text=csv_text,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger classify --file",
        transaction_repository=transaction_repository
        if isinstance(transaction_repository, TransactionCatalogueRepository)
        else None,
    )
    lines = [
        tr(
            "cli.ledger.classify.bulk_summary",
            total=result.total,
            applied=result.applied,
            skipped=result.skipped,
            fail=len(result.failures),
        ),
    ]
    from ._ledger_payloads import LedgerClassifyBulkResult

    for failure in result.failures:
        # MACHINE-FORMAT-RATIONALE-LEDGER-BULK-CLASSIFY-FAILURE: tab-separated machine record (id, reason).
        lines.append(f"  failed\t{failure.transaction_id}\t{failure.reason}")
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
        raise _bad(
            tr("cli.ledger.classify.id_required"),
        )
    if classification is None:
        raise _bad(
            tr("cli.ledger.classify.classification_required"),
        )
    if not is_classified(classification):
        raise _bad(
            tr("cli.ledger.classify.system_state_not_assignable", value=classification.value),
        )
    if reason is not None and not reason.strip():
        raise _bad(
            tr("cli.ledger.classify.reason_empty"),
        )
    return transaction_id, classification


__all__ = ["ledger_classify_bulk_csv", "require_single_ledger_classification_request"]
