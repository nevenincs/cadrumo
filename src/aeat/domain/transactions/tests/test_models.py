"""Unit tests for transaction models and identity semantics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import (
    BusinessClassification,
    ClassificationHistoryEntry,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_transaction_id,
    normalise_movement_reference,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _sample_raw(
    *,
    provider_id: str = "provider-row-1",
    value_date: date | None = date(2026, 4, 10),
    amount: Decimal = Decimal("123.45"),
    description: str = "Office rent",
    source_row_index: int = 1,
    counterparty: str | None = "Landlord SL",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=source_row_index,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def test_provenance_source_path_is_stored_as_basename_only() -> None:
    """An absolute source path is reduced to its basename, leaking no directory."""
    provenance = RawProvenance(
        source_path=Path("/home/alice/private-statements/bank-2026.csv"),
        source_sha256="b" * 64,
        source_row_index=1,
        source_format=SourceFormat.CSV,
        ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        provider_name="CSV provider",
    )
    assert provenance.source_path == Path("bank-2026.csv")
    serialised = provenance.model_dump_json()
    assert "alice" not in serialised
    assert "private-statements" not in serialised


def test_provenance_basename_survives_rehydration_unchanged() -> None:
    """Re-validating a persisted bare filename is a no-op (no cross-OS mutation).

    The prior ``.resolve()`` validator re-anchored the path on every load, so a
    POSIX-authored bundle imported on Windows mutated the stored value and broke
    strict roundtrip equality. The basename is platform-neutral and idempotent.
    """
    original = RawProvenance(
        source_path=Path("/var/data/movements.csv"),
        source_sha256="c" * 64,
        source_row_index=3,
        source_format=SourceFormat.CSV,
        ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        provider_name="CSV provider",
    )
    rehydrated = RawProvenance.model_validate_json(original.model_dump_json())
    assert rehydrated == original
    assert rehydrated.source_path == Path("movements.csv")


def test_transaction_id_hash_is_stable_for_same_identity_tuple() -> None:
    """Equal identity tuples must derive the same transaction ID."""
    raw_a = _sample_raw(source_row_index=1, counterparty="First counterparty")
    raw_b = _sample_raw(source_row_index=99, counterparty="Second counterparty")

    tx_a = Transaction.model_validate(
        {"raw": raw_a, "direction": TransactionDirection.OUTGOING, "source_jurisdiction": "ES"},
    )
    tx_b = Transaction.model_validate(
        {"raw": raw_b, "direction": TransactionDirection.OUTGOING, "source_jurisdiction": "ES"},
    )

    assert tx_a.transaction_id == tx_b.transaction_id


def test_direction_enum_round_trips_through_json() -> None:
    """TransactionDirection must survive a JSON round-trip."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INTERNAL_TRANSFER,
            "source_jurisdiction": "ES",
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.direction is TransactionDirection.INTERNAL_TRANSFER


def test_business_pct_is_only_allowed_for_mixed_transactions() -> None:
    """business_pct must be constrained to MIXED transactions in the 0..1 range."""
    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            source_jurisdiction="ES",
            business_classification=BusinessClassification.BUSINESS,
            business_pct=Decimal("0.2"),
        )

    with pytest.raises(ValidationError):
        Transaction(
            transaction_id="x" * 64,
            raw=_sample_raw(),
            direction=TransactionDirection.OUTGOING,
            source_jurisdiction="ES",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("1.2"),
        )

    mixed = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.MIXED,
            "business_pct": Decimal("0.5"),
        },
    )

    assert mixed.business_pct == Decimal("0.5")


def test_transaction_tax_fields_are_typed_and_round_trip_through_json() -> None:
    """Manual ledger tax fields must be first-class transaction attributes."""

    original = Transaction.model_validate(
        {
            # Gross 121.00 reconstitutes the 100.00 base + 21.00 IVA triple
            # (the gross == base + iva consistency invariant on Transaction).
            "raw": _sample_raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "office-supplies",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "irpf_category": "professional-services",
            "usage_ratio_id": "ratio-office",
            "prorrata_reference": "prorrata-2026",
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("attachment-1",),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.taxable_base == Decimal("100.00")
    assert restored.iva_rate == Decimal("0.21")
    assert restored.iva_amount == Decimal("21.00")
    assert restored.irpf_category == "professional-services"
    assert restored.usage_ratio_id == "ratio-office"
    assert restored.prorrata_reference == "prorrata-2026"
    assert restored.purchase_invoice_evidence_id == "purchase-evidence-1"
    assert restored.attachment_ids == ("attachment-1",)


def test_transaction_lineage_fields_are_typed_and_round_trip_through_json() -> None:
    """Evidence provenance and edit lineage must stay on the transaction payload."""

    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "created_by": "operator-A",
            "source_command": "aeat app ledger add",
            "created_event_id": "c" * 64,
            "purchase_invoice_evidence_id": "purchase-evidence-1",
            "attachment_ids": ("a" * 64,),
            "evidence_provenance": (
                {
                    "evidence_id": "purchase-evidence-1",
                    "evidence_kind": "purchase_invoice_evidence",
                    "actor": "operator-A",
                    "source_command": "aeat app ledger add",
                    "linked_at": datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "c" * 64,
                },
            ),
            "edit_lineage": (
                {
                    "previous_transaction_id": "b" * 64,
                    "actor": "operator-B",
                    "source_command": "aeat app ledger update",
                    "edited_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "bucket_event_id": "d" * 64,
                },
            ),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.created_by == "operator-A"
    assert restored.source_command == "aeat app ledger add"
    assert restored.created_event_id == "c" * 64
    assert restored.evidence_provenance[0].evidence_kind == "purchase_invoice_evidence"
    assert restored.evidence_provenance[0].actor == "operator-A"
    assert restored.edit_lineage[0].previous_transaction_id == "b" * 64
    assert restored.edit_lineage[0].actor == "operator-B"


def test_transaction_lifecycle_lineage_round_trips_through_json() -> None:
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "lifecycle_state": TransactionLifecycleState.ARCHIVED,
            "lifecycle_lineage": (
                {
                    "previous_state": TransactionLifecycleState.ACTIVE,
                    "state": TransactionLifecycleState.ARCHIVED,
                    "actor": "operator-A",
                    "source_command": "aeat app ledger archive",
                    "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    "reason": "wrong account import",
                    "bucket_event_id": "e" * 64,
                },
            ),
        },
    )

    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].previous_state is TransactionLifecycleState.ACTIVE
    assert restored.lifecycle_lineage[0].state is TransactionLifecycleState.ARCHIVED
    assert restored.lifecycle_lineage[0].reason == "wrong account import"
    assert restored.lifecycle_lineage[0].bucket_event_id == "e" * 64


def test_transaction_lifecycle_lineage_rejects_noop_transition() -> None:
    with pytest.raises(ValidationError, match="lifecycle transition must change state"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
                "lifecycle_lineage": (
                    {
                        "previous_state": TransactionLifecycleState.ACTIVE,
                        "state": TransactionLifecycleState.ACTIVE,
                        "actor": "operator-A",
                        "source_command": "aeat app ledger archive",
                        "changed_at": datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                    },
                ),
            },
        )


def test_transaction_tax_fields_reject_negative_values_and_legacy_multi_purchase_evidence() -> None:
    """Tax substrate values and evidence refs must fail at the domain boundary."""

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "taxable_base": Decimal("-1.00"),
            },
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.OUTGOING,
                "source_jurisdiction": "ES",
                "purchase_invoice_evidence_id": ("evidence-1", "evidence-2"),
            },
        )


def test_classified_by_accepts_only_whitelisted_shapes() -> None:
    """classified_by must be auto, manual, or rule:<rule-id>."""
    auto = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
            "classified_by": "auto",
        },
    )
    manual = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
            "classified_by": "manual",
        },
    )
    rule = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
            "classified_by": "rule:vendor-map",
        },
    )
    derived = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
            "classified_by": "derived:iva-category",
        },
    )

    assert auto.classified_by == "auto"
    assert manual.classified_by == "manual"
    assert rule.classified_by == "rule:vendor-map"
    assert derived.classified_by == "derived:iva-category"

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "classified_by": "rule:",
            },
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "classified_by": "derived:",
            },
        )

    with pytest.raises(ValidationError):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
                "source_jurisdiction": "ES",
                "classified_by": "bot",
            },
        )


def test_business_classification_rejects_unclassified_literal() -> None:
    """`BusinessClassification("UNCLASSIFIED")` must raise."""
    with pytest.raises(ValueError):
        BusinessClassification("UNCLASSIFIED")


def test_classification_history_entry_round_trips_through_json() -> None:
    """`ClassificationHistoryEntry` must survive JSON round-trip with reserved slots."""
    entry = ClassificationHistoryEntry(
        business_classification=BusinessClassification.BUSINESS,
        classified_at=datetime(2026, 4, 18, 9, 0, tzinfo=UTC),
        classified_by="manual",
        reason="client invoice",
    )
    restored = ClassificationHistoryEntry.model_validate_json(entry.model_dump_json())
    assert restored == entry
    assert restored.confidence is None
    assert restored.provenance is None


# ---------------------------------------------------------------------------
# Cross-format / post-edit import-dedup fingerprint
# ---------------------------------------------------------------------------


def _ofx_sample_raw(*, provider_id: str, description: str = "Office rent") -> RawTransaction:
    """Return a sample row tagged as an OFX export of the same movement."""
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("123.45"),
        currency="EUR",
        counterparty="Landlord SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.OFX,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="OFX provider",
        ),
        raw_fields={"MEMO": description},
    )


def test_import_fingerprint_ignores_provider_id_and_file_format() -> None:
    """The same movement exported by two providers shares one fingerprint.

    `derive_import_fingerprint` keys on the movement identity (date,
    amount, normalised narrative) — not on the provider-assigned id or
    the source file format — so an OFX export and a CSV export of the
    same bank movement deduplicate against each other.
    """
    ofx_row = _ofx_sample_raw(provider_id="ofx-fitid-1")
    csv_row = _sample_raw(provider_id="csv-row-7")

    assert derive_import_fingerprint(ofx_row) == derive_import_fingerprint(csv_row)
    # The legacy transaction id still diverges — it folds in the
    # provider id — which is exactly why a coarser dedup key is needed.
    assert derive_transaction_id(ofx_row) != derive_transaction_id(csv_row)


def test_import_fingerprint_normalises_accents_and_punctuation() -> None:
    """Narratives differing only in accents / casing / punctuation match."""
    accented = _sample_raw(description="Reunió de negòcis - Òscar")
    plain = _sample_raw(description="reunio  de negocis: oscar")

    assert derive_import_fingerprint(accented) == derive_import_fingerprint(plain)


def test_import_fingerprint_distinguishes_genuinely_different_movements() -> None:
    """A different amount or date produces a different fingerprint."""
    base = _sample_raw()
    other_amount = _sample_raw(amount=Decimal("999.99"))
    other_date = _sample_raw(value_date=date(2026, 4, 11))

    assert derive_import_fingerprint(base) != derive_import_fingerprint(other_amount)
    assert derive_import_fingerprint(base) != derive_import_fingerprint(other_date)


def test_movement_day_key_groups_same_date_and_amount() -> None:
    """The coarse day key matches on date + amount regardless of narrative."""
    a = _sample_raw(description="Transferencia 1")
    b = _sample_raw(description="Pago cliente nota 4471")

    assert derive_movement_day_key(a) == derive_movement_day_key(b)
    assert derive_movement_day_key(a) != derive_movement_day_key(_sample_raw(amount=Decimal("1.00")))


def test_normalise_movement_reference_strips_accents_case_and_noise() -> None:
    """The reference normaliser collapses accents, casing, and punctuation."""
    assert normalise_movement_reference("Compra à material  ÒSCAR!") == "compraamaterialoscar"
    assert normalise_movement_reference("a-b_c") == "abc"


# ---------------------------------------------------------------------------
# source_jurisdiction axis (Spanish-source vs foreign-source)
# ---------------------------------------------------------------------------


def test_source_jurisdiction_roundtrips_es_through_json() -> None:
    """A Spanish-source value survives JSON model roundtrip with strict equality."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": "ES",
        },
    )
    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.source_jurisdiction == "ES"


def test_source_jurisdiction_is_required_but_nullable() -> None:
    """Rows must carry the axis key, while explicit unknown remains valid."""
    original = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": None,
        },
    )
    restored = Transaction.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.source_jurisdiction is None
    with pytest.raises(ValidationError, match="Field required"):
        Transaction.model_validate(
            {
                "raw": _sample_raw(),
                "direction": TransactionDirection.INCOMING,
            },
        )


def test_source_jurisdiction_rejects_non_iso_alpha2_codes() -> None:
    """Anti-tautology: the validator must reject malformed jurisdiction codes."""
    for invalid in ("INVALID", "es", "E1", "E", "ESP", "  "):
        with pytest.raises(ValidationError):
            Transaction.model_validate(
                {
                    "raw": _sample_raw(),
                    "direction": TransactionDirection.INCOMING,
                    "source_jurisdiction": invalid,
                },
            )


def test_source_jurisdiction_normalises_surrounding_whitespace() -> None:
    """Trimming yields the canonical two-letter form."""
    txn = Transaction.model_validate(
        {
            "raw": _sample_raw(),
            "direction": TransactionDirection.INCOMING,
            "source_jurisdiction": " FR ",
        },
    )

    assert txn.source_jurisdiction == "FR"
