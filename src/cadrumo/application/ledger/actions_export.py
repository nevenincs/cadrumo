"""Application export service for bucket-scoped manual ledger snapshots.

The export action reads a loaded
:class:`~cadrumo.domain.transactions.TransactionCatalogue`, projects
:class:`~cadrumo.application.ledger.models.LedgerExportRow` instances, serializes them
with :func:`~cadrumo.application.export.serialize_tabular_rows`, emits a
``LEDGER_TRANSACTION_EXPORTED`` bucket event, and returns
:class:`~cadrumo.application.ledger.models.LedgerExportResult`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ...core.atomic_write import atomic_write_bytes
from ...core.decimal.formatting import format_decimal
from ...core.hashing import content_hash_hex

if TYPE_CHECKING:
    pass

from ...core.period import Period
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..export.tabular import serialize_tabular_rows
from .actions_common import (
    build_ledger_bucket_event,
    normalise_timestamp,
    optional_decimal,
    resolve_bucket_event_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
)
from .models import (
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
    "iva_category",
    "counterparty_country",
    "counterparty_identification_state",
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
    """Export rows for a :class:`~cadrumo.application.ledger.models.LedgerExportCommand`.

    Returns:
        :class:`~cadrumo.application.ledger.models.LedgerExportResult`: The export outcome.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
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
        atomic_write_bytes(command.output_path, serialized.payload)
    export_id = _ledger_export_id(
        bucket_id=command.bucket_id,
        export_format=command.export_format.value,
        sha256=serialized.sha256,
        transaction_ids=tuple(row.transaction_id for row in rows),
    )
    event = build_ledger_bucket_event(
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
    save_transaction_catalogue_and_events(
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


def _optional_text(value: str | None) -> str:
    """Render an unset optional text field as an empty export cell.

    The sibling of :func:`optional_decimal` for the string columns: an export
    row carries a blank cell, never the word ``None``.
    """
    return value or ""


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
        amount=format_decimal(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.display_counterparty,
        description=raw.description,
        source_jurisdiction=_optional_text(transaction.source_jurisdiction),
        business_classification=transaction.business_classification.value,
        business_pct=optional_decimal(transaction.business_pct),
        category_id=_optional_text(transaction.category_id),
        taxable_base=optional_decimal(transaction.taxable_base),
        iva_rate=optional_decimal(transaction.iva_rate),
        iva_amount=optional_decimal(transaction.iva_amount),
        iva_category=transaction.iva_category.value if transaction.iva_category is not None else "",
        counterparty_country=_optional_text(transaction.counterparty_country),
        counterparty_identification_state=(
            transaction.counterparty_identification_state.value
            if transaction.counterparty_identification_state is not None
            else ""
        ),
        irpf_category=_optional_text(transaction.irpf_category),
        usage_ratio_id=_optional_text(transaction.usage_ratio_id),
        prorrata_reference=_optional_text(transaction.prorrata_reference),
        purchase_invoice_evidence_id=_optional_text(transaction.purchase_invoice_evidence_id),
        attachment_ids=",".join(transaction.attachment_ids),
        notes=transaction.notes,
        created_by=_optional_text(transaction.created_by),
        created_source_command=_optional_text(transaction.source_command),
        value_in_eur=optional_decimal(transaction.value_in_eur),
        fx_rate=optional_decimal(transaction.fx_rate),
    )


def _ledger_export_id(
    *,
    bucket_id: str,
    export_format: str,
    sha256: str,
    transaction_ids: tuple[str, ...],
) -> str:
    return content_hash_hex(
        {
            "bucket_id": bucket_id,
            "export_format": export_format,
            "sha256": sha256,
            "transaction_ids": transaction_ids,
        }
    )


def _transaction_ids_digest(transaction_ids: tuple[str, ...]) -> str:
    return content_hash_hex(transaction_ids)


__all__ = [
    "export_ledger_transactions",
]
