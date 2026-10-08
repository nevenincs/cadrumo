"""Definition naming optimization preserves the default Pydantic schema exactly."""

from __future__ import annotations

from decimal import Decimal
from functools import wraps
from typing import Annotated, ClassVar, Literal, TypeAliasType, override

import pytest
from pydantic import BaseModel, Field, create_model
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode

from ....core.hashing import canonical_json_bytes
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.type_guards import is_str_keyed_dict
from ..registry_schema_validation import _UnambiguousDefinitionsSchemaGenerator, strict_model_json_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

type _Label = Annotated[str, Field(min_length=1)]


class _SharedAliases(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    first: _Label = Field(alias="public_first")
    second: tuple[_Label, ...]


class _Recursive(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    label: str
    children: tuple[_Recursive, ...] = ()


class _Box[T](BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    value: T


class _GenericUses(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    text: _Box[str]
    number: _Box[int]


def _colliding_models(*, equivalent: bool) -> type[BaseModel]:
    left = create_model("Entry", __module__="first", __config__=STRICT_FROZEN_CONFIG, value=(str, ...))
    right = create_model(
        "Entry", __module__="second", __config__=STRICT_FROZEN_CONFIG, value=(str if equivalent else int, ...)
    )
    return create_model("Collision", __config__=STRICT_FROZEN_CONFIG, left=(left, ...), right=(right, ...))


def _colliding_aliases() -> type[BaseModel]:
    def text_alias() -> TypeAliasType:
        type Value = str
        return Value

    def number_alias() -> TypeAliasType:
        type Value = int
        return Value

    left, right = text_alias(), number_alias()
    return create_model("AliasCollision", __config__=STRICT_FROZEN_CONFIG, left=(left, ...), right=(right, ...))


def _same_name_parent() -> type[BaseModel]:
    child = create_model("Entry", __module__="child", __config__=STRICT_FROZEN_CONFIG, value=(str, ...))
    return create_model("Entry", __module__="parent", __config__=STRICT_FROZEN_CONFIG, child=(child, ...))


@pytest.mark.parametrize(
    "model_type",
    [
        _SharedAliases,
        _Recursive,
        _GenericUses,
        _colliding_models(equivalent=False),
        _colliding_models(equivalent=True),
        _colliding_aliases(),
        _same_name_parent(),
    ],
)
@pytest.mark.parametrize("mode", ["validation", "serialization"])
@pytest.mark.parametrize("ref_template", ["#/$defs/{model}", "#/components/schemas/{model}"])
@pytest.mark.parametrize("by_alias", [False, True])
def test_default_definition_names_and_schema_bytes_are_preserved(
    model_type: type[BaseModel], mode: JsonSchemaMode, ref_template: str, by_alias: bool
) -> None:
    expected = model_type.model_json_schema(mode=mode, ref_template=ref_template, by_alias=by_alias)
    actual = model_type.model_json_schema(
        mode=mode, ref_template=ref_template, by_alias=by_alias, schema_generator=_UnambiguousDefinitionsSchemaGenerator
    )
    assert actual == expected
    assert canonical_json_bytes(actual) == canonical_json_bytes(expected)


@pytest.mark.parametrize("equivalent", [False, True])
def test_ambiguous_names_delegate_to_original_deduplication(monkeypatch: pytest.MonkeyPatch, equivalent: bool) -> None:
    original = GenerateJsonSchema._build_definitions_remapping
    calls = 0

    def remap(generator: GenerateJsonSchema):
        nonlocal calls
        calls += 1
        return original(generator)

    monkeypatch.setattr(GenerateJsonSchema, "_build_definitions_remapping", remap)
    strict_model_json_schema(_colliding_models(equivalent=equivalent))
    assert calls == 2


def test_mode_dependent_decimal_shapes_are_still_refused() -> None:
    class DecimalPayload(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        amount: Decimal

    with pytest.raises(ValueError, match="validation and serialization shapes must be identical"):
        strict_model_json_schema(DecimalPayload)


def test_decorated_schema_method_remains_authoritative() -> None:
    class DecoratedPayload(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        calls: ClassVar[int] = 0
        value: str

        @classmethod
        @override
        @wraps(BaseModel.model_json_schema)
        def model_json_schema(
            cls,
            by_alias: bool = True,
            ref_template: str = "#/$defs/{model}",
            schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
            mode: JsonSchemaMode = "validation",
            *,
            union_format: Literal["any_of", "primitive_type_array"] = "any_of",
        ) -> dict[str, object]:
            assert schema_generator is GenerateJsonSchema
            cls.calls += 1
            schema = super().model_json_schema(
                by_alias=by_alias,
                ref_template=ref_template,
                schema_generator=schema_generator,
                mode=mode,
                union_format=union_format,
            )
            schema["description"] = "Authoritative method"
            assert is_str_keyed_dict(schema)
            return schema

    assert strict_model_json_schema(DecoratedPayload)["description"] == "Authoritative method"
    assert DecoratedPayload.calls == 2
