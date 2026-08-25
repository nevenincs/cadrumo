"""Deletion regression guard for :func:`aggregation_period_for_modelo`.

The translator accepts ONLY the canonical span-shaped :class:`StandardPeriodCode`
tokens (``1T``-``4T``, ``0A``, ``01``-``12``) the
calc engine and the CLI ledger filter share. The deleted calendar-shape aliases
(``Q1``-``Q4``, ``A``, ``ANUAL``, ``ANNUAL``, ``M01``-``M12``) must now raise.
Each canonical token must map to the typed :class:`Period` consumed by ledger
filters — proving the translator and the shared :meth:`Period.contains`
boundary stay in lock-step.
"""

from __future__ import annotations

import pytest

from ....core import Period, StandardPeriodCode
from .. import aggregation_period_for_modelo
from ..errors import AggregationValidationError
from ._renta_income_aggregation_support import _period as _canonical_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2025

# The span-shaped canonical members the ledger filters by. Instalment claves
# (``1P``-``4P``) carry no date span, so they are not ledger-filterable spans
# and the translator legitimately rejects them.
_LEDGER_SPAN_TOKENS = tuple(
    code
    for code in StandardPeriodCode
    if code
    not in {
        StandardPeriodCode.P1,
        StandardPeriodCode.P2,
        StandardPeriodCode.P3,
        StandardPeriodCode.P4,
    }
)

# Every alias the purge deleted; each must now raise.
_DELETED_ALIASES = (
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "A",
    "ANUAL",
    "ANNUAL",
    "M01",
    "M02",
    "M03",
    "M04",
    "M05",
    "M06",
    "M07",
    "M08",
    "M09",
    "M10",
    "M11",
    "M12",
)


def _period(code: str, *, year: int = 2025) -> Period:
    """Delegate to the canonical builder, keeping this module's code-first convention."""
    return _canonical_period(year, code)


def test_canonical_span_token_maps_to_typed_period() -> None:
    """Every canonical ledger-span token yields an aggregation Period."""
    for token in _LEDGER_SPAN_TOKENS:
        period = aggregation_period_for_modelo(filing_year=_FILING_YEAR, code=token.value)

        assert period.filing_year == _FILING_YEAR, token.value


def test_canonical_tokens_map_to_expected_typed_periods() -> None:
    """The three canonical shapes resolve to their typed aggregation periods."""
    assert aggregation_period_for_modelo(filing_year=2025, code="1T") == _period("1T")
    assert aggregation_period_for_modelo(filing_year=2025, code="4T") == _period("4T")
    assert aggregation_period_for_modelo(filing_year=2025, code="0A") == _period("0A")
    assert aggregation_period_for_modelo(filing_year=2025, code="03") == _period("03")
    assert aggregation_period_for_modelo(filing_year=2025, code="12") == _period("12")


def test_deleted_alias_tokens_now_raise() -> None:
    """Each purged legacy alias raises instead of silently translating."""
    for alias in _DELETED_ALIASES:
        with pytest.raises(AggregationValidationError):
            aggregation_period_for_modelo(filing_year=_FILING_YEAR, code=alias)


def test_lowercase_canonical_token_is_normalised_not_an_alias() -> None:
    """A lowercase canonical token still resolves (case-fold), not via an alias branch."""
    assert aggregation_period_for_modelo(filing_year=2025, code="1t") == _period("1T")
    assert aggregation_period_for_modelo(filing_year=2025, code="0a") == _period("0A")
