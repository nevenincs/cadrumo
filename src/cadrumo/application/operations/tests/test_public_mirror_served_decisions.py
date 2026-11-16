"""A value a canonical model decides itself crosses the mirror and is decided again on the way back."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, computed_field

from ..public_mirror import project_public_mirror, restore_public_mirror

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Row(BaseModel):
    amount: int

    @computed_field
    @property
    def doubled(self) -> int:
        return self.amount * 2


class _PublicRow(BaseModel):
    amount: int
    doubled: int


def test_a_served_decision_restores_to_the_model_that_decides_it_again() -> None:
    projected = project_public_mirror(_Row(amount=3), _Row, _PublicRow)
    assert isinstance(projected, _PublicRow)
    assert projected.doubled == 6

    restored = restore_public_mirror(_PublicRow.model_validate_json(projected.model_dump_json()), _Row, _PublicRow)

    assert restored == _Row(amount=3)


def test_a_mirror_serving_another_decision_than_its_model_decides_is_refused() -> None:
    with pytest.raises(ValueError, match="served decision"):
        restore_public_mirror(_PublicRow(amount=3, doubled=7), _Row, _PublicRow)


def test_a_public_field_that_is_neither_a_field_nor_a_decision_is_still_drift() -> None:
    class _PublicExtra(BaseModel):
        amount: int
        doubled: int
        invented: int

    with pytest.raises(ValueError, match="inventory drifted"):
        restore_public_mirror(_PublicExtra(amount=3, doubled=6, invented=1), _Row, _PublicExtra)
