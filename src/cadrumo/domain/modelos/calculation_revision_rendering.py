"""Original calculation authority retained for later immutable form presentation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Self

from pydantic import BaseModel, FieldSerializationInfo, TypeAdapter, field_serializer, model_validator

from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.schema import RegistrySnapshot


def _complete_registry_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return {name: _complete_registry_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, Mapping):
        mapping = TypeAdapter(dict[object, object]).validate_python(value)
        return {key: _complete_registry_value(item) for key, item in mapping.items()}
    if isinstance(value, tuple | list):
        items = TypeAdapter(tuple[object, ...]).validate_python(value)
        return tuple(_complete_registry_value(item) for item in items)
    return value


def _registry_payload(snapshot: RegistrySnapshot) -> dict[str, object]:
    complete = TypeAdapter(dict[str, object]).validate_python(_complete_registry_value(snapshot))
    adapter = TypeAdapter(dict[str, object])
    return adapter.validate_python(adapter.dump_python(complete, mode="json"))


class SavedRenderingLabel(BaseModel):
    """Original human wording behind one registry localization key."""

    model_config = STRICT_FROZEN_CONFIG
    key: str
    text: str


def _label_keys(value: object) -> set[str]:
    if isinstance(value, BaseModel):
        keys: set[str] = set()
        for name in type(value).model_fields:
            item = getattr(value, name)
            if name.endswith("_key") and isinstance(item, str):
                keys.add(item)
            elif name.endswith("_keys") and isinstance(item, tuple):
                items = TypeAdapter(tuple[object, ...]).validate_python(item)
                keys.update(key for key in items if isinstance(key, str))
            else:
                keys.update(_label_keys(item))
        return keys
    if isinstance(value, tuple | list):
        items = TypeAdapter(tuple[object, ...]).validate_python(value)
        sequence_keys: set[str] = set()
        for item in items:
            sequence_keys.update(_label_keys(item))
        return sequence_keys
    return set()


class CalculationRenderingSnapshot(BaseModel):
    """Digest-bound registry geometry and display rules captured under the calculation pin."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    authority_generation: Hex64Str
    registry_digest: Hex64Str
    registry_snapshot: RegistrySnapshot
    labels: tuple[SavedRenderingLabel, ...] = ()
    rendering_digest: Hex64Str

    @field_serializer("registry_snapshot")
    def _retain_registry_fields(self, value: RegistrySnapshot, info: FieldSerializationInfo) -> dict[str, object]:
        """Persist excluded localization/schema fields required to decode original geometry."""
        if info.mode == "python":
            return TypeAdapter(dict[str, object]).validate_python(_complete_registry_value(value))
        return _registry_payload(value)

    @model_validator(mode="after")
    def _registry_digest_matches(self) -> Self:
        if len({label.key for label in self.labels}) != len(self.labels):
            raise ValueError("saved rendering labels contain duplicate identities")
        if content_hash_hex(self.registry_snapshot.model_dump(mode="json")) != self.registry_digest:
            raise ValueError("saved rendering registry digest does not match its captured snapshot")
        if (
            content_hash_hex(
                {
                    "registry": _registry_payload(self.registry_snapshot),
                    "labels": [label.model_dump(mode="json") for label in self.labels],
                }
            )
            != self.rendering_digest
        ):
            raise ValueError("saved rendering metadata digest does not match its captured schema and labels")
        return self

    @classmethod
    def capture(cls, snapshot: RegistrySnapshot, *, authority_generation: Hex64Str) -> Self:
        """Capture the actual calculation snapshot; never resolve another authority generation."""
        labels = tuple(
            SavedRenderingLabel(key=key, text=text)
            for key in sorted(_label_keys(snapshot))
            for text in (lookup_translation(key, locale="es"),)
            if text is not None
        )
        return cls(
            authority_generation=authority_generation,
            registry_digest=content_hash_hex(snapshot.model_dump(mode="json")),
            registry_snapshot=snapshot,
            labels=labels,
            rendering_digest=content_hash_hex(
                {
                    "registry": _registry_payload(snapshot),
                    "labels": [label.model_dump(mode="json") for label in labels],
                }
            ),
        )
