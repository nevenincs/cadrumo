"""Original calculation authority retained for later immutable form presentation.

:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    FieldSerializationInfo,
    TypeAdapter,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core import SchemaSerializer

from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.type_guards import is_object_dict, is_object_list_or_tuple, is_object_mapping
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.revision_contracts import DeclaredPredecessor, NoPredecessor
from ..calculations.registry.schema import (
    MODELO_REVISION_IDS_CONTEXT,
    RegistrySnapshot,
)

_OBJECT_MAPPING_ADAPTER: TypeAdapter[dict[object, object]] = TypeAdapter(dict[object, object])
_OBJECT_SEQUENCE_ADAPTER: TypeAdapter[tuple[object, ...]] = TypeAdapter(tuple[object, ...])
_STRING_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY = "calculation_rendering_serializer"


class CalculationRenderingSerializerScope:
    """Compile public registry serialization once for one complete catalogue call.

    The caller owns this scope in its validation or serialization context. It
    retains only the public compiled schema, never a snapshot or its payload.
    """

    __slots__ = ("_serializer",)

    def __init__(self) -> None:
        """Start a fresh scope with no compiled schema or captured values."""
        self._serializer: SchemaSerializer | None = None

    def serializer(self) -> SchemaSerializer:
        """Compile lazily so catalogues without saved rendering pay no build cost."""
        if self._serializer is None:
            self._serializer = _compile_registry_serializer()
        return self._serializer


def _complete_registry_value(value: object) -> object:
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        # These types own the authored wire form accepted by their discriminator.
        return _complete_registry_value(value.model_dump(mode="python"))
    if isinstance(value, BaseModel):
        return {name: _complete_registry_value(getattr(value, name)) for name in type(value).model_fields}
    if isinstance(value, Mapping):
        mapping = _OBJECT_MAPPING_ADAPTER.validate_python(value)
        return {key: _complete_registry_value(item) for key, item in mapping.items()}
    if isinstance(value, tuple | list):
        items = _OBJECT_SEQUENCE_ADAPTER.validate_python(value)
        return tuple(_complete_registry_value(item) for item in items)
    return value


def _retain_registry_schema_fields(value: object, *, predecessor: bool = False) -> None:
    """Retain every declared field in a private copy of the registry serialization schema."""
    if is_object_dict(value):
        if value.get("type") == "model":
            model = value.get("cls")
            predecessor = model is DeclaredPredecessor or model is NoPredecessor
            if not predecessor:
                value.pop("serialization", None)
        if value.get("type") == "model-field" and not predecessor:
            value.pop("serialization_exclude", None)
            value.pop("serialization_exclude_if", None)
        for item in value.values():
            _retain_registry_schema_fields(item, predecessor=predecessor)
    elif is_object_list_or_tuple(value):
        for item in value:
            _retain_registry_schema_fields(item, predecessor=predecessor)


def _compile_registry_serializer() -> SchemaSerializer:
    """Compile a complete serializer from an independent copy of the current public schema."""
    adapter = TypeAdapter(RegistrySnapshot)
    adapter.rebuild()
    schema = deepcopy(adapter.core_schema)
    _retain_registry_schema_fields(schema)
    # The original prebuilt serializers omit presentation fields. Reusing them
    # here would silently discard the modifications on this schema copy.
    return SchemaSerializer(schema, _use_prebuilt=False)


def _registry_payload(snapshot: RegistrySnapshot, *, context: object = None) -> dict[str, object]:
    scope = context.get(CALCULATION_RENDERING_SERIALIZER_CONTEXT_KEY) if is_object_mapping(context) else None
    if isinstance(scope, CalculationRenderingSerializerScope):
        serializer = scope.serializer()
    else:
        serializer = _compile_registry_serializer()
    return _STRING_MAPPING_ADAPTER.validate_python(
        serializer.to_python(snapshot, mode="json", by_alias=False, exclude_computed_fields=True)
    )


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
                items = _OBJECT_SEQUENCE_ADAPTER.validate_python(item)
                keys.update(key for key in items if isinstance(key, str))
            else:
                keys.update(_label_keys(item))
        return keys
    if isinstance(value, tuple | list):
        items = _OBJECT_SEQUENCE_ADAPTER.validate_python(value)
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
    revision_directory_ids: tuple[RevisionId, ...] | None = Field(default=None, exclude_if=lambda value: value is None)
    registry_snapshot: RegistrySnapshot
    labels: tuple[SavedRenderingLabel, ...] = ()
    rendering_digest: Hex64Str

    @field_validator("revision_directory_ids")
    @classmethod
    def _require_canonical_directory_ids(cls, value: tuple[RevisionId, ...] | None) -> tuple[RevisionId, ...] | None:
        if value is not None and (not value or tuple(sorted(set(value))) != value):
            raise ValueError("saved rendering directory identities must be sorted, unique and nonempty")
        return value

    @field_validator("registry_snapshot", mode="before")
    @classmethod
    def _restore_directory_validation(cls, value: object, info: ValidationInfo) -> object:
        directory_ids = info.data.get("revision_directory_ids")
        if isinstance(value, RegistrySnapshot):
            return value
        context = dict(info.context) if is_object_mapping(info.context) else {}
        if directory_ids is not None:
            identifiers = TypeAdapter(tuple[RevisionId, ...]).validate_python(directory_ids)
            context[MODELO_REVISION_IDS_CONTEXT] = frozenset(identifiers)
        if info.mode == "json":
            payload = TypeAdapter(object).dump_json(value)
            return RegistrySnapshot.model_validate_json(payload, context=context)
        return RegistrySnapshot.model_validate(value, context=context)

    @field_serializer("registry_snapshot")
    def _retain_registry_fields(self, value: RegistrySnapshot, info: FieldSerializationInfo) -> dict[str, object]:
        """Persist excluded localization/schema fields required to decode original geometry."""
        if info.mode == "python":
            return _STRING_MAPPING_ADAPTER.validate_python(_complete_registry_value(value))
        return _registry_payload(value, context=info.context)

    @model_validator(mode="after")
    def _registry_digest_matches(self, info: ValidationInfo) -> Self:
        if len({label.key for label in self.labels}) != len(self.labels):
            raise ValueError("saved rendering labels contain duplicate identities")
        if content_hash_hex(self.registry_snapshot.model_dump(mode="json")) != self.registry_digest:
            raise ValueError("saved rendering registry digest does not match its captured snapshot")
        if self.revision_directory_ids is not None and frozenset(self.revision_directory_ids) != (
            self.registry_snapshot.modelo.directory_revision_ids
        ):
            raise ValueError("saved rendering directory identities disagree with its captured snapshot")
        if (
            content_hash_hex(
                _rendering_payload(
                    self.registry_snapshot, self.labels, self.revision_directory_ids, context=info.context
                )
            )
            != self.rendering_digest
        ):
            raise ValueError("saved rendering metadata digest does not match its captured schema and labels")
        return self

    @classmethod
    def capture(cls, snapshot: RegistrySnapshot, *, authority_generation: Hex64Str) -> Self:
        """Capture the actual calculation snapshot; never resolve another authority generation.

        The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
        the registry declarations used by the projection.
        """
        labels = tuple(
            SavedRenderingLabel(key=key, text=text)
            for key in sorted(_label_keys(snapshot))
            for text in (lookup_translation(key, locale="es"),)
            if text is not None
        )
        directory_ids = tuple(sorted(snapshot.modelo.directory_revision_ids))
        return cls(
            authority_generation=authority_generation,
            registry_digest=content_hash_hex(snapshot.model_dump(mode="json")),
            registry_snapshot=snapshot,
            revision_directory_ids=directory_ids,
            labels=labels,
            rendering_digest=content_hash_hex(_rendering_payload(snapshot, labels, directory_ids)),
        )


def _rendering_payload(
    snapshot: RegistrySnapshot,
    labels: tuple[SavedRenderingLabel, ...],
    directory_ids: tuple[RevisionId, ...] | None,
    *,
    context: object = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "registry": _registry_payload(snapshot, context=context),
        "labels": [label.model_dump(mode="json") for label in labels],
    }
    if directory_ids is not None:
        payload["revision_directory_ids"] = directory_ids
    return payload
