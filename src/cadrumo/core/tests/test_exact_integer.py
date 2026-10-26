"""Exact-integer admission refuses the value-equal spellings strict mode lets through."""

from __future__ import annotations

from enum import IntEnum
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from cadrumo.core.exact_integer import EXACT_INTEGER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Reason(IntEnum):
    DONE = 64


class _Tagged(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tag: Annotated[Literal[1], EXACT_INTEGER] = 1
    reason: Annotated[_Reason, EXACT_INTEGER] = _Reason.DONE


class _Unguarded(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tag: Literal[1] = 1


def test_strict_mode_alone_admits_a_value_equal_float_for_an_integer_literal() -> None:
    """The defect the helper exists for; if pydantic stops doing this, the helper is redundant."""
    assert _Unguarded.model_validate_json('{"tag":1.0}').tag == 1


def test_the_integer_tag_and_enum_member_are_admitted() -> None:
    assert _Tagged.model_validate_json('{"tag":1,"reason":64}') == _Tagged()
    assert _Tagged.model_validate({"tag": 1, "reason": _Reason.DONE}) == _Tagged()


@pytest.mark.parametrize("spelling", ["1.0", "1e0", "true", '"1"', "null"])
def test_a_json_tag_that_only_equals_one_is_refused(spelling: str) -> None:
    with pytest.raises(ValidationError):
        _Tagged.model_validate_json(f'{{"tag":{spelling}}}')


@pytest.mark.parametrize("value", [1.0, True])
def test_a_python_tag_that_only_equals_one_is_refused(value: object) -> None:
    with pytest.raises(ValidationError):
        _Tagged.model_validate({"tag": value})


@pytest.mark.parametrize("spelling", ["64.0", "6.4e1", "true"])
def test_an_integer_enum_spelled_otherwise_is_refused(spelling: str) -> None:
    with pytest.raises(ValidationError):
        _Tagged.model_validate_json(f'{{"reason":{spelling}}}')
