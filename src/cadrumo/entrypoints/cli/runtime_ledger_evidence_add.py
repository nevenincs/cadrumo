"""CLI transport bridge for registered purchase-invoice evidence addition."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID

import typer

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.evidence import MediaKind, derive_keyed_purchase_invoice_evidence_id
from ...application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error

_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})


def run_ledger_evidence_add(
    ctx: typer.Context,
    *,
    source_path: str,
    supplier: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    notes: str,
    idempotency_key: str | None,
) -> LedgerEvidenceAddProjection:
    """Submit the exact-profile add and correlate its effect and full record."""
    client = bound_profile_client(ctx)
    request = LedgerEvidenceAddRequest(
        profile_id=client.profile_id,
        source_path=source_path,
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=None if taxable_base is None else display_decimal(taxable_base),
        iva_rate=None if iva_rate is None else display_decimal(iva_rate),
        iva_amount=None if iva_amount is None else display_decimal(iva_amount),
        notes=notes,
        idempotency_key=idempotency_key,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceAddProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    extension = Path(source_path).suffix.lower()
    expected_media_kind = MediaKind.IMAGE if extension in _IMAGE_EXTENSIONS else MediaKind.PDF
    keyed_replay = idempotency_key is not None and not projection.bucket_event_ids
    record = projection.record
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or record.bucket_id != str(client.profile_id)
        or record.media_kind is not expected_media_kind
        or len(projection.bucket_event_ids) not in ({0, 1} if idempotency_key is not None else {1})
        or (not projection.bucket_event_ids and idempotency_key is None)
        or any(not _event_id(event_id) for event_id in projection.bucket_event_ids)
        or record.attachment_id != record.source_sha256
        or (not keyed_replay and record.source_path != source_path)
        or record.supplier != supplier
        or record.invoice_number != invoice_number
        or record.invoice_date != invoice_date
        or not _decimal_matches(record.taxable_base, taxable_base)
        or not _decimal_matches(record.iva_rate, iva_rate)
        or not _decimal_matches(record.iva_amount, iva_amount)
        or record.notes != notes
        or (idempotency_key is not None and record.evidence_id != _keyed_id(client.profile_id, idempotency_key))
        or (idempotency_key is None and not _additive_id(record.evidence_id))
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


def _decimal_matches(projected: str | None, expected: Decimal | None) -> bool:
    if projected is None or expected is None:
        return projected is None and expected is None
    parsed = try_parse_canonical_decimal(projected, signed=False)
    return parsed is not None and display_decimal(parsed) == display_decimal(expected)


def _keyed_id(profile_id: UUID, idempotency_key: str) -> str:
    return derive_keyed_purchase_invoice_evidence_id(
        bucket_id=str(profile_id),
        idempotency_key=idempotency_key,
    )


def _additive_id(evidence_id: str) -> bool:
    return len(evidence_id) == 16 and all(character in "0123456789abcdef" for character in evidence_id)


def _event_id(event_id: str) -> bool:
    return len(event_id) == 64 and all(character in "0123456789abcdef" for character in event_id)


__all__ = ["run_ledger_evidence_add"]
