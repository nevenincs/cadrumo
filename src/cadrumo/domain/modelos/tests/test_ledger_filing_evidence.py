"""Domain record coverage for bundled ledger filing evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.ids import LegalRefId, SourceRefId
from .._ledger_filing_snapshot import LedgerEvidenceRow, LedgerFilingEvidence, ManualFactBasisEntry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_EVIDENCE_CASILLA: CasillaId = validated_casilla_id("00501")
_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-37-1992:art-99",)
_SOURCE_REFS: tuple[SourceRefId, ...] = ("boe-modelo-303-2025-form",)
_TRANSACTION_ID = "c" * 64


def test_ledger_filing_evidence_round_trips_strict_json_with_all_carriers() -> None:
    row = LedgerEvidenceRow(
        transaction_id=_TRANSACTION_ID,
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
        iva_category="domestic_general",
        category_id="office-supplies",
        irpf_category="professional-services",
        counterparty_country="DE",
        fx_rate=Decimal("1.08"),
        value_in_eur=Decimal("112.04"),
        lifecycle_state="active",
        counterparty="Proveedor SL",
        description="Compra material oficina",
        purchase_invoice_evidence_id="purchase-evidence-1",
        attachment_ids=("attachment-1",),
        document_link_ids=("drive-doc-1",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    evidence = LedgerFilingEvidence(
        snapshot_fingerprint="b" * 64,
        rows=(row,),
        manual_entries=(
            ManualFactBasisEntry(
                casilla_id=_EVIDENCE_CASILLA,
                value="140000.00",
                kind="casilla_input",
                note="resultado contable",
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
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
        transaction_id=_TRANSACTION_ID,
        fingerprint="a" * 64,
        booked_date="2026-01-31",
        amount=Decimal("1.00"),
        currency="EUR",
        direction="incoming",
        business_classification="business",
        lifecycle_state="active",
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )

    with pytest.raises(ValidationError):
        LedgerEvidenceRow(
            transaction_id=_TRANSACTION_ID,
            fingerprint="short",
            booked_date="2026-01-31",
            amount=Decimal("1.00"),
            currency="EUR",
            direction="incoming",
            business_classification="business",
            lifecycle_state="active",
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
        )

    with pytest.raises(ValidationError, match="frozen"):
        row.__setattr__("amount", Decimal("2.00"))


def test_ledger_filing_evidence_rejects_ungrounded_rows_and_manual_entries() -> None:
    # Deliberately omits the required legal_refs / source_refs grounding field to prove
    # pydantic's own validation refuses it; model_validate (not the constructor) is used
    # so the omission is a runtime ValidationError, not a static missing-argument error.
    with pytest.raises(ValidationError, match="legal_refs"):
        LedgerEvidenceRow.model_validate(
            {
                "transaction_id": _TRANSACTION_ID,
                "fingerprint": "a" * 64,
                "booked_date": "2026-01-31",
                "amount": Decimal("1.00"),
                "currency": "EUR",
                "direction": "incoming",
                "business_classification": "business",
                "lifecycle_state": "active",
                "source_refs": _SOURCE_REFS,
            },
        )

    with pytest.raises(ValidationError, match="source_refs"):
        ManualFactBasisEntry.model_validate(
            {
                "casilla_id": _EVIDENCE_CASILLA,
                "value": "140000.00",
                "legal_refs": _LEGAL_REFS,
            },
        )


def test_ledger_filing_evidence_rejects_blank_grounding_refs() -> None:
    with pytest.raises(ValidationError, match="legal_refs"):
        LedgerEvidenceRow(
            transaction_id=_TRANSACTION_ID,
            fingerprint="a" * 64,
            booked_date="2026-01-31",
            amount=Decimal("1.00"),
            currency="EUR",
            direction="incoming",
            business_classification="business",
            lifecycle_state="active",
            legal_refs=("",),
            source_refs=_SOURCE_REFS,
        )

    with pytest.raises(ValidationError, match="source_refs"):
        ManualFactBasisEntry(
            casilla_id=_EVIDENCE_CASILLA,
            value="140000.00",
            legal_refs=_LEGAL_REFS,
            source_refs=(" ",),
        )
