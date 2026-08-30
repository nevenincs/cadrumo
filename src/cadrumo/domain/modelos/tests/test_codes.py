"""Unit tests for :class:`cadrumo.domain.modelos.codes.ModeloCode`."""

from __future__ import annotations

import pytest

from ..codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_value_round_trip() -> None:
    for raw in ("036", "037", "130", "303", "840"):
        member = ModeloCode(raw)

        assert member == raw
        assert str(member) == raw


def test_invalid_value_rejected() -> None:
    for raw in ("", "13", "1300", "abc", "13A"):
        with pytest.raises(ValueError, match=r"modelo code|three-digit"):
            ModeloCode(raw)


def test_modelo_code_is_not_a_support_catalogue() -> None:
    assert not hasattr(ModeloCode, "MODELO_130")
