"""Grounding gate for M100 ganancias-patrimoniales concept-sections.

Per the V12 audit finding, the actividades chapter (arts. 27/28/30/31/32) was used
as a generic-default grounding across many non-actividades data-entry sections. The
safe discriminator is the SECTION TAG (concept-specific and stable across years), not
the id range (which renumbers). Each ganancias-by-asset concept-section is grounded to
the ganancias foundation (arts. 33 concepto + 34 importe) — foundation-correct for every
box in the section, never the actividades chapter. This gate pins the sections corrected
so far and is extended as further concept-sections are grounded.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_ACTIVIDADES_CHAPTER = frozenset({f"ley-35-2006:art-{n}" for n in (27, 28, 30, 31, 32)})
_GANANCIA_FOUNDATION = frozenset({"ley-35-2006:art-33", "ley-35-2006:art-34"})

# concept-section tag -> the years in which that section exists and was grounded.
_GROUNDED_GANANCIA_SECTIONS: dict[str, tuple[int, ...]] = {
    "elemento_criptomoneda": (2022, 2023, 2024),
}


def _section_casillas(filing_year: int, section_tag: str):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelos_by_id = {m.id: m for m in modelos}
    rev = select_revision(modelos_by_id["100"], filing_year=filing_year, period="0A")
    return [c for c in rev.casillas if section_tag in tuple(c.section)]


def _section_year_params():
    for tag, years in _GROUNDED_GANANCIA_SECTIONS.items():
        for y in years:
            yield pytest.param(tag, y, id=f"{tag}-{y}")


@pytest.mark.parametrize(("section_tag", "year"), list(_section_year_params()))
def test_ganancia_section_grounds_in_foundation_not_actividades(section_tag: str, year: int) -> None:
    """Every box in a grounded ganancias concept-section grounds in the arts. 33/34
    foundation and never the actividades chapter."""
    casillas = _section_casillas(year, section_tag)
    assert casillas, f"M100 {year} section {section_tag} must have casillas"
    actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
    assert not actividades, (
        f"M100 {year} {section_tag}: boxes still cite the actividades chapter: {actividades}"
    )
    missing = [
        (c.id, sorted(c.legal_refs))
        for c in casillas
        if not (_GANANCIA_FOUNDATION & set(c.legal_refs))
    ]
    assert not missing, (
        f"M100 {year} {section_tag}: boxes not grounded in the ganancias foundation "
        f"(arts. 33/34): {missing}"
    )
