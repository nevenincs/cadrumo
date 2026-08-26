"""The Modelo 036 activity axis and its registry-declared art. 95 partitions.

These tests assert the correspondence is registry DATA and that the gap in it is
declared rather than absent. They deliberately do not restate the mapping as an
expected literal for its own sake: a test that hard-codes ``A04 -> profesional``
and compares it to the loader would pass just as well if both were wrong
together. What is asserted instead is the structure the mapping must have
(partition-exclusive, drawn from the closed code set, complete over the four
apartados) plus the two correspondences whose LEGAL basis is the reason they are
not inferences, cited to the apartado that fixes them.
"""

from __future__ import annotations

from typing import Final

import pytest

from ....core import IAE_SUBJECT_TIPOS_ACTIVIDAD, NON_IAE_SUBJECT_TIPOS_ACTIVIDAD, TipoActividad
from ...deadlines import IrpfActivityKind
from .._tipo_actividad_partitions import (
    _ART_95_SELECTORS,
    _code_set,
    irpf_activity_kind_for,
    load_tipo_actividad_selectors,
)
from ..errors import TransactionValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SELECTOR_UNIT: Final[str] = "m036-tipo-actividad-code-set"


class _ParameterLike:
    """A parameter-shaped value object for exercising the pure parser.

    Not a mock of the registry: the parser reads ``unit`` and ``value`` off
    whatever it is handed, and these tests feed it malformed inputs the committed
    registry must never contain. The registry-backed path is covered separately by
    every other test in this module.
    """

    def __init__(self, *, unit: str, value: object) -> None:
        self.unit = unit
        self.value = value


def test_every_partition_is_declared_including_the_one_no_code_selects() -> None:
    """All four art. 95 partitions are present; the engorde carve-out is empty.

    The empty set is the finding, not an oversight. Art. 95.4.1.º fixes 1 % for
    engorde de porcino y avicultura, and the Modelo 036 table's finest livestock
    grain is ``B02 Ganadera``, so no code reaches it. Declaring the partition with
    no codes keeps the gap where a reader looks for the mapping; dropping the
    entry would make the file read as a complete partition of art. 95.
    """
    selectors = load_tipo_actividad_selectors()
    engorde = "rirpf-art-95:selector-m036-actividades-ganaderas-engorde-porcino-avicultura"

    assert set(selectors) == set(_ART_95_SELECTORS)
    assert selectors[engorde] == frozenset()
    assert all(codes for parameter_id, codes in selectors.items() if parameter_id != engorde)


def test_no_code_selects_two_partitions() -> None:
    """A code selects at most one partition, so a rate lookup cannot be ambiguous."""
    selected = [code for codes in load_tipo_actividad_selectors().values() for code in codes]

    assert len(selected) == len(set(selected))


def test_every_selected_code_is_a_real_modelo_036_code() -> None:
    """Selectors draw from the closed code set, never a free-form token."""
    for codes in load_tipo_actividad_selectors().values():
        assert all(isinstance(code, TipoActividad) for code in codes)


def test_artisticas_partitions_as_professional_because_art_95_2_a_says_so() -> None:
    """``A04`` is professional by apartado 2.a), not by resemblance.

    Art. 95.2.a) counts *las actividades incluidas en las Secciones Segunda y
    Tercera de las Tarifas del IAE* among rendimientos de actividades
    profesionales. ``A05 Profesionales`` is Sección Segunda and ``A04 Artísticas y
    Deportivas`` is Sección Tercera, so both select the same partition. Without
    that paragraph the ``A04`` half would be a guess, which is why this assertion
    names it.
    """
    assert irpf_activity_kind_for(TipoActividad.A04_ARTISTICAS_Y_DEPORTIVAS) is IrpfActivityKind.PROFESIONAL
    assert irpf_activity_kind_for(TipoActividad.A05_PROFESIONALES) is IrpfActivityKind.PROFESIONAL


def test_ganaderia_independiente_partitions_agrarian_across_the_iae_split() -> None:
    """``A02`` partitions with the livestock codes although it sits on the IAE side.

    The Modelo 036 table separates activities by IAE subjection, and ``A02
    Ganadería independiente`` is on the subject side while ``B02 Ganadera`` is not.
    Art. 95.4 crosses that line explicitly -- *Se entenderán incluidas entre las
    actividades agrícolas y ganaderas: a) La ganadería independiente* -- so the
    partition follows the activity's nature, not the table's own split.
    """
    assert TipoActividad.A02_GANADERIA_INDEPENDIENTE in IAE_SUBJECT_TIPOS_ACTIVIDAD
    assert TipoActividad.B02_GANADERA in NON_IAE_SUBJECT_TIPOS_ACTIVIDAD
    assert (
        irpf_activity_kind_for(TipoActividad.A02_GANADERIA_INDEPENDIENTE)
        is irpf_activity_kind_for(TipoActividad.B02_GANADERA)
        is IrpfActivityKind.SECTORIAL
    )


@pytest.mark.parametrize(
    "tipo",
    [
        TipoActividad.A01_ARRENDADORES_BIENES_INMUEBLES,
        TipoActividad.A03_RESTO_EMPRESARIALES,
        TipoActividad.B04_PRODUCCION_DE_MEJILLON,
        TipoActividad.B05_PESQUERA,
    ],
)
def test_codes_art_95_fixes_no_rate_for_select_nothing(tipo: TipoActividad) -> None:
    """Arrendamiento, resto empresariales, mejillón and pesquera select no partition.

    Arrendamiento retains under art. 100, and the other three reach art. 95 only
    through apartado 6.1.º by estimación objetiva -- a method axis, not an activity
    one. Returning ``None`` for them is correct; folding them into any partition
    would apply a rate the article does not fix for that activity.
    """
    assert irpf_activity_kind_for(tipo) is None


def test_parser_refuses_a_token_that_is_not_a_modelo_036_code() -> None:
    """A selector naming an unknown code is refused, and the message lists the set."""
    with pytest.raises(TransactionValidationError, match="'Z99'") as raised:
        _code_set({"p": _ParameterLike(unit=_SELECTOR_UNIT, value="A04,Z99")}, "p")

    # The refusal must name the accepted set, not just the offending token.
    assert "A04" in str(raised.value)
    assert "B05" in str(raised.value)


def test_parser_refuses_a_parameter_carrying_the_wrong_unit() -> None:
    """A rate parameter read as a selector is refused rather than parsed as codes.

    The selector parameters live beside the rate parameters in the same file, so
    the unit is what stops ``0.15`` being read as a code list.
    """
    with pytest.raises(TransactionValidationError, match="carries unit"):
        _code_set({"p": _ParameterLike(unit="fraction", value="0.15")}, "p")


def test_parser_refuses_an_absent_parameter() -> None:
    """A missing selector is a loud refusal, never a silently empty partition.

    This is the positive control for the empty-set assertion above: an empty set
    has to mean "declared with no codes", so absence must NOT also produce one.
    """
    with pytest.raises(TransactionValidationError, match="is absent"):
        _code_set({}, "rirpf-art-95:selector-m036-actividades-profesionales")
