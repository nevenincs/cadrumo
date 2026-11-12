"""The Modelo wire-type producer marks optional exactly the fields the serialised record can leave out.

The producer reads each model's own ``exclude_if`` predicates, so a property is optional in the generated
type when, and only when, the model drops it from its JSON.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest
from pydantic import BaseModel, Field
from pydantic.json_schema import models_json_schema

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCER = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts" / "modelo_fixtures.py"


class _Leaf(BaseModel):
    kept: str = "kept"
    dropped_when_none: str | None = Field(default=None, exclude_if=lambda value: value is None)


class _Root(BaseModel):
    always_with_default: tuple[str, ...] = ()
    dropped_when_empty: tuple[str, ...] = Field(default=(), exclude_if=lambda value: not value)
    leaves: tuple[_Leaf, ...] = ()
    leaf: _Leaf | None = None


@pytest.fixture(scope="module")
def producer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("modelo_fixtures_omittable_under_test", _PRODUCER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _rendered(producer: ModuleType) -> dict[str, str]:
    _, schema = models_json_schema([(_Root, "serialization")], ref_template="#/$defs/{model}")
    defs = schema["$defs"]
    omittable = producer.omittable_fields([_Root], defs)
    writer = producer._Writer(defs, sent_only=set(), omittable=omittable)
    return {name: writer.definition(name) for name in defs}


def test_only_fields_the_model_drops_are_optional(producer: ModuleType) -> None:
    rendered = _rendered(producer)
    assert "  dropped_when_empty?: string[];" in rendered["_Root"]
    assert "  always_with_default: string[];" in rendered["_Root"]
    assert "  leaf: Leaf | null;" in rendered["_Root"]
    assert "  dropped_when_none?: string | null;" in rendered["_Leaf"]
    assert "  kept: string;" in rendered["_Leaf"]


def test_the_wire_leaves_out_exactly_those_fields(producer: ModuleType) -> None:
    wire = _Root(leaves=(_Leaf(),)).model_dump(mode="json")
    assert set(wire) == {"always_with_default", "leaves", "leaf"}
    assert wire["leaves"] == [{"kept": "kept"}]
