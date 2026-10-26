"""Edition qualifiers are a binding diagnostic, independent of migration reports."""

import pytest

from dev.registry.identifier_edition import edition_token_in_identifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    "identifier,edition,expected",
    [
        ("modelo-303-2025-reconciliation", "2025", "2025"),
        ("rd-1624-1992:art-71", "2025", None),
        ("page_02.2001-2017", "2016-2017", None),
        ("modelo-232-2016-2017-vinculada", "2016-2017", "2016-2017"),
        ("dr303-09", "2024-desde-09-y-3t", None),
        ("modelo-303-2024-reconciliation", "2024-desde-09-y-3t", "2024"),
        ("stable-member", "2025", None),
    ],
)
def test_edition_qualifier(identifier: str, edition: str, expected: str | None) -> None:
    assert edition_token_in_identifier(identifier, edition) == expected
