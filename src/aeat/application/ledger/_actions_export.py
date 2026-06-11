"""Application services for bucket-scoped manual ledger transactions.

Services operate over a :class:`TransactionCatalogueRepository` for ledger
state, a :class:`BucketEventHistoryRepository` for durable audit events, and
an optional :class:`InvoiceCatalogueRepository` for purchase-invoice evidence
cascade on removal. The inner functions accept a :class:`TransactionCatalogue`
or :class:`InvoiceCatalogue` directly when the caller supplies pre-loaded data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from ...core import Period
from ...domain.buckets import (
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.transactions import (
    Transaction,
    TransactionCatalogue,
    TransactionLifecycleState,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ..export import serialize_tabular_rows
from ._actions_common import (
    _bucket_event_repository,
    _build_bucket_event,
    _decimal_to_string,
    _normalise_timestamp,
    _optional_decimal,
    _save_transaction_catalogue_and_events,
    _transaction_repository,
)
from ._models import (
    LedgerExportCommand,
    LedgerExportResult,
    LedgerExportRow,
)

_LEDGER_EXPORT_FIELDNAMES = (
    "bucket_id",
    "transaction_id",
    "lifecycle_state",
    "booked_date",
    "value_date",
    "effective_date",
    "amount",
    "currency",
    "direction",
    "counterparty",
    "description",
    "source_jurisdiction",
    "business_classification",
    "business_pct",
    "category_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "usage_ratio_id",
    "prorrata_reference",
    "purchase_invoice_evidence_id",
    "attachment_ids",
    "notes",
    "created_by",
    "created_source_command",
    "value_in_eur",
    "fx_rate",
)


def export_ledger_transactions(
    command: LedgerExportCommand,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LedgerExportResult:
    """Export canonical bucket-local ledger transaction rows and emit an audit event.

    Returns:
        :class:`LedgerExportResult`: The export outcome.
    """
    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    rows = _ledger_export_rows(
        catalogue,
        bucket_id=command.bucket_id,
        include_inactive=command.include_inactive,
        period=command.period,
    )
    serialized = serialize_tabular_rows(
        tuple(row.model_dump(mode="json") for row in rows),
        fieldnames=_LEDGER_EXPORT_FIELDNAMES,
        export_format=command.export_format,
    )
    if command.output_path is not None:
        command.output_path.write_bytes(serialized.payload)
    export_id = _ledger_export_id(
        bucket_id=command.bucket_id,
        export_format=command.export_format.value,
        sha256=serialized.sha256,
        transaction_ids=tuple(row.transaction_id for row in rows),
    )
    event = _build_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_EXPORTED,
        occurred_at=now,
        actor=command.actor,
        object_type=BucketEventObjectType.LEDGER_EXPORT,
        object_id=export_id,
        payload={
            "source_command": command.source_command,
            "export_format": command.export_format.value,
            "include_inactive": str(command.include_inactive).lower(),
            "row_count": str(serialized.row_count),
            "byte_size": str(serialized.byte_size),
            "sha256": serialized.sha256,
            "output_path": str(command.output_path) if command.output_path is not None else "",
            "transaction_ids_sha256": _transaction_ids_digest(tuple(row.transaction_id for row in rows)),
            "first_transaction_id": rows[0].transaction_id if rows else "",
            "last_transaction_id": rows[-1].transaction_id if rows else "",
        },
    )
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=catalogue,
        events=(event,),
    )
    return LedgerExportResult(
        bucket_id=command.bucket_id,
        export_id=export_id,
        export_format=serialized.format,
        media_type=serialized.media_type,
        filename_extension=serialized.filename_extension,
        row_count=serialized.row_count,
        byte_size=serialized.byte_size,
        sha256=serialized.sha256,
        fieldnames=serialized.fieldnames,
        rows=rows,
        payload=serialized.payload,
        bucket_event_ids=(event.event_id,),
    )


def _ledger_export_rows(
    catalogue: TransactionCatalogue,
    *,
    bucket_id: str,
    include_inactive: bool,
    period: Period | None = None,
) -> tuple[LedgerExportRow, ...]:
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if (include_inactive or transaction.lifecycle_state is TransactionLifecycleState.ACTIVE)
        and (period is None or period.contains(transaction.raw.value_date or transaction.raw.booked_date))
    )
    return tuple(
        _ledger_export_row(bucket_id=bucket_id, transaction=transaction)
        for transaction in sorted(
            transactions,
            key=lambda item: (
                item.raw.value_date or item.raw.booked_date,
                item.transaction_id,
            ),
        )
    )


def _ledger_export_row(*, bucket_id: str, transaction: Transaction) -> LedgerExportRow:
    raw = transaction.raw
    effective_date = raw.value_date or raw.booked_date
    return LedgerExportRow(
        bucket_id=bucket_id,
        transaction_id=transaction.transaction_id,
        lifecycle_state=transaction.lifecycle_state.value,
        booked_date=raw.booked_date.isoformat(),
        value_date="" if raw.value_date is None else raw.value_date.isoformat(),
        effective_date=effective_date.isoformat(),
        amount=_decimal_to_string(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.display_counterparty,
        description=raw.description,
        business_classification=transaction.business_classification.value,
        business_pct=_optional_decimal(transaction.business_pct),
        category_id=transaction.category_id or "",
        taxable_base=_optional_decimal(transaction.taxable_base),
        iva_rate=_optional_decimal(transaction.iva_rate),
        iva_amount=_optional_decimal(transaction.iva_amount),
        irpf_category=transaction.irpf_category or "",
        usage_ratio_id=transaction.usage_ratio_id or "",
        prorrata_reference=transaction.prorrata_reference or "",
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id or "",
        attachment_ids=",".join(transaction.attachment_ids),
        notes=transaction.notes,
        created_by=transaction.created_by or "",
        created_source_command=transaction.source_command or "",
        value_in_eur=_optional_decimal(transaction.value_in_eur),
        fx_rate=_optional_decimal(transaction.fx_rate),
    )


def _ledger_export_id(
    *,
    bucket_id: str,
    export_format: str,
    sha256: str,
    transaction_ids: tuple[str, ...],
) -> str:
    payload = json.dumps(
        {
            "bucket_id": bucket_id,
            "export_format": export_format,
            "sha256": sha256,
            "transaction_ids": transaction_ids,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _transaction_ids_digest(transaction_ids: tuple[str, ...]) -> str:
    encoded = json.dumps(transaction_ids, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
