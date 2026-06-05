"""Unit tests for :class:`aeat.domain.modelos._codes.ModeloCode`."""

from __future__ import annotations

import pytest

from .._codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("raw", ["036", "037", "130", "303", "840"])
def test_value_round_trip(raw: str) -> None:
    member = ModeloCode(raw)

    assert member == raw
    assert str(member) == raw


@pytest.mark.parametrize("raw", ["", "13", "1300", "abc", "13A"])
def test_invalid_value_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match=r"modelo code|three-digit"):
        ModeloCode(raw)


def test_modelo_code_is_not_a_support_catalogue() -> None:
    assert not hasattr(ModeloCode, "MODELO_130")
