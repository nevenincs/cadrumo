"""Focused unit tests for review._edit value-coercion helpers.

Seven private helpers gate the per-scope ``--set`` edit specs:

- ``_coerce_decimal(clause, *, scope)`` — coerces a clause to
  :class:`Decimal`, rejecting non-numeric strings with reason
  ``invalid-value-{scope}``.
- ``_coerce_invoice_iva_rate(clause)`` — coerces ``iva.rate``
  values, rejecting non-canonical rates with reason
  ``unsupported-iva-rate``. The allowed set
  is ``{0, 4, 10, 21}`` per the IVA substrate slot taxonomy.
- ``_coerce_invoice_retention_rate(clause)`` — coerces
  ``retention.rate`` to a Decimal in the inclusive 0..100 range,
  rejecting out-of-range values with reason
  ``retention-rate-out-of-range``.
- ``_coerce_share(clause, *, scope)`` — coerces business-share
  Decimal in the inclusive 0..1 range.
- ``_coerce_path(clause)`` — coerces a clause value into
  :class:`pathlib.Path`. The empty-value branch is already
  rejected upstream by :func:`parse_edit_clause`.
- ``_ensure_unique_keys`` / ``_ensure_known_keys`` — mirror the
  ``_filter.py`` siblings but raise :exc:`EditParseError` (not
  :exc:`FilterParseError`).

Previously exercised only indirectly through the per-spec
:class:`LedgerEditSpec` / :class:`InvoiceEditSpec` integration tests.
A regression in the IVA-rate substrate gating (e.g. silently accepting
a free-form ``7`` rate) would silently corrupt every operator's invoice
edit audit trail without surfacing a typed error.

Tests pin each branch's typed-error reason; assertions are
predicate-contract / structural-error assertions, not calculation
tautologies.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._edit import (
    EditClause,
    _coerce_decimal,
    _coerce_invoice_iva_rate,
    _coerce_invoice_retention_rate,
    _coerce_path,
    _coerce_share,
    _ensure_known_keys,
    _ensure_unique_keys,
)
from .._errors import EditParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _clause(key: str, raw_value: str) -> EditClause:
    return EditClause(key=key, raw_value=raw_value)


# ---------------------------------------------------------------------------
# _coerce_decimal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    (
        ("120", Decimal("120")),
        ("120.50", Decimal("120.50")),
        ("-42.5", Decimal("-42.5")),
    ),
)
def test_coerce_decimal_accepts_plain_decimal_strings(raw_value: str, expected: Decimal) -> None:
    """The regex anchor permits a leading minus sign — negative
    decimals are valid for ledger amounts (e.g. refunds / credits)."""
    assert _coerce_decimal(_clause("base", raw_value), scope="invoice") == expected


@pytest.mark.parametrize(
    ("scope", "raw_value", "expected_reason"),
    (
        ("invoice", "not-a-decimal", "invalid-value-invoice"),
        ("invoice", "1e6", "invalid-value-invoice"),
        ("ledger", "not-a-decimal", "invalid-value-ledger"),
    ),
)
def test_coerce_decimal_rejects_non_plain_decimal_values(
    scope: str,
    raw_value: str,
    expected_reason: str,
) -> None:
    """The narrow regex excludes scientific notation — operator
    inputs should be plain decimals, not ``1e6``."""
    with pytest.raises(EditParseError, match=expected_reason) as exc_info:
        _coerce_decimal(_clause("base", raw_value), scope=scope)

    assert exc_info.value.reason == expected_reason


# ---------------------------------------------------------------------------
# _coerce_invoice_iva_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", ("0", "4", "10", "21"))
def test_coerce_invoice_iva_rate_accepts_canonical_substrate_slots(rate: str) -> None:
    assert _coerce_invoice_iva_rate(_clause("iva.rate", rate)) == Decimal(rate)


@pytest.mark.parametrize(
    ("raw_value", "expected_reason"),
    (
        ("7", "unsupported-iva-rate"),
        ("abc", "invalid-value-invoice-iva-rate"),
    ),
)
def test_coerce_invoice_iva_rate_rejects_non_canonical_or_non_numeric_values(
    raw_value: str,
    expected_reason: str,
) -> None:
    """7% is not a known IVA substrate slot; the parser rejects it
    before it can reach an invoice record."""
    with pytest.raises(EditParseError, match=expected_reason) as exc_info:
        _coerce_invoice_iva_rate(_clause("iva.rate", raw_value))

    assert exc_info.value.reason == expected_reason


# ---------------------------------------------------------------------------
# _coerce_invoice_retention_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", ("0", "15", "100"))
def test_coerce_invoice_retention_rate_accepts_bounds(rate: str) -> None:
    assert _coerce_invoice_retention_rate(_clause("retention.rate", rate)) == Decimal(rate)


@pytest.mark.parametrize(
    ("raw_value", "expected_reason"),
    (
        ("150", "retention-rate-out-of-range"),
        ("-1", "retention-rate-out-of-range"),
        ("fifteen", "invalid-value-invoice-retention-rate"),
    ),
)
def test_coerce_invoice_retention_rate_rejects_out_of_range_or_non_numeric_values(
    raw_value: str,
    expected_reason: str,
) -> None:
    with pytest.raises(EditParseError, match=expected_reason) as exc_info:
        _coerce_invoice_retention_rate(_clause("retention.rate", raw_value))

    assert exc_info.value.reason == expected_reason


# ---------------------------------------------------------------------------
# _coerce_share
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("share", ("0", "0.5", "1", "1.0"))
def test_coerce_share_accepts_inclusive_zero_one_range(share: str) -> None:
    assert _coerce_share(_clause("business.share", share), scope="ledger") == Decimal(share)


@pytest.mark.parametrize("raw_value", ("1.5", "-0.1", "half"))
def test_coerce_share_rejects_out_of_range_or_non_numeric_values(raw_value: str) -> None:
    """1.5 violates the inclusive 0..1 envelope; the scope tag
    propagates into the reason code."""
    with pytest.raises(EditParseError, match=r"invalid-value-ledger") as exc_info:
        _coerce_share(_clause("business.share", raw_value), scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


# ---------------------------------------------------------------------------
# _coerce_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw_path", ("project/data/example.pdf", "/nonexistent/path/that/does/not/exist.pdf"))
def test_coerce_path_returns_path_without_checking_filesystem_existence(raw_path: str) -> None:
    """The parser does not stat the path — that's the use-case's
    responsibility. A non-existent path round-trips through the
    coercer without raising."""
    result = _coerce_path(_clause("document.path", raw_path))

    assert result == Path(raw_path)
    assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# _ensure_unique_keys (mirrors _filter.py sibling but raises EditParseError)
# ---------------------------------------------------------------------------


def test_ensure_unique_keys_accepts_distinct_keys_and_rejects_scope_tagged_duplicates() -> None:
    clauses = (_clause("base", "120"), _clause("iva.rate", "21"))

    result = _ensure_unique_keys(clauses, scope="invoice")
    assert result is None

    # The edit-spec helper raises EditParseError, not FilterParseError;
    # the error type discriminates which CLI surface failed.
    with pytest.raises(EditParseError, match="duplicate-key-invoice") as exc_info:
        _ensure_unique_keys((_clause("base", "120"), _clause("base", "200")), scope="invoice")

    assert exc_info.value.reason == "duplicate-key-invoice"

    with pytest.raises(EditParseError, match="duplicate-key-ledger") as exc_info:
        _ensure_unique_keys((_clause("category", "software"), _clause("category", "office")), scope="ledger")

    assert exc_info.value.reason == "duplicate-key-ledger"


# ---------------------------------------------------------------------------
# _ensure_known_keys
# ---------------------------------------------------------------------------


def test_ensure_known_keys_accepts_allowed_keys_and_rejects_scope_tagged_unknowns() -> None:
    allowed = {"base", "iva.rate"}
    clauses = (_clause("base", "120"), _clause("iva.rate", "21"))

    result = _ensure_known_keys(clauses, scope="invoice", allowed=allowed)
    assert result is None

    with pytest.raises(EditParseError, match="unknown-key-invoice") as exc_info:
        _ensure_known_keys((_clause("notakey", "value"),), scope="invoice", allowed={"base", "iva.rate"})

    assert exc_info.value.reason == "unknown-key-invoice"
    assert "notakey=value" in exc_info.value.raw_token

    with pytest.raises(EditParseError, match="unknown-key-ledger") as exc_info:
        _ensure_known_keys((_clause("nonsense", "value"),), scope="ledger", allowed={"category"})

    assert exc_info.value.reason == "unknown-key-ledger"
    assert "nonsense=value" in exc_info.value.raw_token
