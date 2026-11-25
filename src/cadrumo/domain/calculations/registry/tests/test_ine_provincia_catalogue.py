"""The INE provincia catalogue resolves for every filing year the registry supports.

Modelo 347 declares a Spanish declarado's CÓDIGO PROVINCIA (pos. 77-78 in both
record designs) by these codes in every supported year, so the one fact that
names them must answer for each year of the support envelope, with the same
fifty-two codes and no 99, which the 347 design reserves for non-residents.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..authority import PinnedAuthorityOperation
from ..form_codes import resolve_form_codes
from ..ine_provincia_catalogue import ine_provincia_names
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_the_catalogue_resolves_the_same_provinces_in_every_supported_year(
    year: int, *, operation: PinnedAuthorityOperation
) -> None:
    codes = resolve_form_codes("ine-provincia-catalogue", effective_date=date(year, 12, 31), authority=operation)

    assert codes.ordered_codes("codes") == tuple(f"{code:02d}" for code in range(1, 53))
    assert dict(codes.under("name")) == dict(ine_provincia_names(authority=operation))
    assert "99" not in codes.ordered_codes("codes")
