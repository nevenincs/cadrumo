"""General grounding gate for M100 concept-sections regrounded from the
actividades generic-default (V12 finding).

Each non-ganancia concept-section that had drifted to the actividades chapter
(arts. 27/28/30/31/32) is regrounded to ITS OWN concept's binding article(s), keyed
by the renumbering-immune section tag. This gate maps each corrected section tag to
the article(s) it must now carry and asserts (a) no actividades article remains and
(b) the concept's article is present, across the years the section exists.

Ganancias-by-asset sections live in ``test_ganancias_seccion_grounding`` (foundation
arts. 33/34); this module covers the other concepts.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_ACTIVIDADES_CHAPTER = frozenset({f"ley-35-2006:art-{n}" for n in (27, 28, 30, 31, 32)})

# section tag -> (required article that must be present, years the section exists)
_CONCEPT_SECTION_GROUNDING: dict[str, tuple[str, tuple[int, ...]]] = {
    # saldos negativos de ganancias y pérdidas — integración y compensación
    "saldos_neg_gy_p_general_res": ("ley-35-2006:art-48", (2021, 2022, 2023, 2024)),
    "saldos_neg_gy_p_ahorro_res": ("ley-35-2006:art-49", (2021, 2022, 2023, 2024)),
}


def _section_casillas(filing_year: int, section_tag: str):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelos_by_id = {m.id: m for m in modelos}
    rev = select_revision(modelos_by_id["100"], filing_year=filing_year, period="0A")
    return [c for c in rev.casillas if section_tag in tuple(c.section)]


def _params():
    for tag, (article, years) in _CONCEPT_SECTION_GROUNDING.items():
        for y in years:
            yield pytest.param(tag, article, y, id=f"{tag}-{y}")


@pytest.mark.parametrize(("section_tag", "article", "year"), list(_params()))
def test_concept_section_grounds_in_its_article_not_actividades(
    section_tag: str, article: str, year: int
) -> None:
    """Every box in a corrected concept-section carries its concept article and no
    actividades article."""
    casillas = _section_casillas(year, section_tag)
    assert casillas, f"M100 {year} section {section_tag} must have casillas"
    actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
    assert not actividades, (
        f"M100 {year} {section_tag}: boxes still cite the actividades chapter: {actividades}"
    )
    missing = [(c.id, sorted(c.legal_refs)) for c in casillas if article not in set(c.legal_refs)]
    assert not missing, (
        f"M100 {year} {section_tag}: boxes not grounded in {article}: {missing}"
    )
