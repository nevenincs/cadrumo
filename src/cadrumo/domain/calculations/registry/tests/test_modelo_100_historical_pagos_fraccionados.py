"""Every authored Modelo 100 edition folds the M130/M131 pagos-fraccionados relations into 0604.

Each edition carries the same legal grounding on 0604 and the same annual
settlement shape, so all of them must use one relation-prefill mechanism
rather than leaving the credit as a manual gap. The editions come from the
published registry, so a new edition is covered without editing this module.
"""

from __future__ import annotations

from functools import cache

import pytest

from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import FilingYearOutsideSupportEnvelopeError
from . import modelo_100_historical_pagos_fraccionados_scenarios as scenarios
from .published_authority import published_authored_revision, published_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _authored_years() -> tuple[int, ...]:
    """The ejercicio of every Modelo 100 edition the published generation stores."""
    with bundled_indexed_authority().operation() as operation:
        return tuple(
            sorted(
                operation.revision("100", str(metadata.id)).valid_from.year
                for metadata in operation.modelo_directory("100").revisions
            )
        )


@pytest.mark.parametrize("year", _authored_years())
def test_historical_pagos_fraccionados_relation_contract_and_fold(
    registry_authority: PinnedAuthorityOperation,
    year: int,
) -> None:
    """Each authored edition declares the M130/M131 relation contract and folds it into 0604.

    Years below the published filing floor keep their authored contract but
    refuse filing selection, so only in-envelope years run the fold.
    """
    supported_years = published_supported_filing_years()
    assert supported_years is not None
    if year < supported_years.floor:
        scenarios.check_relation_contract(published_authored_revision("100", year=year))
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            registry_authority.snapshot("100", filing_year=year, period="0A")
        return

    scenarios.check_relation_contract_and_fold(
        registry_authority.snapshot("100", filing_year=year, period="0A"), year=year
    )
