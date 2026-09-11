"""The art. 110.1.c) volume base and its governed legal authority.

``ConceptoIngreso`` is product vocabulary only.  The governed entity-set fact is the
sole authority for whether that vocabulary is excluded from the regulatory base.
"""

from __future__ import annotations

from datetime import date

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.compiler.fact_loader import load_governed_facts

from ....core.concepto_ingreso import ConceptoIngreso
from ....core.resources.bundled_data import bundled_path
from ....core.tipos_actividad import TipoActividad
from ...calculations.registry.authority import ValidatedRegistryAuthority
from ..tipo_actividad_partitions import tipo_actividad_code_set
from ..volumen_ingresos import counts_toward_volumen_de_ingresos

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXCLUDED_FACT = "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario"
_ACTIVITY_FACT_ID = "modelo-131:selector-m036-volumen-ingresos-agrario"


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


@pytest.mark.parametrize(
    ("concepto", "counts"),
    [
        (None, True),
        (ConceptoIngreso.ORDINARIO, True),
        (ConceptoIngreso.SUBVENCION_CORRIENTE, True),
        (ConceptoIngreso.SUBVENCION_CAPITAL, False),
        (ConceptoIngreso.INDEMNIZACION, False),
    ],
)
def test_the_predicate_splits_where_the_instrucciones_split(
    concepto: ConceptoIngreso | None,
    *,
    counts: bool,
    authority: ValidatedRegistryAuthority,
) -> None:
    """Every member, including the two that share the 'subvención' prefix.

    The AEAT Modelo 131 instrucciones for casilla 05 state both sides: *incluidas las
    subvenciones corrientes y excluidas las subvenciones de capital y las
    indemnizaciones*. The parametrisation covers the whole enum rather than a sample,
    because the interesting pair is precisely the one a sample would be tempted to
    treat as interchangeable.
    """
    assert counts_toward_volumen_de_ingresos(concepto, effective_date=date(2026, 4, 1), authority=authority) is counts


def test_the_two_subvencion_members_land_on_opposite_sides(authority: ValidatedRegistryAuthority) -> None:
    """The assertion the prefix trap would break.

    Any implementation keyed on the word "subvención" -- a ``startswith``, a substring
    test, a name-prefix frozenset -- gets exactly one of these wrong, and it is the
    inclusion that breaks: an operating subsidy silently dropped from a declared
    volume. Stated as its own test so the failure names the reason.
    """
    assert counts_toward_volumen_de_ingresos(
        ConceptoIngreso.SUBVENCION_CORRIENTE, effective_date=date(2026, 4, 1), authority=authority
    )
    assert not counts_toward_volumen_de_ingresos(
        ConceptoIngreso.SUBVENCION_CAPITAL, effective_date=date(2026, 4, 1), authority=authority
    )


def test_an_undeclared_concept_is_included_rather_than_dropped() -> None:
    """Silence means ordinary income, which is the safe direction for the error.

    Treating an unmarked receipt as excluded would drop real income out of a declared
    volume -- the silent under-declaration this project treats as its worst failure
    mode. The cost, an unmarked capital subsidy over-declaring, is the tolerable side.
    """
    assert counts_toward_volumen_de_ingresos(None, effective_date=date(2026, 4, 1)) is True


def test_the_registry_exclusion_set_agrees_with_the_typed_one() -> None:
    """Parity between the grounded home and the typed home.

    The governed fact is the sole legal authority for membership.  The enum only
    supplies the product vocabulary used to interpret its declared tokens.
    """
    fact = next(
        fact
        for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))
        if fact.fact_id == _EXCLUDED_FACT
    )
    declared = frozenset(ConceptoIngreso(token) for token in fact.variants[0].payload.entities)

    assert declared == {ConceptoIngreso.SUBVENCION_CAPITAL, ConceptoIngreso.INDEMNIZACION}


def test_the_modelo_131_activity_selector_is_not_the_art_95_one(authority: ValidatedRegistryAuthority) -> None:
    """The form-specific agrarian selector is its own, and must stay its own.

    Modelo 131 instructions name agricultural, livestock, and forestry activity;
    art. 95's agricultural/livestock set has no forestry code. Reusing it for a
    Modelo 131 casilla would therefore drop a forestry filer's quarterly volume.
    """
    m131 = tipo_actividad_code_set(_ACTIVITY_FACT_ID, effective_date=date(2026, 4, 1), authority=authority)
    art_95_agrarian = tipo_actividad_code_set(
        "rirpf-art-95:selector-m036-actividades-agricolas-ganaderas",
        effective_date=date(2026, 4, 1),
        authority=authority,
    )

    assert TipoActividad.B03_FORESTAL in m131
    assert TipoActividad.B03_FORESTAL not in art_95_agrarian
    assert m131 != art_95_agrarian
    assert art_95_agrarian < m131


def test_pesquera_is_absent_because_the_form_is_narrower_than_article_110(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Modelo 131 is estimación objetiva, and pesca is not in the módulos regime.

    The article's wording is wider than this casilla. The AEAT Modelo 131
    instrucciones place the casilla-05 block under actividades agrícolas, ganaderas y
    forestales and do not mention pesqueras anywhere, so the narrower set is grounded
    in the form rather than in a reading of art. 110.

    Asserting the absence keeps the reason attached to it: a later reader who notices
    the article says *pesqueras* and "fixes" the selector by adding ``B05`` would be
    modelling an activity this form cannot present -- and would then face the
    ``B04`` mejillón question that the current set deliberately never raises.
    """
    declared = tipo_actividad_code_set(_ACTIVITY_FACT_ID, effective_date=date(2026, 4, 1), authority=authority)

    assert TipoActividad.B05_PESQUERA not in declared
    assert TipoActividad.B04_PRODUCCION_DE_MEJILLON not in declared
