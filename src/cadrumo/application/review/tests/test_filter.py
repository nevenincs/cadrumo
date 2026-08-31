"""Unit tests for the typed ``--filter KEY=VALUE`` parser."""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ...transactions._diagnostics import LedgerImportDiagnosticKind
from ..filter import (
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


@pytest.mark.parametrize(
    ("raw", "expected_key", "expected_value"),
    (
        ("status=pending", "status", "pending"),
        ("  STATUS  =pending", "status", "pending"),
        ("status=  pending ", "status", "pending"),
    ),
)
def test_parse_filter_clause_normalizes_key_value_pairs(
    raw: str,
    expected_key: str,
    expected_value: str,
) -> None:
    clause = parse_filter_clause(raw)
    assert clause.key == expected_key
    assert clause.value == expected_value


@pytest.mark.parametrize(
    ("raw", "expected_reason"),
    (
        ("status pending", "missing-equals"),
        ("=pending", "empty-key"),
        ("status=", "empty-value"),
        ("status=   ", "empty-value"),
    ),
)
def test_parse_filter_clause_rejects_malformed_tokens(raw: str, expected_reason: str) -> None:
    with pytest.raises(FilterParseError) as exc:
        parse_filter_clause(raw)
    assert exc.value.reason == expected_reason
    if expected_reason == "missing-equals":
        assert exc.value.raw_token == raw
        assert exc.value.safe_token == _REDACTED
        assert exc.value.translated_message == "review.filter.errors.parse_failed"
        assert exc.value.context == {"reason": "missing-equals"}


def test_parse_filter_clauses_preserves_order() -> None:
    clauses = parse_filter_clauses(["status=pending", "period=1T"])
    assert [c.key for c in clauses] == ["status", "period"]


def test_filter_clause_is_frozen() -> None:
    from pydantic import ValidationError

    clause = FilterClause(key="status", value="pending")
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        clause.value = "changed"


# ---------------------------------------------------------------------
# LedgerReviewFilterSpec
# ---------------------------------------------------------------------


def test_ledger_spec_parses_supported_fields_together() -> None:
    spec = LedgerReviewFilterSpec.from_strings(
        [
            "status=pending",
            "period=1T",
            "year=2026",
            "issue=gap",
            "import=import_003",
            "direction=outgoing",
            "classification=business",
        ],
    )
    assert spec.status is LedgerReviewStatus.PENDING
    assert spec.period == Period.from_year_and_code(2026, "1T")
    assert spec.issue is LedgerImportDiagnosticKind.GAP
    assert spec.import_id == "import_003"
    assert spec.direction is TransactionDirection.OUTGOING
    assert spec.classification is BusinessClassification.BUSINESS
    assert [c.key for c in spec.clauses] == [
        "status",
        "period",
        "year",
        "issue",
        "import",
        "direction",
        "classification",
    ]


@pytest.mark.parametrize("clauses", (["period=1T"], ["year=2026"]))
def test_ledger_spec_requires_period_and_year_pairing(clauses: list[str]) -> None:
    """A bare ``period=`` token with no ``year=`` clause refuses (the pair travels together)."""
    with pytest.raises(FilterParseError):
        LedgerReviewFilterSpec.from_strings(clauses)


@pytest.mark.parametrize("period_code", ("Q1", "quarter-1", "1P", "not-a-period"))
def test_ledger_spec_rejects_non_filterable_period_values(period_code: str) -> None:
    with pytest.raises(FilterParseError) as exc:
        LedgerReviewFilterSpec.from_strings([f"period={period_code}", "year=2026"])

    assert exc.value.reason == "invalid-value-ledger-period"
    assert exc.value.safe_token == f"period={_REDACTED}"


@pytest.mark.parametrize(
    ("raw_issue", "expected_issue"),
    (
        ("gap", LedgerImportDiagnosticKind.GAP),
        ("duplicate", LedgerImportDiagnosticKind.DUPLICATE),
    ),
)
def test_ledger_spec_coerces_issue_values(raw_issue: str, expected_issue: LedgerImportDiagnosticKind) -> None:
    spec = LedgerReviewFilterSpec.from_strings([f"issue={raw_issue}"])
    assert spec.issue is expected_issue


@pytest.mark.parametrize(
    ("raw_direction", "expected_direction"),
    (
        ("outgoing", TransactionDirection.OUTGOING),
        ("internal_transfer", TransactionDirection.INTERNAL_TRANSFER),
        ("INCOMING", TransactionDirection.INCOMING),
        ("incoming", TransactionDirection.INCOMING),
    ),
)
def test_ledger_spec_coerces_direction_values(
    raw_direction: str,
    expected_direction: TransactionDirection,
) -> None:
    spec = LedgerReviewFilterSpec.from_strings([f"direction={raw_direction}"])
    assert spec.direction is expected_direction


@pytest.mark.parametrize("raw_classification", ("BUSINESS", "business"))
def test_ledger_spec_coerces_classification_values(raw_classification: str) -> None:
    spec = LedgerReviewFilterSpec.from_strings([f"classification={raw_classification}"])
    assert spec.classification is BusinessClassification.BUSINESS


def test_ledger_spec_empty_returns_empty_spec() -> None:
    spec = LedgerReviewFilterSpec.from_strings([])
    assert spec.status is None
    assert spec.period is None
    assert spec.issue is None
    assert spec.import_id is None
    assert spec.clauses == ()


@pytest.mark.parametrize(
    ("clauses", "expected_reason", "expected_safe_token", "expected_context"),
    (
        (["kind=received"], "unknown-key-ledger", None, None),
        (
            ["status=fictional"],
            "invalid-value-ledger-status",
            _STATUS_REDACTED,
            {"reason": "invalid-value-ledger-status", "key": "status"},
        ),
        (["issue=fictional"], "invalid-value-ledger-issue", None, None),
        (["direction=sideways"], "invalid-value-ledger-direction", None, None),
        (["status=pending", "status=skipped"], "duplicate-key-ledger", None, None),
    ),
)
def test_ledger_spec_rejects_invalid_keys_and_values(
    clauses: list[str],
    expected_reason: str,
    expected_safe_token: str | None,
    expected_context: dict[str, str] | None,
) -> None:
    with pytest.raises(FilterParseError) as exc:
        LedgerReviewFilterSpec.from_strings(clauses)
    assert exc.value.reason == expected_reason
    if expected_safe_token is not None:
        assert exc.value.safe_token == expected_safe_token
    if expected_context is not None:
        assert exc.value.context == expected_context


def test_ledger_filter_parse_error_message_omits_sensitive_filter_value() -> None:
    sensitive_value = "client-tax-id-12345678Z invoice notes"
    with pytest.raises(FilterParseError) as exc:
        LedgerReviewFilterSpec.from_strings([f"status={sensitive_value}"])

    assert exc.value.raw_token == f"--filter status={sensitive_value}"
    assert exc.value.safe_token == _STATUS_REDACTED
    assert sensitive_value not in str(exc.value)
    assert sensitive_value not in repr(exc.value.context)


# ---------------------------------------------------------------------
# InvoiceReviewFilterSpec
# ---------------------------------------------------------------------


def test_invoice_spec_parses_status_and_case_folded_kind() -> None:
    spec = InvoiceReviewFilterSpec.from_strings(["status=pending", "kind=received"])
    assert spec.status is InvoiceReviewStatus.PENDING
    assert spec.kind is InvoiceKind.RECEIVED

    # The CLI lowercases ``--filter kind=received``; InvoiceKind is uppercase.
    spec = InvoiceReviewFilterSpec.from_strings(["kind=ISSUED"])
    assert spec.kind is InvoiceKind.ISSUED
    spec = InvoiceReviewFilterSpec.from_strings(["kind=issued"])
    assert spec.kind is InvoiceKind.ISSUED


@pytest.mark.parametrize(
    ("clauses", "expected_reason"),
    (
        (["period=1T"], "unknown-key-invoice"),
        (["kind=draft"], "invalid-value-invoice-kind"),
        (["kind=issued", "kind=received"], "duplicate-key-invoice"),
    ),
)
def test_invoice_spec_rejects_invalid_keys_and_values(clauses: list[str], expected_reason: str) -> None:
    with pytest.raises(FilterParseError) as exc:
        InvoiceReviewFilterSpec.from_strings(clauses)
    assert exc.value.reason == expected_reason


# ---------------------------------------------------------------------
# DeclaracionReviewFilterSpec
# ---------------------------------------------------------------------


@pytest.mark.parametrize("status", tuple(DeclaracionReviewStatus))
def test_declaration_spec_parses_status_values(status: DeclaracionReviewStatus) -> None:
    spec = DeclaracionReviewFilterSpec.from_strings([f"status={status.value}"])
    assert spec.status is status


@pytest.mark.parametrize(
    ("clauses", "expected_reason"),
    (
        (["period=1T"], "unknown-key-declaration"),
        (["status=fictional"], "invalid-value-declaration-status"),
    ),
)
def test_declaration_spec_rejects_invalid_keys_and_values(clauses: list[str], expected_reason: str) -> None:
    with pytest.raises(FilterParseError) as exc:
        DeclaracionReviewFilterSpec.from_strings(clauses)
    assert exc.value.reason == expected_reason


# ---------------------------------------------------------------------
# Frozen / consistency invariants
# ---------------------------------------------------------------------


def test_ledger_spec_is_frozen() -> None:
    from pydantic import ValidationError

    spec = LedgerReviewFilterSpec.from_strings([])
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        spec.period = Period.from_year_and_code(2026, "1T")


def test_specs_reject_inconsistent_construction() -> None:
    """Direct construction with mismatched clauses / typed fields fails."""
    # Test LedgerReviewFilterSpec with inconsistent status
    with pytest.raises(ValueError, match=r"clauses|status|inconsistent"):
        LedgerReviewFilterSpec(clauses=(), status=LedgerReviewStatus.PENDING)

    # Test InvoiceReviewFilterSpec with inconsistent kind
    with pytest.raises(ValueError, match=r"clauses|kind|inconsistent"):
        InvoiceReviewFilterSpec(clauses=(), kind=InvoiceKind.ISSUED)

    # Test DeclaracionReviewFilterSpec with inconsistent status
    with pytest.raises(ValueError, match=r"clauses|status|inconsistent"):
        DeclaracionReviewFilterSpec(clauses=(), status=DeclaracionReviewStatus.PENDING)

    clauses = parse_filter_clauses(["period=2T", "year=2026"])

    with pytest.raises(ValueError, match=r"clauses\[period/year\] / period field disagree"):
        LedgerReviewFilterSpec(
            clauses=clauses,
            period=Period.from_year_and_code(2026, "1T"),
        )
