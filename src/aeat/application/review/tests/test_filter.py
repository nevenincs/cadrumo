"""Unit tests for the typed ``--filter KEY=VALUE`` parser."""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from ....domain.iva import InvoiceKind
from ....domain.transactions import BusinessClassification, TransactionDirection
from ...transactions import LedgerImportDiagnosticKind
from .._filter import (
    DeclaracionReviewFilterSpec,
    DeclaracionReviewStatus,
    FilterClause,
    FilterParseError,
    InvoiceReviewFilterSpec,
    InvoiceReviewStatus,
    LedgerReviewFilterSpec,
    LedgerReviewStatus,
    parse_filter_clause,
    parse_filter_clauses,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REDACTED = "<redacted>"
_STATUS_REDACTED = f"status={_REDACTED}"


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
    assert exc.value.safe_token == _REDACTED
    assert exc.value.translated_message == "review.filter.errors.parse_failed"
    assert exc.value.context == {"reason": "missing-equals"}


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
    spec = LedgerReviewFilterSpec.from_strings(["status=pending", "period=1T", "year=2026"])
    assert spec.status is LedgerReviewStatus.PENDING
    assert spec.period == "1T"
    assert spec.year == 2026
    assert spec.issue is None
    assert spec.import_id is None
    assert [c.key for c in spec.clauses] == ["status", "period", "year"]


def test_ledger_spec_requires_year_with_period() -> None:
    """A bare ``period=`` token with no ``year=`` clause refuses (the pair travels together)."""
    with pytest.raises(FilterParseError, match=r"period-year-pairing"):
        LedgerReviewFilterSpec.from_strings(["period=1T"])


def test_ledger_spec_requires_period_with_year() -> None:
    """A ``year=`` clause with no ``period=`` token refuses (the pair travels together)."""
    with pytest.raises(FilterParseError, match=r"period-year-pairing"):
        LedgerReviewFilterSpec.from_strings(["year=2026"])


def test_ledger_spec_parses_issue_filter() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["issue=gap", "period=1T", "year=2026"])
    assert spec.issue is LedgerImportDiagnosticKind.GAP


def test_ledger_spec_parses_duplicate_issue() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["issue=duplicate"])
    assert spec.issue is LedgerImportDiagnosticKind.DUPLICATE


def test_ledger_spec_parses_import_id() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["import=import_003"])
    assert spec.import_id == "import_003"


def test_ledger_spec_parses_direction_lowercase() -> None:
    """direction=outgoing resolves to the TransactionDirection.OUTGOING enum member."""
    spec = LedgerReviewFilterSpec.from_strings(["direction=outgoing"])
    assert spec.direction is TransactionDirection.OUTGOING
    assert [c.key for c in spec.clauses] == ["direction"]


def test_ledger_spec_parses_direction_internal_transfer() -> None:
    spec = LedgerReviewFilterSpec.from_strings(["direction=internal_transfer"])
    assert spec.direction is TransactionDirection.INTERNAL_TRANSFER


def test_ledger_spec_direction_is_case_insensitive() -> None:
    """An operator may type the enum case (INCOMING) or natural lowercase."""
    upper = LedgerReviewFilterSpec.from_strings(["direction=INCOMING"])
    lower = LedgerReviewFilterSpec.from_strings(["direction=incoming"])
    assert upper.direction is lower.direction is TransactionDirection.INCOMING


def test_ledger_spec_unknown_direction_value_raises() -> None:
    with pytest.raises(FilterParseError):
        LedgerReviewFilterSpec.from_strings(["direction=sideways"])


def test_ledger_spec_classification_is_case_insensitive() -> None:
    """classification=business now resolves the same as classification=BUSINESS.

    The lowercase-classification refinement: BusinessClassification members are
    UPPERCASE, but an operator naturally types lowercase; both must resolve.
    """
    upper = LedgerReviewFilterSpec.from_strings(["classification=BUSINESS"])
    lower = LedgerReviewFilterSpec.from_strings(["classification=business"])
    assert upper.classification is lower.classification is BusinessClassification.BUSINESS


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
    assert exc.value.safe_token == _STATUS_REDACTED
    assert exc.value.context == {"reason": "invalid-value-ledger-status", "key": "status"}


def test_ledger_spec_rejects_invalid_issue() -> None:
    with pytest.raises(FilterParseError, match=r"invalid-value-ledger-issue") as exc:
        LedgerReviewFilterSpec.from_strings(["issue=fictional"])
    assert exc.value.reason == "invalid-value-ledger-issue"


def test_ledger_spec_rejects_duplicate_key() -> None:
    with pytest.raises(FilterParseError, match=r"duplicate-key-ledger") as exc:
        LedgerReviewFilterSpec.from_strings(["status=pending", "status=skipped"])
    assert exc.value.reason == "duplicate-key-ledger"


def test_ledger_filter_parse_error_message_omits_sensitive_filter_value() -> None:
    sensitive_value = "client-tax-id-12345678Z invoice notes"
    with pytest.raises(FilterParseError) as exc:
        LedgerReviewFilterSpec.from_strings([f"status={sensitive_value}"])

    assert exc.value.raw_token == f"--filter status={sensitive_value}"
    assert exc.value.safe_token == _STATUS_REDACTED
    assert sensitive_value not in str(exc.value)
    assert sensitive_value not in repr(exc.value.context)


def test_ledger_filter_cli_error_uses_redacted_token() -> None:
    sensitive_value = "client-tax-id-12345678Z invoice notes"
    with pytest.raises(FilterParseError) as exc:
        LedgerReviewFilterSpec.from_strings([f"status={sensitive_value}"])

    rendered = tr("cli.ledger.errors.filter_parse_error", reason=exc.value.reason, token=exc.value.safe_token)

    assert _STATUS_REDACTED in rendered
    assert sensitive_value not in rendered


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
