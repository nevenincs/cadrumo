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

import pytest

from ....core.tipos_actividad import TipoActividad
from ...calculations.registry.facts.resolution import ResolvedEntitySetFact
from ...calculations.registry.facts.schema import EntitySetFactPayload, FactOwnership
from ...calculations.registry.schema_base import DateAxis
from ..errors import TransactionValidationError
from ..tipo_actividad_partitions import (
    _ART_95_SELECTORS,
    _typed_code_set,
    load_tipo_actividad_selectors,
    resolve_tipo_actividad_selector,
    tipo_actividad_code_set,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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


@pytest.mark.parametrize(
    ("parameter_id", "expected_ref"),
    (
        (
            "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrario-objetiva",
            "rd-439-2007:art-110",
        ),
        (
            "rd-439-2007-art-109:selector-m036-actividades-exencion-pago-fraccionado",
            "rd-439-2007:art-109",
        ),
        (
            "rd-439-2007-art-109:selector-m036-actividades-base-neta-de-subvenciones",
            "rd-439-2007:art-109",
        ),
    ),
)
def test_non_art_95_activity_selectors_resolve_through_the_same_fact_authority(
    parameter_id: str,
    expected_ref: str,
) -> None:
    selector = resolve_tipo_actividad_selector(parameter_id, effective_date=date(2025, 12, 31))

    assert expected_ref in selector.legal_refs
    assert selector.authority_digest
    assert tipo_actividad_code_set(parameter_id, effective_date=date(2025, 12, 31)) == frozenset(
        TipoActividad(token) for token in selector.payload.entities
    )


def test_typed_code_set_refuses_a_token_that_is_not_a_modelo_036_code() -> None:
    """A selector naming an unknown code is refused, and the message lists the set."""
    selector = ResolvedEntitySetFact(
        fact_id="rirpf-art-95:selector-m036-actividades-profesionales",
        variant_id="rirpf-art-95:selector-m036-actividades-profesionales.current",
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=date(2025, 12, 31),
        valid_from=date.min,
        payload=EntitySetFactPayload(entities=frozenset({"A04", "Z99"})),
        legal_refs=("rd-439-2007:art-95",),
        review_status="agent_reviewed",
        ownership=FactOwnership.GENERATED,
        authority_digest="a" * 64,
    )
    with pytest.raises(TransactionValidationError, match="'Z99'") as raised:
        _typed_code_set(selector)

    # The refusal must name the accepted set, not just the offending token.
    assert "A04" in str(raised.value)
    assert "B05" in str(raised.value)


def test_selector_resolution_refuses_an_unenrolled_parameter() -> None:
    """A missing selector is a loud refusal, never a silently empty partition.

    This is the positive control for the empty-set assertion above: an empty set
    has to mean "declared with no codes", so absence must NOT also produce one.
    """
    with pytest.raises(TransactionValidationError, match="no typed governed"):
        tipo_actividad_code_set("rirpf-art-95:selector-missing", effective_date=date(2025, 12, 31))
