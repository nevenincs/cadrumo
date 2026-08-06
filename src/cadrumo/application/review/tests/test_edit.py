"""Unit tests for the typed ``--set KEY=VALUE`` parser."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._edit import (
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


@pytest.mark.parametrize(
    ("raw", "expected_key", "expected_value"),
    (
        ("category=software", "category", "software"),
        ("  CATEGORY  =software", "category", "software"),
        ("category=  software ", "category", "software"),
    ),
)
def test_parse_edit_clause_normalizes_key_value_pairs(
    raw: str,
    expected_key: str,
    expected_value: str,
) -> None:
    clause = parse_edit_clause(raw)
    assert clause.key == expected_key
    assert clause.raw_value == expected_value


@pytest.mark.parametrize(
    ("raw", "expected_reason"),
    (
        ("category software", "missing-equals"),
        ("=software", "empty-key"),
        ("category=", "empty-value"),
        ("category=   ", "empty-value"),
    ),
)
def test_parse_edit_clause_rejects_malformed_tokens(raw: str, expected_reason: str) -> None:
    with pytest.raises(EditParseError, match=expected_reason) as exc:
        parse_edit_clause(raw)
    assert exc.value.reason == expected_reason
    if expected_reason == "missing-equals":
        assert exc.value.raw_token == raw
        assert exc.value.translated_message == "review.edit.errors.parse_failed"
        assert exc.value.context == {"reason": "missing-equals"}


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


def test_ledger_spec_parses_supported_fields_together() -> None:
    """Parse ledger edits together."""
    spec = LedgerEditSpec.from_strings(
        [
            "category=software",
            "business.share=1.0",
            "reference=invoice-1",
            "document.path=./receipts/receipt-901.pdf",
            "comments=invoice-reviewed",
        ],
    )
    assert spec.category == "software"
    assert spec.business_share == Decimal("1.0")
    assert spec.reference == "invoice-1"
    assert spec.document_path == Path("./receipts/receipt-901.pdf")
    assert spec.comments == "invoice-reviewed"


@pytest.mark.parametrize(("raw_value", "expected"), (("0", Decimal("0")), ("1", Decimal("1"))))
def test_ledger_spec_business_share_accepts_decimal_boundaries(raw_value: str, expected: Decimal) -> None:
    spec = LedgerEditSpec.from_strings([f"business.share={raw_value}"])
    assert spec.business_share == expected


@pytest.mark.parametrize("raw_value", ("1.5", "-0.1", "full"))
def test_ledger_spec_business_share_rejects_invalid_values(raw_value: str) -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger-business-share") as exc:
        LedgerEditSpec.from_strings([f"business.share={raw_value}"])
    assert exc.value.reason == "invalid-value-ledger-business-share"


@pytest.mark.parametrize(
    ("clauses", "expected_reason", "expected_context"),
    (
        (["base=120.00"], "unknown-key-ledger", None),
        (["category=a", "category=b"], "duplicate-key-ledger", {"reason": "duplicate-key-ledger", "key": "category"}),
    ),
)
def test_ledger_spec_rejects_invalid_keys(
    clauses: list[str],
    expected_reason: str,
    expected_context: dict[str, str] | None,
) -> None:
    with pytest.raises(EditParseError, match=expected_reason) as exc:
        LedgerEditSpec.from_strings(clauses)
    assert exc.value.reason == expected_reason
    if expected_context is not None:
        assert exc.value.context == expected_context


def test_ledger_spec_parse_error_message_omits_sensitive_edit_value() -> None:
    sensitive_path = "C:/Users/example/Documents/client-tax-id-12345678Z.pdf"
    with pytest.raises(EditParseError) as exc:
        LedgerEditSpec.from_strings([f"business.share={sensitive_path}"])

    assert exc.value.reason == "invalid-value-ledger-business-share"
    assert exc.value.raw_token == f"--set business.share={sensitive_path}"
    assert exc.value.context == {"reason": "invalid-value-ledger-business-share", "key": "business.share"}
    assert sensitive_path not in str(exc.value)
    assert sensitive_path not in repr(exc.value.context)


# ---------------------------------------------------------------------
# InvoiceEditSpec
# ---------------------------------------------------------------------


def test_invoice_spec_parses_supported_fields_together() -> None:
    """Parse invoice edits together."""
    spec = InvoiceEditSpec.from_strings(
        [
            "base=120.00",
            "iva.rate=21",
            "iva.amount=25.20",
            "iva.category=intracomunitario",
            "retention.rate=15",
            "retention.amount=18.00",
            "payment.id=row_1_1",
            "reference=invoice-1",
            "comments=invoice-reviewed",
            "document.path=./receipts/receipt-901.pdf",
        ],
    )
    assert spec.base == Decimal("120.00")
    assert spec.iva_rate == Decimal("21")
    assert spec.iva_amount == Decimal("25.20")
    assert spec.iva_category == "intracomunitario"
    assert spec.retention_rate == Decimal("15")
    assert spec.retention_amount == Decimal("18.00")
    assert spec.payment_id == "row_1_1"
    assert spec.reference == "invoice-1"
    assert spec.comments == "invoice-reviewed"
    assert spec.document_path == Path("./receipts/receipt-901.pdf")


@pytest.mark.parametrize(
    ("clauses", "expected_reason"),
    (
        (["category=software"], "unknown-key-invoice"),
        (["base=tbd"], "invalid-value-invoice-base"),
        (["base=1.0", "base=2.0"], "duplicate-key-invoice"),
    ),
)
def test_invoice_spec_rejects_invalid_keys_and_values(clauses: list[str], expected_reason: str) -> None:
    with pytest.raises(EditParseError, match=expected_reason) as exc:
        InvoiceEditSpec.from_strings(clauses)
    assert exc.value.reason == expected_reason


@pytest.mark.parametrize("raw_value", ("1.234", "1.000"))
def test_invoice_base_rejects_values_that_bare_decimal_would_misread(raw_value: str) -> None:
    """Review editing cannot bypass the creation wizard's euro-cent precision boundary."""
    assert isinstance(Decimal(raw_value.replace(",", ".")), Decimal)

    with pytest.raises(EditParseError, match="invalid-value-invoice-base") as exc:
        InvoiceEditSpec.from_strings([f"base={raw_value}"])

    assert exc.value.reason == "invalid-value-invoice-base"


def test_invoice_base_rejects_european_thousands_text() -> None:
    with pytest.raises(EditParseError, match="invalid-value-invoice-base"):
        InvoiceEditSpec.from_strings(["base=1.234,56"])


def test_empty_specs_return_empty_instances() -> None:
    ledger_spec = LedgerEditSpec.from_strings([])
    assert ledger_spec.clauses == ()
    assert ledger_spec.category is None
    assert ledger_spec.business_share is None

    invoice_spec = InvoiceEditSpec.from_strings([])
    assert invoice_spec.clauses == ()
    assert all(
        getattr(invoice_spec, name) is None
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
# Frozen / consistency invariants
# ---------------------------------------------------------------------


def test_ledger_spec_is_frozen() -> None:
    from pydantic import ValidationError

    spec = LedgerEditSpec.from_strings([])
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        spec.category = "changed"


def test_specs_reject_inconsistent_construction() -> None:
    # Test LedgerEditSpec rejects empty clauses with non-empty category
    with pytest.raises(ValueError, match=r"clauses|category|inconsistent"):
        LedgerEditSpec(clauses=(), category="software")

    # Test InvoiceEditSpec rejects empty clauses with non-empty base
    with pytest.raises(ValueError, match=r"clauses|base|inconsistent"):
        InvoiceEditSpec(clauses=(), base=Decimal("100.00"))


# ---------------------------------------------------------------------
# Enum sanity
# ---------------------------------------------------------------------


def test_edit_key_enums_carry_cli_values() -> None:
    assert {item.value for item in LedgerEditKey} == {
        "category",
        "treatment",
        "business.share",
        "reference",
        "comments",
        "document.path",
    }

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
