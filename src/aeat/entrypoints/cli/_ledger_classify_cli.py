"""Bulk CSV transport helper for ``aeat app ledger classify``.

Use of :class:`TransactionCatalogueRepository` for compliance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import typer

from ...application.ledger import bulk_classify_from_csv as _bulk_classify
from ...core import resolve_active_bucket_id
from ...core.i18n import tr
from ...domain.transactions import BusinessClassification, TransactionCatalogueRepository
from ._common import _bad, _emit_envelope


class _TransactionRepo(Protocol):
    @property
    def bucket_id(self) -> str: ...


def ledger_classify_bulk_csv(
    ctx: typer.Context,
    *,
    transaction_repository: _TransactionRepo,
    transaction_id: str | None,
    classification: BusinessClassification | None,
    from_csv: str,
    actor: str | None,
) -> None:
    if transaction_id is not None or classification is not None:
        raise _bad(
            tr(
                "cli.ledger.classify.from_csv_exclusive",
                default="--from-csv cannot be combined with a transaction id or --classification.",
            ),
        )
    csv_path = Path(from_csv)
    if not csv_path.exists():
        raise _bad(
            tr("cli.ledger.classify.from_csv_not_found", path=from_csv, default=f"CSV file not found: {from_csv}"),
        )
    csv_text = csv_path.read_text(encoding="utf-8")
    result = _bulk_classify(
        bucket_id=transaction_repository.bucket_id,
        csv_text=csv_text,
        actor=actor or resolve_active_bucket_id() or "operator",
        source_command="aeat app ledger classify",
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
            default=(
                f"bulk classify: {result.total} rows, {result.applied} applied, "
                f"{result.skipped} skipped, {len(result.failures)} failed"
            ),
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
    _emit_envelope(ctx, command="ledger.classify", result=classify_result, lines=lines)


__all__ = ["ledger_classify_bulk_csv"]
