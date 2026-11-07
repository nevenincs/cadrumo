"""Every supported Renta year reads its printed borrador boxes through its own published profile.

The borrador grammar is the printed box number beside its amount, so a year's
profile names box numbers and no row positions. Each year's official Diseño de
Registro dictionary prints the same numbers for the same boxes (0505 base
liquidable general sometida a gravamen, 0545 and 0546 cuota íntegra, 0585 and
0586 cuota líquida incrementada). A synthetic, anonymized draft is rendered
for each year and read back through the real parser under the year's
published profile, so a year that loses its profile, or a profile that stops
naming those boxes, fails here instead of refusing every import.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from .....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from .....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition, ExtractionSurface
from .....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from .....tests.fixtures.borrador.generate import render_borrador_pdf
from ..parser import parse_borrador
from ..schema import ArtefactKind, BorradorParseMode

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_PRINTED_BOXES: dict[CasillaId, Decimal] = {
    "0505": Decimal("41234.56"),
    "0545": Decimal("4321.09"),
    "0546": Decimal("4198.76"),
    "0585": Decimal("4300.01"),
    "0586": Decimal("4100.02"),
}


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot("100", filing_year=year, period="0A")
        except FilingYearOutsideSupportEnvelopeError:
            continue
        years.append(year)
    return tuple(years)


def _borrador_profile(year: int) -> ExtractionProfileDefinition:
    snapshot = published_snapshot("100", filing_year=year, period="0A")
    profiles = [
        profile
        for profile in snapshot.extraction_profiles.values()
        if profile.surface == ExtractionSurface.BORRADOR_PDF
    ]
    assert len(profiles) == 1, f"Modelo 100 {year} declares {len(profiles)} borrador profiles"
    return profiles[0]


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_declares_the_borrador_profile(year: int) -> None:
    assert _borrador_profile(year).id == "modelo-100-borrador-pdf"


@pytest.mark.parametrize("year", _supported_years())
def test_each_supported_year_reads_the_printed_results_through_its_profile(year: int) -> None:
    profile = _borrador_profile(year)
    support = published_supported_filing_years()
    assert support is not None

    observation = parse_borrador(
        render_borrador_pdf(year, _PRINTED_BOXES, tax_id="12345678Z"),
        artefact_kind_override=ArtefactKind.BORRADOR,
        filing_year=year,
        supported_filing_years=support,
        extraction_profile=profile,
        parse_mode=BorradorParseMode.REGISTRY_PROFILE,
    )

    assert sorted(str(target.casilla_id) for target in profile.target_casillas) == sorted(_PRINTED_BOXES)
    assert observation.registry_extraction_profile_id == profile.id
    assert observation.extraction_coverage == Decimal("1")
    assert observation.ejercicio == str(year)
    assert {row.casilla_id: row.printed_value for row in observation.values} == _PRINTED_BOXES
