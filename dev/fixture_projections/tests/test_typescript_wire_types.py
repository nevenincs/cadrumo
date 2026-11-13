"""The wire-type writer marks optional exactly the fields the serialised record can leave out.

The writer reads each model's own ``exclude_if`` predicates, so a property is optional in the generated
type when, and only when, the model drops it from its JSON.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from pydantic.json_schema import models_json_schema

from ..typescript_wire_types import TypeScriptWriter, omittable_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Leaf(BaseModel):
    kept: str = "kept"
    dropped_when_none: str | None = Field(default=None, exclude_if=lambda value: value is None)


class _Root(BaseModel):
    always_with_default: tuple[str, ...] = ()
    dropped_when_empty: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)
    leaves: tuple[_Leaf, ...] = ()
    leaf: _Leaf | None = None


class _BehindAlias(BaseModel):
    dropped_when_none: str | None = Field(default=None, exclude_if=lambda value: value is None)


type _AliasedRows = tuple[_BehindAlias, ...]


class _AliasRoot(BaseModel):
    rows: _AliasedRows = ()


def _rendered() -> dict[str, str]:
    _, schema = models_json_schema([(_Root, "serialization")], ref_template="#/$defs/{model}")
    defs = schema["$defs"]
    omittable = omittable_fields([_Root], defs)
    writer = TypeScriptWriter(defs, sent_only=set(), omittable=omittable)
    return {name: writer.definition(name) for name in defs}


def test_only_fields_the_model_drops_are_optional() -> None:
    rendered = _rendered()
    assert "  dropped_when_empty?: string[];" in rendered["_Root"]
    assert "  always_with_default: string[];" in rendered["_Root"]
    assert "  leaf: Leaf | null;" in rendered["_Root"]
    assert "  dropped_when_none?: string | null;" in rendered["_Leaf"]
    assert "  kept: string;" in rendered["_Leaf"]


def test_the_wire_leaves_out_exactly_those_fields() -> None:
    wire = _Root(leaves=(_Leaf(),)).model_dump(mode="json")
    assert set(wire) == {"always_with_default", "leaves", "leaf"}
    assert wire["leaves"] == [{"kept": "kept"}]


def test_a_model_reached_only_through_a_type_alias_keeps_its_omittable_fields() -> None:
    _, schema = models_json_schema([(_AliasRoot, "serialization")], ref_template="#/$defs/{model}")
    omittable = omittable_fields([_AliasRoot], schema["$defs"])
    assert omittable.get("_BehindAlias") == frozenset({"dropped_when_none"})


def test_a_model_the_schema_does_not_define_is_refused() -> None:
    with pytest.raises(SystemExit, match="_Leaf"):
        omittable_fields([_Root], {"_Root": {}})
