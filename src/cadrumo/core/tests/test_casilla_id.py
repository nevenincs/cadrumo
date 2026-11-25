"""The casilla-id check admits exactly the tokens the ``CasillaId`` type admits."""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import TypeAdapter, ValidationError

from ..casilla_id import CasillaId, validated_casilla_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TYPE: TypeAdapter[CasillaId] = TypeAdapter(CasillaId)


class _Box(StrEnum):
    BASE = "iva.base-imponible"


_CANDIDATES: tuple[object, ...] = (
    "0001",
    "a",
    "iva.base-imponible",
    "renta:1380_x",
    "Z" * 64,
    "Z" * 65,
    "",
    ".0001",
    "-a",
    "a b",
    "a\n",
    "\na",
    "a/b",
    "é01",
    "٣",
    "a\u200b",
    _Box.BASE,
    1380,
    None,
    b"0001",
)


def _admitted_by_type(candidate: object) -> str | None:
    if not isinstance(candidate, str):
        return None
    try:
        return _TYPE.validate_python(candidate)
    except ValidationError:
        return None


def _admitted_by_check(candidate: object) -> str | None:
    try:
        return validated_casilla_id(candidate)
    except ValueError:
        return None


@pytest.mark.parametrize("candidate", _CANDIDATES, ids=repr)
def test_the_check_admits_and_refuses_exactly_what_the_type_does(candidate: object) -> None:
    admitted = _admitted_by_check(candidate)

    assert admitted == _admitted_by_type(candidate)
    assert admitted is None or type(admitted) is str


def test_a_refusal_names_its_surface() -> None:
    with pytest.raises(ValueError, match=r"casilla_values 'a b' is not a canonical casilla.id"):
        validated_casilla_id("a b", surface="casilla_values")
