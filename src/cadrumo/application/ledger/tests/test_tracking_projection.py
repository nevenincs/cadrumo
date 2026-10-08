"""Closed runtime projections preserve the canonical ledger track facts."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
)
from ....domain.transactions.enums import TransactionLifecycleState
from ....domain.transactions.lineage_models import (
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
)
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_manual import ledger_transaction_tracking_payload
from ..models import LedgerTransactionTrackingPayload
from ..tracking_projection import (
    LedgerImportedProvenanceProjection,
    LedgerParticipationProjection,
    LedgerTrackingProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _tracking_payload() -> LedgerTransactionTrackingPayload:
    occurred_at = datetime(2026, 5, 5, 10, 15, tzinfo=UTC)
    return LedgerTransactionTrackingPayload(
        transaction_id="a" * 64,
        created_event_id=None,
        evidence_provenance=(
            TransactionEvidenceProvenanceEntry(
                evidence_id="purchase-proof-1",
                evidence_kind="purchase_invoice_evidence",
                actor="operator",
                source_command="aeat app ledger attach",
                linked_at=occurred_at,
                bucket_event_id="b" * 64,
            ),
        ),
        edit_lineage=(
            TransactionEditLineageEntry(
                previous_transaction_id="c" * 64,
                actor="operator",
                source_command="aeat app ledger update",
                edited_at=occurred_at,
                bucket_event_id="d" * 64,
            ),
        ),
        lifecycle_state=TransactionLifecycleState.ARCHIVED.value,
        lifecycle_lineage=(
            TransactionLifecycleLineageEntry(
                previous_state=TransactionLifecycleState.ACTIVE,
                state=TransactionLifecycleState.ARCHIVED,
                actor="operator",
                source_command="aeat app ledger archive",
                changed_at=occurred_at,
                reason="reviewed",
                bucket_event_id="e" * 64,
            ),
        ),
    )


def test_tracking_projection_matches_canonical_json_and_rejects_extra_fields() -> None:
    payload = _tracking_payload()

    projection = LedgerTrackingProjection.from_payload(payload)

    assert projection.model_dump(mode="json") == payload.model_dump(mode="json")
    assert [entry.evidence_id for entry in projection.evidence_provenance] == ["purchase-proof-1"]
    assert projection.created_event_id is None
    assert projection.lifecycle_lineage[0].previous_state == "ACTIVE"

    widened = json.loads(projection.model_dump_json())
    widened["raw_fields"] = {"account": "private"}
    with pytest.raises(ValidationError):
        LedgerTrackingProjection.model_validate_json(json.dumps(widened))


def _participation(
    *,
    revision_id: str,
    revision_state: str,
    filing_record_id: str | None = None,
    justificante_reference: str | None = None,
) -> TransactionRevisionParticipation:
    period = Period.from_year_and_code(2026, "1T")
    return TransactionRevisionParticipation(
        calculation_revision_id=revision_id,
        work_unit_id="f" * 64,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_state=revision_state,
        filing_record_id=filing_record_id,
        justificante_reference=justificante_reference,
    )


def test_participation_projection_preserves_period_shape_order_and_empty_absence() -> None:
    verified = _participation(revision_id="1" * 64, revision_state="verificado")
    filed = _participation(
        revision_id="2" * 64,
        revision_state="presentado",
        filing_record_id="3" * 64,
        justificante_reference="CSV-2026-303-0001",
    )
    index = TransactionRevisionParticipationIndex(
        transaction_id="4" * 64,
        participations=(verified, filed),
    )

    projected = LedgerParticipationProjection.from_index(index)

    assert projected is not None
    assert [item.model_dump(mode="json") for item in projected] == [
        item.model_dump(mode="json") for item in index.participations
    ]
    assert projected[0].period.model_dump(mode="json") == {"filing_year": 2026, "code": "1T"}
    assert projected[0].filing_record_id is None
    assert projected[1].filing_record_id == "3" * 64
    assert (
        LedgerParticipationProjection.from_index(
            TransactionRevisionParticipationIndex(transaction_id="4" * 64),
        )
        is None
    )


def _transaction(*, created_event_id: str | None = None) -> Transaction:
    ingested_at = datetime(2026, 5, 6, 9, 30, tzinfo=UTC)
    raw = RawTransaction(
        provider_transaction_id="tracking-import-row",
        booked_date=date(2026, 5, 5),
        value_date=None,
        amount=Decimal("42.50"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="Imported tracking projection fixture",
        provenance=RawProvenance(
            source_path=Path(__file__).parent / "sensitive-directory-name" / "statement.csv",
            source_sha256="6" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=ingested_at,
            provider_name="bank-importer",
        ),
        raw_fields={"raw-column-secret": "do-not-project"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": "OUTGOING",
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_event_id": created_event_id,
            "import_fingerprint": "7" * 64,
            "created_at": ingested_at,
            "modified_at": ingested_at,
        },
    )


def test_imported_provenance_projection_exposes_basename_and_text_facts_only() -> None:
    transaction = _transaction()

    projection = LedgerImportedProvenanceProjection.from_transaction(transaction)

    assert projection is not None
    assert projection.provider_name == "bank-importer"
    assert projection.source_filename == "statement.csv"
    assert projection.source_row_index == 7
    assert projection.ingested_at == transaction.raw.provenance.ingested_at.isoformat()
    assert projection.import_fingerprint == "7" * 64
    serialized = projection.model_dump_json()
    assert "sensitive-directory-name" not in serialized
    assert "raw-column-secret" not in serialized
    assert "do-not-project" not in serialized
    assert "6" * 64 not in serialized
    assert (
        LedgerImportedProvenanceProjection.from_transaction(
            _transaction(created_event_id="8" * 64),
        )
        is None
    )


def test_tracking_projection_is_the_canonical_action_payload() -> None:
    transaction = _transaction(created_event_id="9" * 64)

    canonical = ledger_transaction_tracking_payload(transaction)
    projection = LedgerTrackingProjection.from_payload(canonical)

    assert projection.transaction_id == transaction.transaction_id
    assert projection.model_dump(mode="json") == canonical.model_dump(mode="json")
