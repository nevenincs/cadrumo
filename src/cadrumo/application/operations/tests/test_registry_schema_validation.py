"""Build-scoped schema reuse preserves closed contracts and model changes."""

from __future__ import annotations

from contextvars import copy_context
from copy import deepcopy
from typing import Any, ClassVar, Literal, cast, override

import pytest
from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import ModelPrivateAttr
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode

from ....core.models import STRICT_FROZEN_CONFIG
from ..registry_schema_validation import operation_schema_compilation_scope, strict_model_json_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _DeferredParent(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    child: _LaterLaxChild


class _LaterLaxChild(BaseModel):
    model_config = ConfigDict(strict=False, frozen=True, extra="forbid", defer_build=True)
    value: str


class _CountedPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    schema_generations: ClassVar[int] = 0
    value: str

    @classmethod
    @override
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> dict[str, Any]:
        cls.schema_generations += 1
        return super().model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )


@pytest.fixture
def payload_type() -> type[_CountedPayload]:
    class Payload(_CountedPayload):
        value: str = Field(description="Value", examples=["example"], min_length=1, max_length=20, pattern="^[a-z]+$")

    return Payload


def test_compilation_scope_reuses_schema_with_independent_deep_copies(payload_type: type[_CountedPayload]) -> None:
    expected = strict_model_json_schema(payload_type)
    with operation_schema_compilation_scope():
        first = strict_model_json_schema(payload_type)
        first.clear()
        second = strict_model_json_schema(payload_type)
        assert second == expected
        cast(dict[str, Any], second["properties"])["value"]["examples"].append("poison")
        assert strict_model_json_schema(payload_type) == expected
    assert payload_type.schema_generations == 4
    assert strict_model_json_schema(payload_type) == expected
    assert payload_type.schema_generations == 6


def test_nested_scopes_own_fresh_memos_and_restore_parent(payload_type: type[_CountedPayload]) -> None:
    with operation_schema_compilation_scope():
        expected = strict_model_json_schema(payload_type)
        with operation_schema_compilation_scope():
            assert strict_model_json_schema(payload_type) == expected
            assert strict_model_json_schema(payload_type) == expected
        assert strict_model_json_schema(payload_type) == expected
    assert payload_type.schema_generations == 4


def test_exception_resets_scope_and_inherited_context(payload_type: type[_CountedPayload]) -> None:
    inherited = copy_context()
    with pytest.raises(RuntimeError, match="compilation failed"), operation_schema_compilation_scope():
        strict_model_json_schema(payload_type)
        inherited = copy_context()
        raise RuntimeError("compilation failed")
    inherited.run(strict_model_json_schema, payload_type)
    strict_model_json_schema(payload_type)
    assert payload_type.schema_generations == 6


def test_decorator_creates_new_scope_on_each_build(payload_type: type[_CountedPayload]) -> None:
    @operation_schema_compilation_scope()
    def build() -> dict[str, object]:
        strict_model_json_schema(payload_type)
        return strict_model_json_schema(payload_type)

    assert build() == build()
    assert payload_type.schema_generations == 4


def test_cached_schema_still_refuses_malformed_model_graph(payload_type: type[_CountedPayload]) -> None:
    with operation_schema_compilation_scope():
        strict_model_json_schema(payload_type)
        payload_type.model_config["strict"] = False
        with pytest.raises(ValueError, match="strict=True"):
            strict_model_json_schema(payload_type)


def test_first_schema_refuses_lax_model_resolved_during_deferred_build() -> None:
    with operation_schema_compilation_scope(), pytest.raises(ValueError, match="strict=True"):
        strict_model_json_schema(_DeferredParent)


@pytest.mark.parametrize("scoped", [False, True])
def test_shared_nested_model_contract_is_rechecked_on_later_calls(scoped: bool) -> None:
    class Child(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        value: str

    class Parent(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        left: Child
        right: Child

    def validate_and_mutate() -> None:
        strict_model_json_schema(Parent)
        Child.__private_attributes__["hidden"] = ModelPrivateAttr(default=0)
        with pytest.raises(ValueError, match="private mutable state"):
            strict_model_json_schema(Parent)

    if scoped:
        with operation_schema_compilation_scope():
            validate_and_mutate()
    else:
        validate_and_mutate()


@pytest.mark.parametrize("nested", [False, True])
def test_root_or_nested_rebuild_is_refused_during_compilation(nested: bool) -> None:
    class Child(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        value: str

    class Parent(_CountedPayload):
        child: Child

    with operation_schema_compilation_scope():
        strict_model_json_schema(Parent)
        changed = Child if nested else Parent
        changed.model_rebuild(force=True)
        with pytest.raises(ValueError, match="model graph changed"):
            strict_model_json_schema(Parent)


@pytest.mark.parametrize("change", ["model_metadata", "field_metadata", "core_schema"])
def test_schema_state_edits_are_refused_during_compilation(payload_type: type[_CountedPayload], change: str) -> None:
    with operation_schema_compilation_scope():
        strict_model_json_schema(payload_type)
        if change == "model_metadata":
            payload_type.model_config["title"] = "Changed title"
        elif change == "field_metadata":
            payload_type.model_fields["value"].description = "Changed description"
        else:
            payload_type.__pydantic_core_schema__ = deepcopy(payload_type.__pydantic_core_schema__)
        with pytest.raises(ValueError, match="model graph changed"):
            strict_model_json_schema(payload_type)


def test_unclosed_schemas_are_never_memoized() -> None:
    class OpenPayload(_CountedPayload):
        payload: object

    with operation_schema_compilation_scope():
        for _ in range(2):
            with pytest.raises(ValueError, match="untyped branch"):
                strict_model_json_schema(OpenPayload)
    assert OpenPayload.schema_generations == 4


def test_scalar_subclass_metadata_remains_mutation_guarded(payload_type: type[_CountedPayload]) -> None:
    class Description(str):
        notes: list[str]

    description = Description("Value")
    description.notes = ["initial"]
    payload_type.model_fields["value"].description = description
    with operation_schema_compilation_scope():
        strict_model_json_schema(payload_type)
        description.notes.append("changed")
        with pytest.raises(ValueError, match="model graph changed"):
            strict_model_json_schema(payload_type)


def test_model_mutation_during_schema_generation_is_refused() -> None:
    class MutatingPayload(_CountedPayload):
        @classmethod
        @override
        def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
            schema = super().model_json_schema(*args, **kwargs)
            if kwargs.get("mode") == "serialization":
                cls.model_fields["value"].description = "Changed during generation"
            return schema

    with operation_schema_compilation_scope(), pytest.raises(ValueError, match="model graph changed"):
        strict_model_json_schema(MutatingPayload)
