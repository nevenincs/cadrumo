"""Behavioral contracts for the shareable read-only mapping and its model annotation."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, MutableMapping
from decimal import Decimal
from typing import Annotated, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import JsonSchemaMode

from ..frozen_mapping import FROZEN_MAPPING, FrozenMapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _Leaf(BaseModel):
    model_config = _STRICT_FROZEN

    amount: Decimal
    note: str = Field(default="", exclude=True)


class _Frozen(BaseModel):
    model_config = _STRICT_FROZEN

    leaves: Annotated[Mapping[str, _Leaf], FROZEN_MAPPING]
    codes: Annotated[Mapping[str, int], FROZEN_MAPPING] | None = None
    defaulted: Annotated[Mapping[str, int], FROZEN_MAPPING] = Field(default_factory=dict, validate_default=True)


class _Plain(BaseModel):
    """The same fields without the annotation: the shape the frozen form must reproduce."""

    model_config = _STRICT_FROZEN

    leaves: Mapping[str, _Leaf]
    codes: Mapping[str, int] | None = None
    defaulted: Mapping[str, int] = Field(default_factory=dict)


def _pair() -> tuple[_Frozen, _Plain]:
    fields: dict[str, object] = {"leaves": {"a": _Leaf(amount=Decimal("1.50"), note="kept out")}, "codes": {"z": 2}}
    return _Frozen.model_validate(fields), _Plain.model_validate(fields)


def test_a_validated_field_and_its_default_refuse_mutation() -> None:
    """Neither a supplied mapping nor a defaulted one can be changed through the model."""
    frozen, _ = _pair()

    for mapping in (frozen.leaves, frozen.codes, frozen.defaulted):
        assert isinstance(mapping, FrozenMapping)
        with pytest.raises(TypeError):
            cast("MutableMapping[str, object]", mapping)["injected"] = 1
    storage = "_items"
    with pytest.raises(AttributeError):
        setattr(frozen.leaves, storage, {})


def test_the_caller_mapping_is_copied_not_aliased() -> None:
    """Changing the dict a model was built from cannot reach the model."""
    source = {"z": 2}
    frozen = _Frozen(leaves={}, codes=source)

    source["injected"] = 3

    assert dict(frozen.codes or {}) == {"z": 2}


@pytest.mark.parametrize(
    "dump",
    [
        lambda model: model.model_dump(),
        lambda model: model.model_dump(mode="json"),
        lambda model: model.model_dump(exclude={"leaves": {"a": {"amount"}}}),
        lambda model: model.model_dump(include={"codes"}),
        lambda model: model.model_dump(exclude_none=True),
        lambda model: model.model_dump_json(),
    ],
)
def test_serialisation_matches_the_plain_mapping_field(dump: Callable[[BaseModel], object]) -> None:
    """The annotation changes mutability only: dumps, nested include/exclude and JSON are unchanged."""
    frozen, plain = _pair()

    assert dump(frozen) == dump(plain)


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_json_schema_matches_the_plain_mapping_field(mode: JsonSchemaMode) -> None:
    """Generated schemas cannot tell the frozen field from the plain one."""
    frozen_schema = _Frozen.model_json_schema(mode=mode)
    plain_schema = _Plain.model_json_schema(mode=mode)

    for structural_key in ("properties", "required", "$defs"):
        assert frozen_schema[structural_key] == plain_schema[structural_key]


def test_json_round_trip_restores_an_equal_frozen_model() -> None:
    """A dumped model validates back to an equal model whose mappings are frozen again."""
    frozen, _ = _pair()

    restored = _Frozen.model_validate_json(frozen.model_dump_json())

    assert restored.leaves == {"a": _Leaf(amount=Decimal("1.50"))}
    assert isinstance(restored.leaves, FrozenMapping)


def test_copies_share_the_mapping_and_its_reduction_rebuilds_it() -> None:
    """A deep model copy shares the immutable mapping; the pickle reduction rebuilds an equal frozen one."""
    frozen, _ = _pair()

    deep = frozen.model_copy(deep=True)
    leaves = frozen.leaves
    assert isinstance(leaves, FrozenMapping)
    constructor, arguments = leaves.__reduce__()
    rebuilt = constructor(*arguments)

    assert deep.leaves is frozen.leaves
    assert copy.copy(frozen.leaves) is frozen.leaves
    assert rebuilt == frozen.leaves
    assert isinstance(rebuilt, FrozenMapping)
    assert rebuilt is not frozen.leaves
