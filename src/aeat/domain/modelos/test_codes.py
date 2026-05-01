"""Unit tests for :class:`aeat.models._codes.ModeloCode`."""

from __future__ import annotations

import pytest

from ._codes import ModeloCode

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_modelo_code_has_exactly_twenty_one_members() -> None:
    """The inventory locks exactly 21 modelos."""
    assert len(list(ModeloCode)) == 21


def test_every_value_is_three_digit_string() -> None:
    """Every value is a three-character numeric string."""
    for member in ModeloCode:
        assert len(member.value) == 3
        assert member.value.isdigit()


def test_member_name_matches_value() -> None:
    """Member name equals ``MODELO_<value>`` for every entry."""
    for member in ModeloCode:
        assert member.name == f"MODELO_{member.value}"


@pytest.mark.parametrize("raw", ["036", "037", "303", "840"])
def test_value_round_trip(raw: str) -> None:
    """``ModeloCode(str)`` round-trips through the value."""
    member = ModeloCode(raw)
    assert member.value == raw


def test_error_classes_import() -> None:
    """error classes import cleanly from the private module."""
    from ...core.errors import AeatError
    from ._errors import (
        ModeloRegistryError,
        RegistryIntegrityError,
        UnknownModeloError,
    )

    assert issubclass(ModeloRegistryError, AeatError)
    assert issubclass(UnknownModeloError, ModeloRegistryError)
    assert issubclass(RegistryIntegrityError, ModeloRegistryError)
