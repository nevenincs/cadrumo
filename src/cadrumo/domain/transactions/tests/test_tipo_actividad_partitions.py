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

from datetime import date
from typing import Final

import pytest

from ....core.tipos_actividad import TipoActividad
from ..errors import TransactionValidationError
from ..tipo_actividad_partitions import (
    _ART_95_SELECTORS,
    _code_set,
    load_tipo_actividad_selectors,
    resolve_tipo_actividad_selector,
)

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


def test_art_95_selector_resolution_retains_typed_fact_provenance() -> None:
    """The activity partition facade resolves an entity-set fact at its filing coordinate."""
    selector = resolve_tipo_actividad_selector(
        "rirpf-art-95:selector-m036-actividades-profesionales",
        effective_date=date(2025, 12, 31),
    )

    assert selector.payload.entities == frozenset({"A04", "A05"})
    assert selector.effective_date == date(2025, 12, 31)
    assert "rd-439-2007:art-95" in selector.legal_refs
    assert selector.authority_digest


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
