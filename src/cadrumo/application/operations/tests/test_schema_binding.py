"""Binding construction retains exact identities and live model admission."""

from __future__ import annotations

from contextlib import nullcontext
from typing import ClassVar

import pytest
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from ....core.models import STRICT_FROZEN_CONFIG
from .. import registry, schema_identity
from ..registry import OperationSchemaBindingV1, _SchemaBindingIdentitySeed
from ..registry_schema_validation import operation_schema_compilation_scope, strict_model_json_schema
from ..schema_identity import OperationSchemaIdentityV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class Payload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str


class BindingHolder(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    binding: OperationSchemaBindingV1


def test_factory_compiles_once_and_preserves_public_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = OperationSchemaIdentityV1.from_model(schema_id="test.payload", schema_version=1, model_type=Payload)
    compilations: list[type[BaseModel]] = []

    def compile_model(model_type: type[BaseModel]) -> dict[str, object]:
        compilations.append(model_type)
        return strict_model_json_schema(model_type)

    monkeypatch.setattr(registry, "strict_model_json_schema", compile_model)
    monkeypatch.setattr(schema_identity, "strict_model_json_schema", compile_model)

    binding = OperationSchemaBindingV1.bind(schema_id="test.payload", schema_version=1, model_type=Payload)

    assert compilations == [Payload]
    assert binding.identity.model_dump(mode="json") == expected.model_dump(mode="json")
    assert binding.model_dump() == {"identity": expected.model_dump(), "model_type": Payload}
    with pytest.raises(ValidationError, match="frozen"):
        binding.identity.schema_version = 2


def test_arbitrary_constructor_refuses_forged_fingerprint() -> None:
    forged = OperationSchemaIdentityV1(schema_id="test.payload", schema_version=1, schema_fingerprint="0" * 64)

    with pytest.raises(ValidationError, match="fingerprint does not match"):
        OperationSchemaBindingV1(identity=forged, model_type=Payload)


def test_private_seed_subclass_is_not_admitted_as_derivation_metadata() -> None:
    class SeedSubclass(_SchemaBindingIdentitySeed):
        pass

    with pytest.raises(ValidationError):
        OperationSchemaBindingV1.model_validate(
            {
                "model_type": Payload,
                "identity": SeedSubclass(schema_id="test.payload", schema_version=1),
            }
        )


@pytest.mark.parametrize(
    ("schema_id", "schema_version"),
    [("invalid", 1), ("test.payload", 0), ("test.payload", True), ("test.payload", "1")],
)
def test_factory_keeps_schema_metadata_validation(schema_id: str, schema_version: int) -> None:
    with pytest.raises(ValidationError):
        OperationSchemaBindingV1.bind(
            schema_id=schema_id,
            schema_version=schema_version,
            model_type=Payload,
        )


@pytest.mark.parametrize("scoped", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_reused_binding_rechecks_current_nested_model(scoped: bool, nested: bool) -> None:
    class Child(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        value: str

    class Parent(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        child: Child

    with operation_schema_compilation_scope() if scoped else nullcontext():
        binding = OperationSchemaBindingV1.bind(schema_id="test.parent", schema_version=1, model_type=Parent)
        Child.model_config["strict"] = False

        with pytest.raises(ValidationError, match="strict=True"):
            if nested:
                BindingHolder(binding=binding)
            else:
                OperationSchemaBindingV1.model_validate(binding)


def test_supplied_identity_validation_runs_before_current_model_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    class Child(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        value: str

    class Parent(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        child: Child

    class MutatingIdentity(OperationSchemaIdentityV1):
        mutate: ClassVar[bool] = False

        @model_validator(mode="after")
        def mutate_model(self) -> MutatingIdentity:
            if self.mutate:
                Child.model_config["strict"] = False
            return self

    class ValidatingBinding(OperationSchemaBindingV1):
        identity: MutatingIdentity

    identity = MutatingIdentity.from_model(schema_id="test.parent", schema_version=1, model_type=Parent)
    MutatingIdentity.mutate = True
    compiled_strict_states: list[bool | None] = []

    def compile_model(model_type: type[BaseModel]) -> dict[str, object]:
        compiled_strict_states.append(Child.model_config.get("strict"))
        return strict_model_json_schema(model_type)

    monkeypatch.setattr(registry, "strict_model_json_schema", compile_model)

    with pytest.raises(ValidationError, match="strict=True"):
        ValidatingBinding(identity=identity, model_type=Parent)
    assert compiled_strict_states == [False]


def test_binding_subclass_field_validation_cannot_change_model_after_admission() -> None:
    class Child(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        value: str

    class Parent(BaseModel):
        model_config = STRICT_FROZEN_CONFIG
        child: Child

    class MutatingBinding(OperationSchemaBindingV1):
        @field_validator("identity")
        @classmethod
        def mutate_model(cls, identity: OperationSchemaIdentityV1) -> OperationSchemaIdentityV1:
            Child.model_config["strict"] = False
            return identity

    with pytest.raises(ValidationError, match="strict=True"):
        MutatingBinding.bind(schema_id="test.parent", schema_version=1, model_type=Parent)
