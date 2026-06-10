"""Domain record coverage for bundled ledger filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_ledger_filing_evidence_round_trips_strict_json_with_all_carriers() -> None:
    row = LedgerEvidenceRow(
        transaction_id="tx-1",
        fingerprint="a" * 64,
        booked_date="2026-01-31",
        value_date="2026-02-01",
        amount=Decimal("121.00"),
        currency="EUR",
        direction="outgoing",
        business_classification="business",
        business_pct=Decimal("0.75"),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        iva_category="domestic_general_21",
        category_id="office-supplies",
        irpf_category="professional-services",
        counterparty_eu_member_state="DE",
        fx_rate=Decimal("1.08"),
        value_in_eur=Decimal("112.04"),
        lifecycle_state="active",
        counterparty="Proveedor SL",
        description="Compra material oficina",
        purchase_invoice_evidence_id="purchase-evidence-1",
        attachment_ids=("attachment-1",),
        document_link_ids=("drive-doc-1",),
        legal_refs=("liva-art-99",),
        source_refs=("boe-a-2026-1",),
    )
    evidence = LedgerFilingEvidence(
        snapshot_fingerprint="b" * 64,
        rows=(row,),
        manual_entries=(
            ManualFactBasisEntry(
                casilla="00501",
                value="140000.00",
                kind="casilla_input",
                note="resultado contable",
            ),
        ),
        captured_at=datetime(2026, 6, 3, 12, 30, tzinfo=UTC),
    )

    restored = LedgerFilingEvidence.model_validate_json(evidence.model_dump_json())

    assert restored == evidence
    assert restored.rows[0].purchase_invoice_evidence_id == "purchase-evidence-1"
    assert restored.rows[0].attachment_ids == ("attachment-1",)
    assert restored.rows[0].document_link_ids == ("drive-doc-1",)
    assert restored.manual_entries[0].note == "resultado contable"


def test_ledger_filing_evidence_records_are_frozen_and_strict() -> None:
    row = LedgerEvidenceRow(
        transaction_id="tx-1",
        fingerprint="a" * 64,
        booked_date="2026-01-31",
        amount=Decimal("1.00"),
        currency="EUR",
        direction="incoming",
        business_classification="business",
        lifecycle_state="active",
    )

    with pytest.raises(ValidationError):
        LedgerEvidenceRow(
            transaction_id="tx-1",
            fingerprint="short",
            booked_date="2026-01-31",
            amount=Decimal("1.00"),
            currency="EUR",
            direction="incoming",
            business_classification="business",
            lifecycle_state="active",
        )

    with pytest.raises(ValidationError, match="frozen"):
        row.amount = Decimal("2.00")  # type: ignore[misc]
