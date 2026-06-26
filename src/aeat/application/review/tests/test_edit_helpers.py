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


def test_coerce_decimal_returns_decimal_from_integer_string() -> None:
    assert _coerce_decimal(_clause("base", "120"), scope="invoice") == Decimal("120")


def test_coerce_decimal_returns_decimal_from_fractional_string() -> None:
    assert _coerce_decimal(_clause("base", "120.50"), scope="invoice") == Decimal("120.50")


def test_coerce_decimal_handles_negative_value() -> None:
    """The regex anchor permits a leading minus sign — negative
    decimals are valid for ledger amounts (e.g. refunds / credits)."""
    assert _coerce_decimal(_clause("base", "-42.5"), scope="invoice") == Decimal("-42.5")


def test_coerce_decimal_rejects_non_numeric_string() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-invoice") as exc_info:
        _coerce_decimal(_clause("base", "not-a-decimal"), scope="invoice")

    assert exc_info.value.reason == "invalid-value-invoice"


def test_coerce_decimal_rejects_scientific_notation() -> None:
    """The narrow regex excludes scientific notation — operator
    inputs should be plain decimals, not ``1e6``."""
    with pytest.raises(EditParseError, match=r"invalid-value-invoice") as exc_info:
        _coerce_decimal(_clause("base", "1e6"), scope="invoice")

    assert exc_info.value.reason == "invalid-value-invoice"


def test_coerce_decimal_scope_tag_composes_into_reason() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger") as exc_info:
        _coerce_decimal(_clause("base", "not-a-decimal"), scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


# ---------------------------------------------------------------------------
# _coerce_invoice_iva_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", ["0", "4", "10", "21"])
def test_coerce_invoice_iva_rate_accepts_canonical_substrate_slot(rate: str) -> None:
    assert _coerce_invoice_iva_rate(_clause("iva.rate", rate)) == Decimal(rate)


def test_coerce_invoice_iva_rate_rejects_non_canonical_value() -> None:
    """7% is not a known IVA substrate slot; the parser rejects it
    before it can reach an invoice record."""
    with pytest.raises(EditParseError, match=r"unsupported-iva-rate") as exc_info:
        _coerce_invoice_iva_rate(_clause("iva.rate", "7"))

    assert exc_info.value.reason == "unsupported-iva-rate"


def test_coerce_invoice_iva_rate_rejects_non_numeric_value() -> None:
    """A non-numeric value fails at the ``_coerce_decimal`` gate
    with the ``invalid-value-invoice-iva-rate`` scope tag."""
    with pytest.raises(EditParseError, match=r"invalid-value-invoice-iva-rate") as exc_info:
        _coerce_invoice_iva_rate(_clause("iva.rate", "abc"))

    assert exc_info.value.reason == "invalid-value-invoice-iva-rate"


# ---------------------------------------------------------------------------
# _coerce_invoice_retention_rate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rate", ["0", "15", "100"])
def test_coerce_invoice_retention_rate_accepts_bounds(rate: str) -> None:
    assert _coerce_invoice_retention_rate(_clause("retention.rate", rate)) == Decimal(rate)


def test_coerce_invoice_retention_rate_rejects_value_above_100() -> None:
    with pytest.raises(EditParseError, match=r"retention-rate-out-of-range") as exc_info:
        _coerce_invoice_retention_rate(_clause("retention.rate", "150"))

    assert exc_info.value.reason == "retention-rate-out-of-range"


def test_coerce_invoice_retention_rate_rejects_negative_value() -> None:
    with pytest.raises(EditParseError, match=r"retention-rate-out-of-range") as exc_info:
        _coerce_invoice_retention_rate(_clause("retention.rate", "-1"))

    assert exc_info.value.reason == "retention-rate-out-of-range"


def test_coerce_invoice_retention_rate_rejects_non_numeric_value() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-invoice-retention-rate") as exc_info:
        _coerce_invoice_retention_rate(_clause("retention.rate", "fifteen"))

    assert exc_info.value.reason == "invalid-value-invoice-retention-rate"


# ---------------------------------------------------------------------------
# _coerce_share
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("share", ["0", "0.5", "1", "1.0"])
def test_coerce_share_accepts_inclusive_zero_one_range(share: str) -> None:
    assert _coerce_share(_clause("business.share", share), scope="ledger") == Decimal(share)


def test_coerce_share_rejects_value_above_one() -> None:
    """1.5 violates the inclusive 0..1 envelope; the scope tag
    propagates into the reason code."""
    with pytest.raises(EditParseError, match=r"invalid-value-ledger") as exc_info:
        _coerce_share(_clause("business.share", "1.5"), scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


def test_coerce_share_rejects_negative_value() -> None:
    with pytest.raises(EditParseError, match=r"invalid-value-ledger") as exc_info:
        _coerce_share(_clause("business.share", "-0.1"), scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


def test_coerce_share_rejects_non_numeric_value() -> None:
    """Non-numeric strings fail at the ``_coerce_decimal`` gate
    with the same scope-tagged reason."""
    with pytest.raises(EditParseError, match=r"invalid-value-ledger") as exc_info:
        _coerce_share(_clause("business.share", "half"), scope="ledger")

    assert exc_info.value.reason == "invalid-value-ledger"


# ---------------------------------------------------------------------------
# _coerce_path
# ---------------------------------------------------------------------------


def test_coerce_path_returns_path_object() -> None:
    result = _coerce_path(_clause("document.path", "project/data/example.pdf"))

    assert result == Path("project/data/example.pdf")
    assert isinstance(result, Path)


def test_coerce_path_does_not_check_filesystem_existence() -> None:
    """The parser does not stat the path — that's the use-case's
    responsibility. A non-existent path round-trips through the
    coercer without raising."""
    result = _coerce_path(_clause("document.path", "/nonexistent/path/that/does/not/exist.pdf"))

    assert result == Path("/nonexistent/path/that/does/not/exist.pdf")


# ---------------------------------------------------------------------------
# _ensure_unique_keys (mirrors _filter.py sibling but raises EditParseError)
# ---------------------------------------------------------------------------


def test_ensure_unique_keys_passes_when_all_keys_distinct() -> None:
    clauses = (_clause("base", "120"), _clause("iva.rate", "21"))

    result = _ensure_unique_keys(clauses, scope="invoice")
    assert result is None


def test_ensure_unique_keys_raises_edit_parse_error_on_repeated_key() -> None:
    """The edit-spec helper raises :exc:`EditParseError`, not
    :exc:`FilterParseError` — the error type discriminates which
    CLI surface the failure came from."""
    clauses = (_clause("base", "120"), _clause("base", "200"))

    with pytest.raises(EditParseError, match=r"duplicate-key-invoice") as exc_info:
        _ensure_unique_keys(clauses, scope="invoice")

    assert exc_info.value.reason == "duplicate-key-invoice"


def test_ensure_unique_keys_scope_tag_composes_into_reason() -> None:
    clauses = (_clause("category", "software"), _clause("category", "office"))

    with pytest.raises(EditParseError, match=r"duplicate-key-ledger") as exc_info:
        _ensure_unique_keys(clauses, scope="ledger")

    assert exc_info.value.reason == "duplicate-key-ledger"


# ---------------------------------------------------------------------------
# _ensure_known_keys
# ---------------------------------------------------------------------------


def test_ensure_known_keys_passes_when_every_key_is_allowed() -> None:
    allowed = {"base", "iva.rate"}
    clauses = (_clause("base", "120"), _clause("iva.rate", "21"))

    result = _ensure_known_keys(clauses, scope="invoice", allowed=allowed)
    assert result is None


def test_ensure_known_keys_raises_edit_parse_error_on_unknown_key() -> None:
    allowed = {"base", "iva.rate"}
    clauses = (_clause("notakey", "value"),)

    with pytest.raises(EditParseError, match=r"unknown-key-invoice") as exc_info:
        _ensure_known_keys(clauses, scope="invoice", allowed=allowed)

    assert exc_info.value.reason == "unknown-key-invoice"


def test_ensure_known_keys_scope_tag_composes_into_reason() -> None:
    allowed = {"category"}
    clauses = (_clause("nonsense", "value"),)

    with pytest.raises(EditParseError, match=r"unknown-key-ledger") as exc_info:
        _ensure_known_keys(clauses, scope="ledger", allowed=allowed)

    assert exc_info.value.reason == "unknown-key-ledger"


def test_ensure_known_keys_raw_token_carries_offending_clause() -> None:
    allowed = {"base"}
    clauses = (_clause("nonsense", "value"),)

    with pytest.raises(EditParseError, match=r"edit|parse") as exc_info:
        _ensure_known_keys(clauses, scope="invoice", allowed=allowed)

    assert "nonsense=value" in exc_info.value.raw_token
