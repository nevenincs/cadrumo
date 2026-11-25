"""Edition qualifiers are a binding diagnostic, independent of migration reports."""

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from dev.registry.identifier_edition import edition_token_in_identifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_EARLIEST, _MIDDLE, _LATEST = filing_year_envelope().years[:3]


#: Editions are spelled from the support envelope's years: the identifiers are synthetic, so only their shape matters.
@pytest.mark.parametrize(
    "identifier,edition,expected",
    [
        (f"modelo-303-{_LATEST}-reconciliation", str(_LATEST), str(_LATEST)),
        ("rd-1624-1992:art-71", str(_LATEST), None),
        (f"page_02.{_EARLIEST}-{_LATEST}", f"{_MIDDLE}-{_LATEST}", None),
        (f"modelo-232-{_MIDDLE}-{_LATEST}-vinculada", f"{_MIDDLE}-{_LATEST}", f"{_MIDDLE}-{_LATEST}"),
        ("dr303-09", f"{_LATEST}-desde-09-y-3t", None),
        (f"modelo-303-{_LATEST}-reconciliation", f"{_LATEST}-desde-09-y-3t", str(_LATEST)),
        ("stable-member", str(_LATEST), None),
    ],
)
def test_edition_qualifier(identifier: str, edition: str, expected: str | None) -> None:
    assert edition_token_in_identifier(identifier, edition) == expected
