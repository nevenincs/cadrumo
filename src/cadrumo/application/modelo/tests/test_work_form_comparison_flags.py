"""The work form's comparison flags derive from the published registry, not from a modelo number.

``compares_taxation`` holds when the revision declares exactly one filing-mode
casilla and one box for each compared result; ``compares_borrador`` holds when
the revision declares exactly one Borrador PDF extraction profile.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    projected_exercise,
    supported_exercises_with_projection,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ...live.borrador_100_import import borrador_pdf_extraction_profile
from ..taxation_comparison import revision_compares_taxation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "compares_taxation", "compares_borrador"),
    [
        *(("100", year, "0A", True, True) for year in supported_exercises_with_projection("100")),
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


def test_projected_year_serves_the_capabilities_of_its_source_edition() -> None:
    """A filing year no edition authors reads the newest edition's design, so it serves the same comparisons."""
    projected = projected_exercise("100")
    source = published_snapshot("100", filing_year=newest_authored_edition("100"), period="0A")

    snapshot = published_snapshot("100", filing_year=projected, period="0A")

    assert snapshot.revision.id == source.revision.id
    assert revision_compares_taxation(snapshot) is revision_compares_taxation(source) is True
    assert borrador_pdf_extraction_profile(snapshot) == borrador_pdf_extraction_profile(source)
    assert borrador_pdf_extraction_profile(snapshot) is not None
