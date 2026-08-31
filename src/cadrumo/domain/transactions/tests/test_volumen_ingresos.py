"""The art. 110.1.c) volume base: what counts, and that the two homes agree.

The exclusion is declared twice on purpose and that needs guarding rather than
apologising for. :class:`~core.ConceptoIngreso` is the TYPED home, because a closed
value set belongs in ``core`` where production code and tests can hold members rather
than strings. The registry parameter is the GROUNDED home, because the exclusion is a
regulatory fact and regulatory facts carry their ``legal_refs`` in the registry.

Neither can be dropped, so the risk is that they drift. These tests bind them, in the
same shape the binding-source taxonomy uses: the enum is the authority, and a parity
assertion makes a registry edit that disagrees with it a loud failure instead of a
silently divergent second answer.
"""

from __future__ import annotations

import pytest

from ....core.concepto_ingreso import INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE, ConceptoIngreso
from ....core.resources._boundary import bundled_path
from ....core.tipos_actividad import TipoActividad
from ...calculations.registry.loader import load_legal_parameters_only
from ..tipo_actividad_partitions import tipo_actividad_code_set
from ..volumen_ingresos import counts_toward_volumen_de_ingresos

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXCLUDED_PARAM = "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario"
_ACTIVITY_PARAM = "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva"


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
) -> None:
    """Every member, including the two that share the 'subvención' prefix.

    The AEAT Modelo 131 instrucciones for casilla 05 state both sides: *incluidas las
    subvenciones corrientes y excluidas las subvenciones de capital y las
    indemnizaciones*. The parametrisation covers the whole enum rather than a sample,
    because the interesting pair is precisely the one a sample would be tempted to
    treat as interchangeable.
    """
    assert counts_toward_volumen_de_ingresos(concepto) is counts


def test_the_two_subvencion_members_land_on_opposite_sides() -> None:
    """The assertion the prefix trap would break.

    Any implementation keyed on the word "subvención" -- a ``startswith``, a substring
    test, a name-prefix frozenset -- gets exactly one of these wrong, and it is the
    inclusion that breaks: an operating subsidy silently dropped from a declared
    volume. Stated as its own test so the failure names the reason.
    """
    assert counts_toward_volumen_de_ingresos(ConceptoIngreso.SUBVENCION_CORRIENTE)
    assert not counts_toward_volumen_de_ingresos(ConceptoIngreso.SUBVENCION_CAPITAL)


def test_an_undeclared_concept_is_included_rather_than_dropped() -> None:
    """Silence means ordinary income, which is the safe direction for the error.

    Treating an unmarked receipt as excluded would drop real income out of a declared
    volume -- the silent under-declaration this project treats as its worst failure
    mode. The cost, an unmarked capital subsidy over-declaring, is the tolerable side.
    """
    assert counts_toward_volumen_de_ingresos(None) is True


def test_the_registry_exclusion_set_agrees_with_the_typed_one() -> None:
    """Parity between the grounded home and the typed home.

    A registry edit that added or removed an excluded concept without moving
    :data:`INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE` would leave the calculation
    following the enum while the ``legal_refs`` described something else -- grounding
    that had quietly stopped describing the code.
    """
    parameter = load_legal_parameters_only(bundled_path("registry", "aeat"))[_EXCLUDED_PARAM]
    declared = frozenset(ConceptoIngreso(token.strip()) for token in parameter.value.split(",") if token.strip())

    assert declared == INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE


def test_the_art_110_activity_selector_is_not_the_art_95_one() -> None:
    """The agrarian pago fraccionado selector is its own, and must stay its own.

    Art. 110.1.c) names *agrícolas, ganaderas, forestales o pesqueras* while art. 95
    fixes no pesquera rate at all, so the two sets are not interchangeable even though
    they overlap almost completely. Reusing the art. 95 agrícola/ganadera selector for
    a Modelo 131 casilla is the specific mistake this asserts against: it carries no
    forestal code, so a forestal filer's whole quarterly volume would vanish.
    """
    art_110 = tipo_actividad_code_set(_ACTIVITY_PARAM)
    art_95_agrarian = tipo_actividad_code_set("rirpf-art-95:selector-m036-actividades-agricolas-ganaderas")

    assert TipoActividad.B03_FORESTAL in art_110
    assert TipoActividad.B03_FORESTAL not in art_95_agrarian
    assert art_110 != art_95_agrarian
    assert art_95_agrarian < art_110


def test_pesquera_is_absent_and_that_is_the_form_talking_not_the_article() -> None:
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
    declared = tipo_actividad_code_set(_ACTIVITY_PARAM)

    assert TipoActividad.B05_PESQUERA not in declared
    assert TipoActividad.B04_PRODUCCION_DE_MEJILLON not in declared
