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

from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ACTIVIDADES_CHAPTER = frozenset({f"ley-35-2006:art-{n}" for n in (27, 28, 30, 31, 32)})
_GANANCIA_FOUNDATION = frozenset({"ley-35-2006:art-33", "ley-35-2006:art-34"})

# concept-section tag -> the years in which that section exists and was grounded.
_GROUNDED_GANANCIA_SECTIONS: dict[str, tuple[int, ...]] = {
    "elemento_criptomoneda": (2022, 2023, 2024),
    "elemento_inmueble": (2022, 2023, 2024),  # gp_otros_inmuebles (ganancias otros inmuebles)
    "elemento_patrimonial": (2021, 2022, 2023, 2024),  # gp_otros_elementos
    # exención por reinversión sections (ganancia foundation + art. 38)
    "exencion_rentas_vitalicias_res": (2021, 2022, 2023, 2024),
    "exencion_nuevas_empresas_res": (2021, 2022, 2023, 2024),
    # ganancias por transmisión de acciones/participaciones/fondos de inversión
    "entidad_accion": (2021, 2022, 2023, 2024),
    "entidad_derecho": (2021, 2022, 2023, 2024),
    "fondo": (2021, 2022, 2023, 2024),
    # ganancias y pérdidas patrimoniales — sumas/resultado
    "gp_patrimoniales_res": (2021, 2022, 2023, 2024),
    # ganancias y pérdidas a integrar en la base imponible del ahorro (cuartas)
    "gan_per_cuartas": (2021, 2022, 2023, 2024),
    # further ganancia surfaces: FEAC (ganancias diferidas cap. VII), ayudas públicas
    # (ganancias patrimoniales), juegos (ganancias/pérdidas), G4 transmisión de acciones
    "feac": (2023, 2024),
    "otras": (2021, 2022, 2023, 2024),
    "juegos": (2021, 2022, 2023, 2024),
    "g4_re": (2021, 2022, 2023, 2024),
}


def _section_casillas(filing_year: int, section_tag: str):
    modelo, _ = _committed_modelo("100")
    rev = select_revision(modelo, filing_year=filing_year, period="0A")
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
    assert not actividades, f"M100 {year} {section_tag}: boxes still cite the actividades chapter: {actividades}"
    missing = [(c.id, sorted(c.legal_refs)) for c in casillas if not (_GANANCIA_FOUNDATION & set(c.legal_refs))]
    assert not missing, (
        f"M100 {year} {section_tag}: boxes not grounded in the ganancias foundation (arts. 33/34): {missing}"
    )
