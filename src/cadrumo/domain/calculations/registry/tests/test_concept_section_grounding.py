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

from functools import lru_cache

import pytest

from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ACTIVIDADES_CHAPTER = frozenset({f"ley-35-2006:art-{n}" for n in (27, 28, 30, 31, 32)})

# section tag -> (required article(s), years the section exists)
_CONCEPT_SECTION_GROUNDING: dict[str, tuple[str | tuple[str, ...], tuple[int, ...]]] = {
    # saldos negativos de ganancias y pérdidas — integración y compensación
    "saldos_neg_gy_p_general_res": ("ley-35-2006:art-48", (2021, 2022, 2023, 2024)),
    "saldos_neg_gy_p_ahorro_res": ("ley-35-2006:art-49", (2021, 2022, 2023, 2024)),
    # deducciones en cuota acogidas al régimen del IS (I+D, cine, etc.) — art. 68.2 LIRPF
    "deducciones_inversion_empresarial_res": ("ley-35-2006:art-68.2", (2021, 2022, 2023, 2024)),
    # mínimo personal y familiar (resultado) — art. 56 (umbrella de arts. 56-61)
    "minimo_per_fam_res": ("ley-35-2006:art-56", (2021, 2022, 2023, 2024)),
    # rendimientos de capital mobiliario negativos pendientes — integración base ahorro
    "rdtos_cm_negativos_res": ("ley-35-2006:art-49", (2021, 2022, 2023, 2024)),
    # deducción por alquiler de la vivienda habitual (régimen transitorio) — DT-15ª
    "deduccion_alquiler_res": ("ley-35-2006:dt-15", (2021, 2022, 2023, 2024)),
    # deducciones por familia numerosa y personas con discapacidad a cargo — art. 81 bis
    "deduc_familia_numerosa_res": ("ley-35-2006:art-81-bis", (2021, 2022, 2023, 2024)),
    "deduc_ascendiente_disc_res": ("ley-35-2006:art-81-bis", (2021, 2022, 2023, 2024)),
    "deduc_descendiente_disc_res": ("ley-35-2006:art-81-bis", (2021, 2022, 2023, 2024)),
    "deduc_conyuge_disc_res": ("ley-35-2006:art-81-bis", (2021, 2022, 2023, 2024)),
    # base imponible is a mixed result section: general base -> art. 48,
    # savings base -> art. 49.
    "base_imponible_res": (("ley-35-2006:art-48", "ley-35-2006:art-49"), (2021, 2022, 2023, 2024)),
    "base_liquidable_res": ("ley-35-2006:art-50", (2021, 2022, 2023, 2024)),
    # base liquidable general negativa (carry-forward) — art. 50; grounded via the
    # binding-aware pass (casilla + construct + binding coherently, resolving V19).
    "base_liq_neg_res": ("ley-35-2006:art-50", (2021, 2022, 2023, 2024)),
    # reducciones de la base imponible (aggregate) — art. 50 (base liquidable = base
    # imponible - reducciones); specific reduction outputs can bind to their own
    # article instead via _SECTION_ROLE_GROUNDING_OVERRIDES.
    "red_base_imponible_res": ("ley-35-2006:art-50", (2021, 2022, 2023, 2024)),
}

_SECTION_ROLE_GROUNDING_OVERRIDES: dict[tuple[str, int, str], tuple[str, ...]] = {
    (
        "red_base_imponible_res",
        2024,
        "irpf_reduccion_tributacion_conjunta_importe",
    ): ("ley-35-2006:art-84",),
}


@lru_cache
def _m100_revision(filing_year: int):
    modelo, _ = _committed_modelo("100")
    return select_revision(modelo, filing_year=filing_year, period="0A")


def _section_casillas(filing_year: int, section_tag: str):
    rev = _m100_revision(filing_year)
    return [c for c in rev.casillas if section_tag in tuple(c.section)]


def _concept_section_cases():
    for tag, (articles, years) in _CONCEPT_SECTION_GROUNDING.items():
        expected_articles = (articles,) if isinstance(articles, str) else articles
        for y in years:
            yield tag, expected_articles, y


def test_concept_section_grounds_in_its_article_not_actividades() -> None:
    """Every box in a corrected concept-section carries its concept article and no
    actividades article."""
    for section_tag, articles, year in _concept_section_cases():
        casillas = _section_casillas(year, section_tag)
        assert casillas, f"M100 {year} section {section_tag} must have casillas"
        actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
        assert not actividades, f"M100 {year} {section_tag}: boxes still cite the actividades chapter: {actividades}"
        missing = []
        for casilla in casillas:
            semantic_role = casilla.semantic_role or ""
            expected = set(
                _SECTION_ROLE_GROUNDING_OVERRIDES.get(
                    (section_tag, year, semantic_role),
                    articles,
                )
            )
            if expected.isdisjoint(casilla.legal_refs):
                missing.append((casilla.id, sorted(expected), sorted(casilla.legal_refs)))
        assert not missing, f"M100 {year} {section_tag}: boxes not grounded in their article: {missing}"


def _prevision_social_casillas(filing_year: int):
    """Boxes for aportaciones/excesos a sistemas de previsión social + seguros
    colectivos de dependencia (arts. 51/52), excluding patrimonio-protegido (art. 54)
    and deportistas (DA-11ª) which share the 'excesos' prefix but bind to other law."""
    rev = _m100_revision(filing_year)
    out = []
    for c in rev.casillas:
        sec = "/".join(tuple(c.section))
        if ("prevision_social" in sec or "seguros_colectivos_dependencia" in sec) and (
            "patrim_protegid" not in sec and "deportista" not in sec
        ):
            out.append(c)
    return out


def test_prevision_social_grounds_in_arts_51_52_not_actividades() -> None:
    """Previsión-social aportación/exceso boxes cite art. 51 (and not the actividades
    chapter) — the binding reduction provision (límite conjunto in art. 52)."""
    for year in (2021, 2022, 2023, 2024):
        casillas = _prevision_social_casillas(year)
        assert casillas, f"M100 {year}: previsión-social section must have casillas"
        actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
        assert not actividades, f"M100 {year}: previsión-social boxes still cite the actividades chapter: {actividades}"
        missing = [(c.id, sorted(c.legal_refs)) for c in casillas if "ley-35-2006:art-51" not in set(c.legal_refs)]
        assert not missing, f"M100 {year}: previsión-social boxes not grounded in art. 51: {missing}"


_AUTONOMIC_COMUNIDADES = (
    "valenciana",
    "canarias",
    "asturias",
    "la_rioja",
    "i_baleares",
    "madrid",
    "castilla_la_mancha",
    "castilla_y_leon",
    "galicia",
    "murcia",
    "cantabria",
    "aragon",
    "andalucia",
    "catalunya",
    "extremadura",
    "navarra",
    "la_palma",
    "c_valenciana",
    "deduccion_autonomica",
    "datos_adicionales_anexo_b",  # Anexo B = autonomic-deductions annex (info blocks)
)
_AUTONOMIC_DEDUCTION_FRAMEWORK_REF = "ley-35-2006:art-77"
_AUTONOMIC_DEDUCTION_REFS_BY_ROLE = {
    "irpf_deduccion_nueva_empresa_entidad_nif": "ley-35-2006:art-68.1",
}


def _autonomic_deduction_casillas(filing_year: int):
    """Comunidad-named autonomic-deduction sections. Their LIRPF home is art. 77
    (cuota líquida autonómica = cuota íntegra autonómica − deducciones autonómicas);
    the specific comunidad-law article is a future refinement on this framework."""
    rev = _m100_revision(filing_year)
    out = []
    for c in rev.casillas:
        sec = "/".join(tuple(c.section))
        if any(com in sec for com in _AUTONOMIC_COMUNIDADES):
            out.append(c)
    return out


def test_autonomic_deductions_ground_in_own_article_not_actividades() -> None:
    """Autonomic-deduction boxes cite their governing deduction article and never
    the actividades chapter.

    Most Anexo B autonomic-deduction boxes bind to art. 77 (cuota líquida
    autonómica). New-company entity NIF boxes are still additional Anexo B data, but
    their governing deduction provision is art. 68.1.
    """
    for year in (2021, 2022, 2023, 2024):
        casillas = _autonomic_deduction_casillas(year)
        assert casillas, f"M100 {year}: autonomic-deduction sections must have casillas"
        actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
        assert not actividades, (
            f"M100 {year}: autonomic-deduction boxes still cite the actividades chapter: {actividades[:10]}"
        )
        missing = []
        for casilla in casillas:
            expected_ref = _AUTONOMIC_DEDUCTION_REFS_BY_ROLE.get(
                casilla.semantic_role, _AUTONOMIC_DEDUCTION_FRAMEWORK_REF
            )
            if expected_ref not in set(casilla.legal_refs):
                missing.append((casilla.id, casilla.semantic_role, expected_ref, sorted(casilla.legal_refs)))
        assert not missing, f"M100 {year}: autonomic-deduction boxes not grounded in their article: {missing[:10]}"


def _casillas_with_section_substr(filing_year: int, needle: str):
    rev = _m100_revision(filing_year)
    return [c for c in rev.casillas if needle in "/".join(tuple(c.section))]


# section-substring -> (article every box must carry, years the section exists).
_SUBSTRING_CONCEPTS: dict[str, tuple[str, tuple[int, ...]]] = {
    "patrim_protegid": ("ley-35-2006:art-54", (2021, 2022, 2023, 2024)),  # patrimonio protegido
    "deportista": ("ley-35-2006:da-11", (2021, 2022, 2023, 2024)),  # mutualidad deportistas
    "anualidades_alimentos": ("ley-35-2006:art-64", (2022, 2023, 2024)),  # anualidades por alimentos
    "deduccion_vivienda_habitual": ("ley-35-2006:dt-18", (2021, 2022, 2023, 2024)),  # DT-18ª vivienda
    "mejoras_energeticas": ("ley-35-2006:da-50", (2021, 2022, 2023, 2024)),  # DA-50ª eficiencia energética
    "eficiencia_energetica": ("ley-35-2006:da-50", (2022, 2023, 2024)),
    "vehiculos_elec": ("ley-35-2006:da-58", (2023, 2024)),  # DA-58ª vehículos eléctricos
    # régimen de atribución de rentas + AIE — framework art. 86 (attributed income; the
    # underlying source nature is a refinement, like autonomic→art.77).
    "re_at_rentas": ("ley-35-2006:art-86", (2021, 2022, 2023, 2024)),
    "re_agrup_interes_economico": ("ley-35-2006:art-86", (2021, 2022, 2023, 2024)),
}


def _substring_cases():
    for needle, (article, years) in _SUBSTRING_CONCEPTS.items():
        for y in years:
            yield needle, article, y


def test_substring_concept_section_grounding() -> None:
    """Boxes in a concept-section (matched by section substring) carry the concept's
    article and never the actividades chapter."""
    for needle, article, year in _substring_cases():
        casillas = _casillas_with_section_substr(year, needle)
        assert casillas, f"M100 {year}: section substring '{needle}' must have casillas"
        actividades = [(c.id, sorted(c.legal_refs)) for c in casillas if _ACTIVIDADES_CHAPTER & set(c.legal_refs)]
        assert not actividades, f"M100 {year} '{needle}': boxes still cite the actividades chapter: {actividades}"
        missing = [(c.id, sorted(c.legal_refs)) for c in casillas if article not in set(c.legal_refs)]
        assert not missing, f"M100 {year} '{needle}': boxes not grounded in {article}: {missing}"
