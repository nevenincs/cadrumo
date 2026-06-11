"""Unit tests for the typed ``--set KEY=VALUE`` parser."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._edit import (
    DeclaracionEditSpec,
    EditClause,
    EditParseError,
    InvoiceEditKey,
    InvoiceEditSpec,
    LedgerEditKey,
    LedgerEditSpec,
    parse_edit_clause,
    parse_edit_clauses,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------
# Parser substrate
# ---------------------------------------------------------------------


def test_parse_edit_clause_round_trips_canonical_pair() -> None:
    clause = parse_edit_clause("category=software")
    assert clause.key == "category"
    assert clause.raw_value == "software"


def test_parse_edit_clause_lowercases_and_trims_key() -> None:
    clause = parse_edit_clause("  CATEGORY  =software")
    assert clause.key == "category"


def test_parse_edit_clause_trims_value() -> None:
    clause = parse_edit_clause("category=  software ")
    assert clause.raw_value == "software"


def test_parse_edit_clause_rejects_missing_equals() -> None:
    raw = "category software"
    with pytest.raises(EditParseError, match=r"missing-equals") as exc:
        parse_edit_clause(raw)
    assert exc.value.reason == "missing-equals"
    assert exc.value.raw_token == raw
    assert exc.value.translated_message == "review.edit.errors.parse_failed"
    assert exc.value.context == {"reason": "missing-equals"}


def test_parse_edit_clause_rejects_empty_key() -> None:
    with pytest.raises(EditParseError, match=r"empty-key") as exc:
        parse_edit_clause("=software")
    assert exc.value.reason == "empty-key"


def test_parse_edit_clause_rejects_empty_value() -> None:
    with pytest.raises(EditParseError, match=r"empty-value") as exc:
        parse_edit_clause("category=")
    assert exc.value.reason == "empty-value"


def test_parse_edit_clause_rejects_blank_value() -> None:
    with pytest.raises(EditParseError, match=r"empty-value|blank"):
        parse_edit_clause("category=   ")


def test_parse_edit_clauses_preserves_order() -> None:
    clauses = parse_edit_clauses(["category=software", "business.share=1.0"])
    assert [c.key for c in clauses] == ["category", "business.share"]


def test_edit_clause_is_frozen() -> None:
    from pydantic import ValidationError

    clause = EditClause(key="category", raw_value="software")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        clause.raw_value = "changed"


# ---------------------------------------------------------------------
# LedgerEditSpec
# ---------------------------------------------------------------------


def test_ledger_spec_parses_category_share_and_reference_together() -> None:
    """Parse ledger category, share, and reference edits together."""
    spec = LedgerEditSpec.from_strings(
        [
            "category=software",
            "business.share=1.0",
            "reference=invoice-1",
        ],
    )
    assert spec.category == "software"
    assert spec.business_share == Decimal("1.0")
    assert spec.reference == "invoice-1"


def test_ledger_spec_parses_document_path() -> None:
    spec = LedgerEditSpec.from_strings(["document.path=./receipts/receipt-901.pdf"])
    assert spec.document_path == Path("./receipts/receipt-901.pdf")


def test_ledger_spec_parses_comments() -> None:
    spec = LedgerEditSpec.from_strings(["comments=invoice-reviewed"])
    assert spec.comments == "invoice-reviewed"


def test_ledger_spec_business_share_accepts_decimal_zero() -> None:
    spec = LedgerEditSpec.from_strings(["business.share=0"])
    assert spec.business_share == Decimal("0")


def test_ledger_spec_business_share_accepts_decimal_one() -> None:
    spec = LedgerEditSpec.from_strings(["business.share=1"])
    assert spec.business_share == Decimal("1")


def test_ledger_spec_business_share_rejects_above_one() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger-business-share") as exc:
        LedgerEditSpec.from_strings(["business.share=1.5"])
    assert exc.value.reason == "invalid-value-ledger-business-share"


def test_ledger_spec_business_share_rejects_negative() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger-business-share") as exc:
        LedgerEditSpec.from_strings(["business.share=-0.1"])
    assert exc.value.reason == "invalid-value-ledger-business-share"


def test_ledger_spec_business_share_rejects_non_decimal() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger-business-share") as exc:
        LedgerEditSpec.from_strings(["business.share=full"])
    assert exc.value.reason == "invalid-value-ledger-business-share"


def test_ledger_spec_rejects_unknown_key() -> None:
    with pytest.raises(EditParseError, match=r"unknown-key-ledger") as exc:
        LedgerEditSpec.from_strings(["base=120.00"])
    assert exc.value.reason == "unknown-key-ledger"


def test_ledger_spec_rejects_duplicate_key() -> None:
    with pytest.raises(EditParseError, match=r"duplicate-key-ledger") as exc:
        LedgerEditSpec.from_strings(["category=a", "category=b"])
    assert exc.value.reason == "duplicate-key-ledger"
    assert exc.value.context == {"reason": "duplicate-key-ledger", "key": "category"}


def test_ledger_spec_parse_error_message_omits_sensitive_edit_value() -> None:
    sensitive_path = "C:/Users/example/Documents/client-tax-id-12345678Z.pdf"
    with pytest.raises(EditParseError) as exc:
        LedgerEditSpec.from_strings([f"business.share={sensitive_path}"])

    assert exc.value.reason == "invalid-value-ledger-business-share"
    assert exc.value.raw_token == f"--set business.share={sensitive_path}"
    assert exc.value.context == {"reason": "invalid-value-ledger-business-share", "key": "business.share"}
    assert sensitive_path not in str(exc.value)
    assert sensitive_path not in repr(exc.value.context)


def test_ledger_spec_empty_returns_empty_spec() -> None:
    spec = LedgerEditSpec.from_strings([])
    assert spec.clauses == ()
    assert spec.category is None
    assert spec.business_share is None


# ---------------------------------------------------------------------
# InvoiceEditSpec
# ---------------------------------------------------------------------


def test_invoice_spec_parses_base_iva_and_payment_edits_together() -> None:
    """Parse invoice base, IVA, and payment-id edits together."""
    spec = InvoiceEditSpec.from_strings(
        [
            "base=120.00",
            "iva.rate=21",
            "iva.amount=25.20",
            "payment.id=row_1_1",
        ],
    )
    assert spec.base == Decimal("120.00")
    assert spec.iva_rate == Decimal("21")
    assert spec.iva_amount == Decimal("25.20")
    assert spec.payment_id == "row_1_1"


def test_invoice_spec_parses_retention_fields() -> None:
    spec = InvoiceEditSpec.from_strings(
        [
            "retention.rate=15",
            "retention.amount=18.00",
        ],
    )
    assert spec.retention_rate == Decimal("15")
    assert spec.retention_amount == Decimal("18.00")


def test_invoice_spec_parses_iva_category_as_free_text() -> None:
    spec = InvoiceEditSpec.from_strings(["iva.category=intracomunitario"])
    assert spec.iva_category == "intracomunitario"


def test_invoice_spec_rejects_unknown_key() -> None:
    with pytest.raises(EditParseError, match=r"unknown-key-invoice") as exc:
        InvoiceEditSpec.from_strings(["category=software"])
    assert exc.value.reason == "unknown-key-invoice"


def test_invoice_spec_rejects_non_decimal_base() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-invoice-base") as exc:
        InvoiceEditSpec.from_strings(["base=tbd"])
    assert exc.value.reason == "invalid-value-invoice-base"


def test_invoice_spec_rejects_duplicate_key() -> None:
    with pytest.raises(EditParseError, match=r"duplicate-key-invoice") as exc:
        InvoiceEditSpec.from_strings(["base=1.0", "base=2.0"])
    assert exc.value.reason == "duplicate-key-invoice"


def test_invoice_spec_empty_returns_empty_spec() -> None:
    spec = InvoiceEditSpec.from_strings([])
    assert spec.clauses == ()
    assert all(
        getattr(spec, name) is None
        for name in (
            "base",
            "iva_rate",
            "iva_amount",
            "iva_category",
            "retention_rate",
            "retention_amount",
            "payment_id",
            "reference",
            "comments",
            "document_path",
        )
    )


# ---------------------------------------------------------------------
# DeclaracionEditSpec
# ---------------------------------------------------------------------


def test_declaration_spec_parses_casilla_override() -> None:
    """Parse a declaration casilla override."""
    spec = DeclaracionEditSpec.from_strings(["casilla.71=1200.00"])
    assert spec.casilla_edits == {"71": Decimal("1200.00")}


def test_declaration_spec_parses_multi_casilla_edits() -> None:
    spec = DeclaracionEditSpec.from_strings(
        [
            "casilla.71=1200.00",
            "casilla.03=-500.50",
            "casilla.12345=0",
        ],
    )
    assert spec.casilla_edits == {
        "71": Decimal("1200.00"),
        "03": Decimal("-500.50"),
        "12345": Decimal("0"),
    }


def test_declaration_spec_rejects_non_casilla_key() -> None:
    with pytest.raises(EditParseError, match=r"unknown-key-declaration") as exc:
        DeclaracionEditSpec.from_strings(["category=software"])
    assert exc.value.reason == "unknown-key-declaration"


def test_declaration_spec_rejects_short_casilla_id() -> None:
    with pytest.raises(EditParseError, match=r"unknown-key-declaration") as exc:
        DeclaracionEditSpec.from_strings(["casilla.1=10"])
    assert exc.value.reason == "unknown-key-declaration"


def test_declaration_spec_rejects_long_casilla_id() -> None:
    with pytest.raises(EditParseError, match=r"unknown-key-declaration") as exc:
        DeclaracionEditSpec.from_strings(["casilla.123456=10"])
    assert exc.value.reason == "unknown-key-declaration"


def test_declaration_spec_rejects_non_decimal_value() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-declaration-casilla") as exc:
        DeclaracionEditSpec.from_strings(["casilla.71=tbd"])
    assert exc.value.reason == "invalid-value-declaration-casilla"


def test_declaration_spec_rejects_duplicate_casilla_key() -> None:
    with pytest.raises(EditParseError, match=r"duplicate-key-declaration") as exc:
        DeclaracionEditSpec.from_strings(["casilla.71=1.0", "casilla.71=2.0"])
    assert exc.value.reason == "duplicate-key-declaration"


def test_declaration_spec_empty_returns_empty_spec() -> None:
    spec = DeclaracionEditSpec.from_strings([])
    assert spec.clauses == ()
    assert spec.casilla_edits == {}


# ---------------------------------------------------------------------
# Frozen / consistency invariants
# ---------------------------------------------------------------------


def test_ledger_spec_is_frozen() -> None:
    from pydantic import ValidationError

    spec = LedgerEditSpec.from_strings([])
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        spec.category = "changed"


def test_ledger_spec_rejects_inconsistent_construction() -> None:
    with pytest.raises(ValueError, match=r"clauses|category|inconsistent"):
        LedgerEditSpec(clauses=(), category="software")


def test_invoice_spec_rejects_inconsistent_construction() -> None:
    with pytest.raises(ValueError, match=r"clauses|base|inconsistent"):
        InvoiceEditSpec(clauses=(), base=Decimal("100.00"))


def test_declaration_spec_rejects_inconsistent_construction() -> None:
    with pytest.raises(ValueError, match=r"clauses|casilla_edits|inconsistent"):
        DeclaracionEditSpec(clauses=(), casilla_edits={"71": Decimal("100.00")})


# ---------------------------------------------------------------------
# Enum sanity
# ---------------------------------------------------------------------


def test_ledger_edit_key_enum_carries_cli_values() -> None:
    assert {item.value for item in LedgerEditKey} == {
        "category",
        "treatment",
        "business.share",
        "reference",
        "comments",
        "document.path",
    }


def test_invoice_edit_key_enum_carries_cli_values() -> None:
    assert {item.value for item in InvoiceEditKey} == {
        "base",
        "iva.rate",
        "iva.amount",
        "iva.category",
        "retention.rate",
        "retention.amount",
        "payment.id",
        "reference",
        "comments",
        "document.path",
    }
