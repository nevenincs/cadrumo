"""The term a cobros y pagos election binds is a dated registry fact.

The expectation is RD 439/2007 art. 7.2.1.º as bundled: "deberá mantenerse durante
un plazo mínimo de tres años", in force since the Real Decreto took effect in 2007.
"""

from __future__ import annotations

import pytest

from ..authority import PinnedAuthorityOperation
from ..cash_election_minimum_years import cash_election_minimum_years
from ..errors import GovernedFactNotApplicableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("filing_year", [2007, 2019, 2022, 2025])
def test_the_election_binds_for_three_years(operation: PinnedAuthorityOperation, filing_year: int) -> None:
    assert cash_election_minimum_years(filing_year=filing_year, authority=operation) == 3


def test_an_ejercicio_before_the_reglamento_declares_no_term(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(GovernedFactNotApplicableError):
        cash_election_minimum_years(filing_year=2006, authority=operation)
