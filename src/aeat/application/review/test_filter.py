"""Unit tests for the typed ``--filter KEY=VALUE`` parser."""

from __future__ import annotations

import pytest

from ...domain.invoices import InvoiceKind
from ._filter import (
    DeclaracionReviewFilterSpec,
    DeclaracionReviewStatus,
    FilterClause,
    FilterParseError,
    InvoiceReviewFilterSpec,
    InvoiceReviewStatus,
    LedgerReviewFilterSpec,
    LedgerReviewIssue,
    LedgerReviewStatus,
    parse_filter_clause,
    parse_filter_clauses,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------
# Parser substrate
# ---------------------------------------------------------------------


def test_parse_filter_clause_round_trips_canonical_pair() -> None:
    clause = parse_filter_clause("status=pending")
    assert clause.key == "status"
    assert clause.value == "pending"


def test_parse_filter_clause_lowercases_and_trims_key() -> None:
    clause = parse_filter_clause("  STATUS  =pending")
    assert clause.key == "status"


def test_parse_filter_clause_trims_value() -> None:
    clause = parse_filter_clause("status=  pending ")
    assert clause.value == "pending"


def test_parse_filter_clause_rejects_missing_equals() -> None:
    raw = "status pending"
    with pytest.raises(FilterParseError, match=r"missing-equals") as exc:
        parse_filter_clause(raw)
    assert exc.value.reason == "missing-equals"
    assert exc.value.raw_token == raw


def test_parse_filter_clause_rejects_empty_key() -> None:
    with pytest.raises(FilterParseError, match=r"empty-key") as exc:
        parse_filter_clause("=pending")
    assert exc.value.reason == "empty-key"


def test_parse_filter_clause_rejects_empty_value() -> None:
    with pytest.raises(FilterParseError, match=r"empty-value") as exc:
        parse_filter_clause("status=")
    assert exc.value.reason == "empty-value"


def test_parse_filter_clause_rejects_blank_value() -> None:
    with pytest.raises(FilterParseError, match=r"empty-value|blank"):
        parse_filter_clause("status=   ")


def test_parse_filter_clauses_preserves_order() -> None:
    clauses = parse_filter_clauses(["status=pending", "period=2026-Q1"])
    assert [c.key for c in clauses] == ["status", "period"]


def test_filter_clause_is_frozen() -> None:
    from pydantic import ValidationError

    clause = FilterClause(key="status", value="pending")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        clause.value = "changed"


# ---------------------------------------------------------------------
# LedgerReviewFilterSpec
# ---------------------------------------------------------------------


def test_ledger_spec_parses_status_and_period() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["status=pending", "period=2026-Q1"])
    assert spec.status is LedgerReviewStatus.PENDING
    assert spec.period == "2026-Q1"
    assert spec.issue is None
    assert spec.import_id is None
    assert [c.key for c in spec.clauses] == ["status", "period"]


def test_ledger_spec_parses_issue_filter() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["issue=gap", "period=2026-Q1"])
    assert spec.issue is LedgerReviewIssue.GAP


def test_ledger_spec_parses_duplicate_issue() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["issue=duplicate"])
    assert spec.issue is LedgerReviewIssue.DUPLICATE


def test_ledger_spec_parses_import_id() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["import=import_003"])
    assert spec.import_id == "import_003"


def test_ledger_spec_empty_returns_empty_spec() -> None:
    spec = LedgerReviewFilterSpec.from_strings([])
    assert spec.status is None
    assert spec.period is None
    assert spec.issue is None
    assert spec.import_id is None
    assert spec.clauses == ()


def test_ledger_spec_rejects_unknown_key() -> None:
    with pytest.raises(FilterParseError, match=r"unknown-key-ledger") as exc:
        LedgerReviewFilterSpec.from_strings(["kind=received"])
    assert exc.value.reason == "unknown-key-ledger"


def test_ledger_spec_rejects_invalid_status() -> None:
    with pytest.raises(FilterParseError, match=r"invalid-value-ledger-status") as exc:
        LedgerReviewFilterSpec.from_strings(["status=fictional"])
    assert exc.value.reason == "invalid-value-ledger-status"


def test_ledger_spec_rejects_invalid_issue() -> None:
    with pytest.raises(FilterParseError, match=r"invalid-value-ledger-issue") as exc:
        LedgerReviewFilterSpec.from_strings(["issue=fictional"])
    assert exc.value.reason == "invalid-value-ledger-issue"


def test_ledger_spec_rejects_duplicate_key() -> None:
    with pytest.raises(FilterParseError, match=r"duplicate-key-ledger") as exc:
        LedgerReviewFilterSpec.from_strings(["status=pending", "status=skipped"])
    assert exc.value.reason == "duplicate-key-ledger"


# ---------------------------------------------------------------------
# InvoiceReviewFilterSpec
# ---------------------------------------------------------------------


def test_invoice_spec_parses_status_and_kind() -> None:
    spec = InvoiceReviewFilterSpec.from_strings(["status=pending", "kind=received"])
    assert spec.status is InvoiceReviewStatus.PENDING
    assert spec.kind is InvoiceKind.RECEIVED


def test_invoice_spec_case_folds_kind() -> None:
    """The CLI lowercases ``--filter kind=received``; InvoiceKind is uppercase."""
    spec = InvoiceReviewFilterSpec.from_strings(["kind=ISSUED"])
    assert spec.kind is InvoiceKind.ISSUED
    spec = InvoiceReviewFilterSpec.from_strings(["kind=issued"])
    assert spec.kind is InvoiceKind.ISSUED


def test_invoice_spec_rejects_unknown_key() -> None:
    with pytest.raises(FilterParseError, match=r"unknown-key-invoice") as exc:
        InvoiceReviewFilterSpec.from_strings(["period=2026-Q1"])
    assert exc.value.reason == "unknown-key-invoice"


def test_invoice_spec_rejects_invalid_kind() -> None:
    with pytest.raises(FilterParseError, match=r"invalid-value-invoice-kind") as exc:
        InvoiceReviewFilterSpec.from_strings(["kind=draft"])
    assert exc.value.reason == "invalid-value-invoice-kind"


def test_invoice_spec_rejects_duplicate_key() -> None:
    with pytest.raises(FilterParseError, match=r"duplicate-key-invoice") as exc:
        InvoiceReviewFilterSpec.from_strings(["kind=issued", "kind=received"])
    assert exc.value.reason == "duplicate-key-invoice"


# ---------------------------------------------------------------------
# DeclaracionReviewFilterSpec
# ---------------------------------------------------------------------


def test_declaration_spec_parses_status() -> None:
    spec = DeclaracionReviewFilterSpec.from_strings(["status=pending"])
    assert spec.status is DeclaracionReviewStatus.PENDING


def test_declaration_spec_supports_every_status_value() -> None:
    for status in DeclaracionReviewStatus:
        spec = DeclaracionReviewFilterSpec.from_strings([f"status={status.value}"])
        assert spec.status is status


def test_declaration_spec_rejects_unknown_key() -> None:
    with pytest.raises(FilterParseError, match=r"unknown-key-declaration") as exc:
        DeclaracionReviewFilterSpec.from_strings(["period=2026-Q1"])
    assert exc.value.reason == "unknown-key-declaration"


def test_declaration_spec_rejects_invalid_status() -> None:
    with pytest.raises(FilterParseError, match=r"invalid-value-declaration-status") as exc:
        DeclaracionReviewFilterSpec.from_strings(["status=fictional"])
    assert exc.value.reason == "invalid-value-declaration-status"


# ---------------------------------------------------------------------
# Frozen / consistency invariants
# ---------------------------------------------------------------------


def test_ledger_spec_is_frozen() -> None:
    from pydantic import ValidationError

    spec = LedgerReviewFilterSpec.from_strings([])
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        spec.period = "2026-Q1"


def test_ledger_spec_rejects_inconsistent_construction() -> None:
    """Direct construction with mismatched clauses / typed fields fails."""
    with pytest.raises(ValueError, match=r"clauses|status|inconsistent"):
        LedgerReviewFilterSpec(clauses=(), status=LedgerReviewStatus.PENDING)


def test_invoice_spec_rejects_inconsistent_construction() -> None:
    with pytest.raises(ValueError, match=r"clauses|kind|inconsistent"):
        InvoiceReviewFilterSpec(clauses=(), kind=InvoiceKind.ISSUED)


def test_declaration_spec_rejects_inconsistent_construction() -> None:
    with pytest.raises(ValueError, match=r"clauses|status|inconsistent"):
        DeclaracionReviewFilterSpec(clauses=(), status=DeclaracionReviewStatus.PENDING)
