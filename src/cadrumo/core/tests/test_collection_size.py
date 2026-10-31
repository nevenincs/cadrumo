"""A wire collection that needs two members states it as a check, not a schema bound."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import AfterValidator, BaseModel, ValidationError

from ..collection_size import at_least_two, exactly_two

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Members(BaseModel):
    many: Annotated[tuple[int, ...], AfterValidator(at_least_two)] = (1, 2)
    pair: Annotated[tuple[int, ...], AfterValidator(exactly_two)] = (1, 2)


@pytest.mark.parametrize("members", [(), (1,)])
def test_fewer_than_two_members_are_refused(members: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="at least two"):
        _Members(many=members)


@pytest.mark.parametrize("members", [(1, 2), (1, 2, 3, 4)])
def test_two_or_more_members_are_admitted(members: tuple[int, ...]) -> None:
    assert _Members(many=members).many == members


@pytest.mark.parametrize("members", [(), (1,), (1, 2, 3)])
def test_a_pair_of_another_size_is_refused(members: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="exactly two"):
        _Members(pair=members)


def test_a_pair_is_admitted() -> None:
    assert _Members(pair=(7, 8)).pair == (7, 8)
