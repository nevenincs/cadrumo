"""Every casilla of a published revision projects onto the grammar its engine channel accepts.

Run over the real published registry (Modelo 303 and Modelo 714), not a
fixture: the channel of each data type is what the calculation boundary reads,
and a projection that disagreed with it would admit a value the engine refuses.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..edit_value_grammar import (
    ModeloEditRatioUnit,
    ModeloEditValueChannel,
    ModeloEditValueFamily,
    binding_value_grammar,
    casilla_value_grammar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPECTED_CHANNEL: dict[str, ModeloEditValueChannel] = {
    CasillaDataType.MONEY: ModeloEditValueChannel.DECIMAL,
    CasillaDataType.DECIMAL: ModeloEditValueChannel.DECIMAL,
    CasillaDataType.RATIO: ModeloEditValueChannel.DECIMAL,
    CasillaDataType.INTEGER: ModeloEditValueChannel.DECIMAL,
    CasillaDataType.BOOLEAN: ModeloEditValueChannel.DECIMAL,
    CasillaDataType.YEAR: ModeloEditValueChannel.UNAVAILABLE,
    CasillaDataType.DATE: ModeloEditValueChannel.UNAVAILABLE,
}


@pytest.mark.parametrize(("modelo", "year", "period"), [("303", 2025, "1T"), ("714", 2025, "0A")])
def test_each_casilla_projects_onto_the_channel_the_engine_reads(modelo: str, year: int, period: str) -> None:
    revision = published_snapshot(modelo, filing_year=year, period=period).revision

    for casilla in revision.casillas:
        grammar = casilla_value_grammar(casilla)
        data_type = str(casilla.data_type)
        assert grammar.channel is _EXPECTED_CHANNEL.get(data_type, ModeloEditValueChannel.TEXT), casilla.id
        assert grammar.money_operand_bound is (data_type == CasillaDataType.MONEY)
        if data_type == CasillaDataType.MONEY:
            assert grammar.max_fraction_digits == 2
        if data_type == CasillaDataType.INTEGER:
            assert grammar.max_fraction_digits == 0
        assert grammar.required is casilla.required
        assert grammar.constraints_declared is (casilla.constraints is not None)
        if data_type == CasillaDataType.BOOLEAN:
            assert grammar.family is ModeloEditValueFamily.BOOLEAN


def test_a_ratio_unit_is_known_only_where_its_bounds_say_so() -> None:
    revision = published_snapshot("303", filing_year=2025, period="1T").revision
    units = {
        casilla.id: casilla_value_grammar(casilla).ratio_unit
        for casilla in revision.casillas
        if casilla.data_type == CasillaDataType.RATIO
    }

    assert units, "Modelo 303 declares ratio casillas"
    assert set(units.values()) <= {
        ModeloEditRatioUnit.PERCENT,
        ModeloEditRatioUnit.FRACTION,
        ModeloEditRatioUnit.UNDECLARED,
    }
    for casilla in revision.casillas:
        if casilla.data_type != CasillaDataType.RATIO:
            continue
        maximum = casilla.constraints.max_value if casilla.constraints is not None else None
        expected = (
            ModeloEditRatioUnit.PERCENT
            if maximum == 100
            else ModeloEditRatioUnit.FRACTION
            if maximum == 1
            else ModeloEditRatioUnit.UNDECLARED
        )
        assert units[casilla.id] is expected


def test_binding_grammar_follows_the_override_route_of_each_binding() -> None:
    revision = published_snapshot("714", filing_year=2025, period="0A").revision
    grammars = [binding_value_grammar(binding, revision=revision) for binding in revision.bindings]

    assert any(grammar.channel is ModeloEditValueChannel.DECIMAL for grammar in grammars)
    for binding, grammar in zip(revision.bindings, grammars, strict=True):
        if grammar.channel is ModeloEditValueChannel.DECIMAL:
            assert grammar.family in {
                ModeloEditValueFamily.DECIMAL,
                ModeloEditValueFamily.INTEGER,
                ModeloEditValueFamily.BOOLEAN,
            }, binding.id
