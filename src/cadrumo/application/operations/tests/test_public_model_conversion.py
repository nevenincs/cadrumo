"""Contract tests for recursive public/domain scalar conversion."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

import pytest
from pydantic import BaseModel

from ..public_model_conversion import domain_model_mapping, domain_value, public_model_mapping, public_value
from ..public_scalar import PublicDecimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Kind(StrEnum):
    A = "a"


class _Leaf(BaseModel):
    amount: Decimal
    kind: _Kind


class _Root(BaseModel):
    leaves: tuple[_Leaf, ...]
    total: Decimal


def test_public_value_wraps_decimals_and_unwraps_enums_recursively() -> None:
    root = _Root(leaves=(_Leaf(amount=Decimal("1.50"), kind=_Kind.A),), total=Decimal("0"))

    assert public_value(root) == {
        "leaves": ({"amount": PublicDecimal(decimal="1.50"), "kind": "a"},),
        "total": PublicDecimal(decimal="0"),
    }


class _PublicLeaf(BaseModel):
    amount: PublicDecimal
    kind: str


class _PublicRoot(BaseModel):
    leaves: tuple[_PublicLeaf, ...]
    total: PublicDecimal


def test_domain_value_restores_decimals_losslessly() -> None:
    public = _PublicRoot(
        leaves=(_PublicLeaf(amount=PublicDecimal(decimal="1.50"), kind="a"),),
        total=PublicDecimal(decimal="0"),
    )

    restored = _Root.model_validate(domain_value(public))

    assert restored.leaves[0].amount == Decimal("1.50")
    assert str(restored.leaves[0].amount) == "1.50"
    assert restored.total == Decimal("0")


def test_domain_value_unwraps_enum_instances() -> None:
    assert domain_value((_Kind.A, PublicDecimal(decimal="2"))) == ("a", Decimal("2"))


def test_model_mappings_round_trip_through_both_directions() -> None:
    root = _Root(leaves=(_Leaf(amount=Decimal("3.10"), kind=_Kind.A),), total=Decimal("3.10"))

    public = _PublicRoot.model_validate(public_model_mapping(root))

    assert _Root.model_validate(domain_model_mapping(public)) == root
