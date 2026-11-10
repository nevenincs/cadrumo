"""The term a cobros y pagos election binds is a dated registry fact.

The expectation is RD 439/2007 art. 7.2.1.º as bundled: "deberá mantenerse durante
un plazo mínimo de tres años", in force from the first ejercicio the registry fact declares (the Real Decreto's own
entry into force) and through every supported ejercicio.
"""

from __future__ import annotations

import pytest

from ..authority import PinnedAuthorityOperation
from ..cash_election_minimum_years import cash_election_minimum_years
from ..errors import GovernedFactNotApplicableError
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _first_declared_ejercicio(operation: PinnedAuthorityOperation) -> int:
    return min(
        variant.valid_from.year
        for variant in operation.governed_fact("rirpf-art-7-cash-election-minimum-years").variants
    )


@pytest.mark.parametrize("filing_year", filing_year_envelope().years)
def test_the_election_binds_for_three_years_in_every_supported_ejercicio(
    operation: PinnedAuthorityOperation, filing_year: int
) -> None:
    assert cash_election_minimum_years(filing_year=filing_year, authority=operation) == 3


def test_the_election_binds_for_three_years_from_the_first_declared_ejercicio(
    operation: PinnedAuthorityOperation,
) -> None:
    first = _first_declared_ejercicio(operation)
    assert first <= filing_year_envelope().floor, "the fact must reach every supported ejercicio"
    assert cash_election_minimum_years(filing_year=first, authority=operation) == 3


def test_an_ejercicio_before_the_reglamento_declares_no_term(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(GovernedFactNotApplicableError):
        cash_election_minimum_years(filing_year=_first_declared_ejercicio(operation) - 1, authority=operation)
