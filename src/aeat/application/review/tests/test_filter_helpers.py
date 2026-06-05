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


def test_ensure_unique_keys_passes_on_empty_tuple() -> None:
    """An empty clause tuple has no duplicates; the helper returns
    silently."""
    result = _ensure_unique_keys((), scope="ledger")
    assert result is None


def test_ensure_unique_keys_passes_when_all_keys_distinct() -> None:
    clauses = (_clause("status", "pending"), _clause("period", "2026-Q1"))

    result = _ensure_unique_keys(clauses, scope="ledger")
    assert result is None


def test_ensure_unique_keys_raises_on_repeated_key() -> None:
    clauses = (_clause("status", "pending"), _clause("status", "reviewed"))

    with pytest.raises(FilterParseError, match=r"duplicate-key-ledger") as exc_info:
        _ensure_unique_keys(clauses, scope="ledger")

    assert exc_info.value.reason == "duplicate-key-ledger"


def test_ensure_unique_keys_scope_tag_composes_into_reason() -> None:
    """The scope kwarg becomes the suffix of the reason code so the
    CLI can route the repair hint per-scope."""
    clauses = (_clause("status", "pending"), _clause("status", "reviewed"))

    with pytest.raises(FilterParseError, match=r"duplicate-key-invoice") as exc_info:
        _ensure_unique_keys(clauses, scope="invoice")

    assert exc_info.value.reason == "duplicate-key-invoice"


def test_ensure_unique_keys_raw_token_carries_offending_clause() -> None:
    clauses = (_clause("status", "pending"), _clause("status", "reviewed"))

    with pytest.raises(FilterParseError, match=r"filter|parse") as exc_info:
        _ensure_unique_keys(clauses, scope="ledger")

    assert "status=reviewed" in exc_info.value.raw_token


# ---------------------------------------------------------------------------
# _ensure_known_keys
# ---------------------------------------------------------------------------


def test_ensure_known_keys_passes_when_every_key_is_allowed() -> None:
    clauses = (_clause("status", "pending"), _clause("period", "2026-Q1"))

    result = _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)
    assert result is None


def test_ensure_known_keys_passes_on_empty_tuple() -> None:
    """An empty clause tuple has no unknown keys; the helper returns
    silently."""
    result = _ensure_known_keys((), scope="ledger", allowed=LedgerReviewFilterKey)
    assert result is None


def test_ensure_known_keys_raises_on_unknown_key() -> None:
    clauses = (_clause("status", "pending"), _clause("notakey", "value"))

    with pytest.raises(FilterParseError, match=r"unknown-key-ledger") as exc_info:
        _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)

    assert exc_info.value.reason == "unknown-key-ledger"


def test_ensure_known_keys_scope_tag_composes_into_reason() -> None:
    clauses = (_clause("notakey", "value"),)

    with pytest.raises(FilterParseError, match=r"unknown-key-invoice") as exc_info:
        _ensure_known_keys(clauses, scope="invoice", allowed=InvoiceReviewFilterKey)

    assert exc_info.value.reason == "unknown-key-invoice"


def test_ensure_known_keys_per_scope_catalogues_differ() -> None:
    """``import`` is a valid ledger key but unknown for the invoice
    scope; the per-scope catalogue gating must reject it."""
    clauses = (_clause("import", "import_003"),)

    _ensure_known_keys(clauses, scope="ledger", allowed=LedgerReviewFilterKey)

    with pytest.raises(FilterParseError, match=r"unknown-key-invoice") as exc_info:
        _ensure_known_keys(clauses, scope="invoice", allowed=InvoiceReviewFilterKey)

    assert exc_info.value.reason == "unknown-key-invoice"


# ---------------------------------------------------------------------------
# _enum_value_or_raise
# ---------------------------------------------------------------------------


def test_enum_value_or_raise_coerces_valid_value_to_enum_member() -> None:
    clause = _clause("status", "pending")

    result = _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert result is LedgerReviewStatus.PENDING


def test_enum_value_or_raise_raises_on_unknown_value() -> None:
    clause = _clause("status", "not-a-real-status")

    with pytest.raises(FilterParseError, match=r"invalid-value-ledger") as exc_info:
        _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


def test_enum_value_or_raise_scope_tag_composes_into_reason() -> None:
    clause = _clause("status", "not-a-real-status")

    with pytest.raises(FilterParseError, match=r"invalid-value-invoice") as exc_info:
        _enum_value_or_raise(clause, LedgerReviewStatus, scope="invoice")

    assert exc_info.value.reason == "invalid-value-invoice"


def test_enum_value_or_raise_case_fold_true_uppercases_input_before_lookup() -> None:
    """:class:`InvoiceKind` members are uppercase (``ISSUED``,
    ``RECEIVED``); the CLI passes lowercase tokens. ``case_fold=True``
    uppercases the input so the lookup matches."""
    clause = _clause("kind", "issued")

    result = _enum_value_or_raise(clause, InvoiceKind, scope="invoice", case_fold=True)

    assert result is InvoiceKind.ISSUED


def test_enum_value_or_raise_case_fold_false_rejects_uppercase_for_lowercase_enum() -> None:
    """Without ``case_fold=True`` the uppercased input does not match
    a lowercase-valued enum like :class:`LedgerReviewStatus`."""
    clause = _clause("status", "PENDING")

    with pytest.raises(FilterParseError, match=r"invalid-value-ledger") as exc_info:
        _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


def test_enum_value_or_raise_case_fold_true_rejects_unknown_uppercase_value() -> None:
    """``case_fold=True`` uppercases the input but still rejects
    values outside the enum catalogue."""
    clause = _clause("kind", "not-a-real-kind")

    with pytest.raises(FilterParseError, match=r"invalid-value-invoice") as exc_info:
        _enum_value_or_raise(clause, InvoiceKind, scope="invoice", case_fold=True)

    assert exc_info.value.reason == "invalid-value-invoice"


def test_enum_value_or_raise_raw_token_carries_offending_clause() -> None:
    clause = _clause("status", "not-a-status")

    with pytest.raises(FilterParseError, match=r"filter|parse") as exc_info:
        _enum_value_or_raise(clause, LedgerReviewStatus, scope="ledger")

    assert "status=not-a-status" in exc_info.value.raw_token
