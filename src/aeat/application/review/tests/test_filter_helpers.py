"""Focused unit tests for review._filter private validation helpers.

Three private helpers gate the per-scope ``--filter`` specs:

- ``_ensure_unique_keys(clauses, *, scope)`` — rejects duplicate
  keys, surfacing ``duplicate-key-{scope}`` errors.
- ``_ensure_known_keys(clauses, *, scope, allowed)`` — rejects keys
  outside the per-scope :class:`StrEnum` catalogue, surfacing
  ``unknown-key-{scope}`` errors.
- ``_enum_value_or_raise(clause, enum_cls, *, scope, case_fold)`` —
  coerces a clause value into the matching :class:`StrEnum`
  member, with optional uppercase folding for case-mismatched
  upstream enums (e.g. :class:`InvoiceKind`).

Previously exercised only indirectly through the per-spec
:class:`LedgerReviewFilterSpec` / :class:`InvoiceReviewFilterSpec`
/ :class:`DeclaracionReviewFilterSpec` integration tests. A
regression in the scope-tag composition (e.g. dropping the
``duplicate-key-`` prefix) would silently render the CLI repair
hints ambiguous across scopes; the integration tests do not pin
the ``error.reason`` shape at this level of granularity.

Tests pin each branch's typed-error reason; assertions are
predicate-contract / structural assertions, not calculation
tautologies.
"""

from __future__ import annotations

import pytest

from ....domain.iva import InvoiceKind
from .._errors import FilterParseError
from .._filter import (
    FilterClause,
    InvoiceReviewFilterKey,
    LedgerReviewFilterKey,
    LedgerReviewStatus,
    _ensure_known_keys,
    _ensure_unique_keys,
    _enum_value_or_raise,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _clause(key: str, value: str) -> FilterClause:
    return FilterClause(key=key, value=value)


# ---------------------------------------------------------------------------
# _ensure_unique_keys
# ---------------------------------------------------------------------------


def test_ensure_unique_keys_accepts_empty_and_distinct_key_sets() -> None:
    """An empty clause tuple has no duplicates; the helper returns
    silently."""
    cases = (
        (),
        (_clause("status", "pending"), _clause("period", "2026-Q1")),
    )
    for clauses in cases:
        result = _ensure_unique_keys(clauses, scope="ledger")
        assert result is None


def test_ensure_unique_keys_rejects_scope_tagged_duplicates() -> None:
    """The scope kwarg becomes the suffix of the reason code so the
    CLI can route the repair hint per-scope."""
    clauses = (_clause("status", "pending"), _clause("status", "reviewed"))
    for scope, expected_reason in (("ledger", "duplicate-key-ledger"), ("invoice", "duplicate-key-invoice")):
        with pytest.raises(FilterParseError, match=expected_reason) as exc_info:
            _ensure_unique_keys(clauses, scope=scope)

        assert exc_info.value.reason == expected_reason
        assert "status=reviewed" in exc_info.value.raw_token


# ---------------------------------------------------------------------------
# _ensure_known_keys
# ---------------------------------------------------------------------------


def test_ensure_known_keys_accepts_empty_and_allowed_key_sets() -> None:
    """An empty clause tuple has no unknown keys; the helper returns
    silently."""
    cases = (
        (),
        (_clause("status", "pending"), _clause("period", "2026-Q1")),
    )
    for clauses in cases:
        result = _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)
        assert result is None


def test_ensure_known_keys_rejects_scope_tagged_unknowns_and_per_scope_catalogues() -> None:
    """``import`` is a valid ledger key but unknown for the invoice
    scope; the per-scope catalogue gating must reject it."""
    unknown_cases = (
        ("ledger", LedgerReviewFilterKey, (_clause("notakey", "value"),), "unknown-key-ledger"),
        ("invoice", InvoiceReviewFilterKey, (_clause("notakey", "value"),), "unknown-key-invoice"),
    )
    for scope, allowed, clauses, expected_reason in unknown_cases:
        with pytest.raises(FilterParseError, match=expected_reason) as exc_info:
            _ensure_known_keys(clauses, scope=scope, allowed=allowed)

        assert exc_info.value.reason == expected_reason

    clauses = (_clause("import", "import_003"),)
    _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)

    with pytest.raises(FilterParseError, match=r"unknown-key-invoice") as exc_info:
        _ensure_known_keys(clauses, scope="invoice", allowed=InvoiceReviewFilterKey)

    assert exc_info.value.reason == "unknown-key-invoice"


# ---------------------------------------------------------------------------
# _enum_value_or_raise
# ---------------------------------------------------------------------------


def test_enum_value_or_raise_coerces_valid_and_case_folded_values() -> None:
    clause = _clause("status", "pending")

    result = _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert result is LedgerReviewStatus.PENDING

    # InvoiceKind members are uppercase; the CLI passes lowercase tokens.
    # ``case_fold=True`` uppercases the input so the lookup matches.
    clause = _clause("kind", "issued")

    result = _enum_value_or_raise(clause, InvoiceKind, scope="invoice", case_fold=True)

    assert result is InvoiceKind.ISSUED


def test_enum_value_or_raise_rejects_unknown_values_with_scope_tagged_reasons() -> None:
    cases = (
        ("ledger", _clause("status", "not-a-real-status"), LedgerReviewStatus, False, "invalid-value-ledger"),
        ("invoice", _clause("status", "not-a-real-status"), LedgerReviewStatus, False, "invalid-value-invoice"),
        ("invoice", _clause("kind", "not-a-real-kind"), InvoiceKind, True, "invalid-value-invoice"),
    )
    for scope, clause, enum_cls, case_fold, expected_reason in cases:
        with pytest.raises(FilterParseError, match=expected_reason) as exc_info:
            _enum_value_or_raise(clause, enum_cls, scope=scope, case_fold=case_fold)

        assert exc_info.value.reason == expected_reason
        assert f"{clause.key}={clause.value}" in exc_info.value.raw_token


def test_enum_value_or_raise_case_fold_false_rejects_uppercase_for_lowercase_enum() -> None:
    """Without ``case_fold=True`` the uppercased input does not match
    a lowercase-valued enum like :class:`LedgerReviewStatus`."""
    clause = _clause("status", "PENDING")

    with pytest.raises(FilterParseError, match=r"invalid-value-ledger") as exc_info:
        _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"
