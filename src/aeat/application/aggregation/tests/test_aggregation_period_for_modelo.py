"""Deletion regression guard for :func:`aggregation_period_for_modelo`.

After the legacy alias purge (ADR ``2026-06-10-ledger-filter-period``,
decision 2), the translator accepts ONLY the canonical span-shaped
:class:`StandardPeriodCode` tokens (``1T``-``4T``, ``0A``, ``01``-``12``) the
calc engine and the CLI ledger filter share. The deleted calendar-shape aliases
(``Q1``-``Q4``, ``A``, ``ANUAL``, ``ANNUAL``, ``M01``-``M12``) must now raise.
Each canonical token must map to the internal calendar string
:meth:`Period.model_validate` consumes — proving the translator and the shared
:meth:`Period.contains` boundary stay in lock-step.
"""

from __future__ import annotations

import pytest

from ....core import StandardPeriodCode
from .. import Period, aggregation_period_for_modelo
from .._errors import AggregationValidationError

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


@pytest.mark.parametrize("token", _LEDGER_SPAN_TOKENS, ids=[c.value for c in _LEDGER_SPAN_TOKENS])
def test_canonical_span_token_maps_to_a_validatable_internal_calendar_string(
    token: StandardPeriodCode,
) -> None:
    """Every canonical ledger-span token yields an internal string Period accepts."""
    internal = aggregation_period_for_modelo(filing_year=_FILING_YEAR, period=token.value)

    # The result must be the calendar shape Period.model_validate consumes, and
    # the resolved Period must carry the year the translator was asked for.
    period = Period.model_validate(internal)
    assert period.year == _FILING_YEAR


def test_canonical_tokens_map_to_expected_internal_calendar_shapes() -> None:
    """The three canonical shapes resolve to their documented internal strings."""
    assert aggregation_period_for_modelo(filing_year=2025, period="1T") == "2025Q1"
    assert aggregation_period_for_modelo(filing_year=2025, period="4T") == "2025Q4"
    assert aggregation_period_for_modelo(filing_year=2025, period="0A") == "2025"
    assert aggregation_period_for_modelo(filing_year=2025, period="03") == "2025-03"
    assert aggregation_period_for_modelo(filing_year=2025, period="12") == "2025-12"


@pytest.mark.parametrize("alias", _DELETED_ALIASES)
def test_deleted_alias_tokens_now_raise(alias: str) -> None:
    """Each purged legacy alias raises instead of silently translating."""
    with pytest.raises(AggregationValidationError):
        aggregation_period_for_modelo(filing_year=_FILING_YEAR, period=alias)


def test_lowercase_canonical_token_is_normalised_not_an_alias() -> None:
    """A lowercase canonical token still resolves (case-fold), not via an alias branch."""
    assert aggregation_period_for_modelo(filing_year=2025, period="1t") == "2025Q1"
    assert aggregation_period_for_modelo(filing_year=2025, period="0a") == "2025"
