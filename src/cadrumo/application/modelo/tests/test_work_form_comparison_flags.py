"""The work form's comparison flags derive from the published registry, not from a modelo number.

``compares_taxation`` holds when the revision declares exactly one filing-mode
casilla and one box for each compared result; ``compares_borrador`` holds when
the revision declares exactly one Borrador PDF extraction profile.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ...live.borrador_100_import import borrador_pdf_extraction_profile
from ..taxation_comparison import revision_compares_taxation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "compares_taxation", "compares_borrador"),
    [
        ("100", 2022, "0A", True, True),
        ("100", 2023, "0A", True, True),
        ("100", 2024, "0A", False, True),
        ("100", 2025, "0A", True, True),
        ("130", 2025, "1T", False, False),
        ("303", 2025, "3T", False, False),
    ],
)
def test_comparison_flags_follow_registry_declarations(
    modelo: str, filing_year: int, period: str, compares_taxation: bool, compares_borrador: bool
) -> None:
    snapshot = published_snapshot(modelo, filing_year=filing_year, period=period)

    assert revision_compares_taxation(snapshot) is compares_taxation
    assert (borrador_pdf_extraction_profile(snapshot) is not None) is compares_borrador
