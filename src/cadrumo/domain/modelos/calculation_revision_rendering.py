"""Original calculation authority retained for later immutable form presentation.

:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Literal, Self, TypeGuard
from weakref import ReferenceType, ref

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

from ...core.hashing import content_hash_hex, sha256_hex
from ...core.hex import Hex64Str
from ...core.i18n.render import lookup_translation
from ...core.identity.documents import TAX_ID_FORMAT_CONTEXT
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.type_guards import is_object_dict, is_object_list_or_tuple, is_object_mapping, is_object_set_or_frozenset
from ..calculations.registry.facts.atoms import TAGGED_FACT_ATOM_CONTEXT
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
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


type _LabelIdentity = tuple[tuple[str, str], ...]
type _RenderingDigestKey = tuple[_LabelIdentity, tuple[RevisionId, ...] | None]
type _RegistryKey = tuple[int, str, frozenset[str] | None]

#: Caller context that changes how a registry snapshot validates. A read that
#: supplies one is validated in full every time rather than matched to a memo.
_REGISTRY_VALIDATION_CONTEXT_KEYS: tuple[str, ...] = (TAX_ID_FORMAT_CONTEXT, TAGGED_FACT_ATOM_CONTEXT)


@dataclass(slots=True, eq=False)
class _VerifiedRegistry:
    """One validated public registry snapshot and the digests computed over it."""

    owner: ReferenceType[GovernedFactSource]
    snapshot: RegistrySnapshot
    payload_bytes: int
    registry_digest: str | None = None
    rendering_digests: dict[_RenderingDigestKey, str] = field(default_factory=dict)


class _VerifiedRegistryMemo:
    """Reuse the validation of saved registry snapshot bytes that were already validated.

    Every saved calculation revision embeds the complete public registry
    snapshot it was calculated under, and every catalogue read revalidated
    that snapshot and recomputed both digests over it. The outcome depends only
    on the snapshot bytes, the revision identities supplied for validation and
    the governed facts in scope. An entry is keyed by all three and is used
    only while that same governed-fact owner is alive.

    A hit still compares each stored digest with the value computed from the
    validated snapshot, so altered bytes or a mismatched claim are refused as
    before. Entries hold public registry content only, never taxpayer values,
    and are released with the pinned authority that owns them.

    Retention is bounded by the saved bytes it stands for. A full memo admits
    nothing new rather than evicting: a catalogue read walks its revisions in
    one order, so eviction would discard each entry just before it is needed.
    """

    def __init__(self, *, max_payload_bytes: int) -> None:
        """Start empty with a bound on the saved bytes of retained snapshots."""
        self._max_payload_bytes = max_payload_bytes
        self._entries: dict[_RegistryKey, _VerifiedRegistry] = {}
        self._by_snapshot: dict[int, _VerifiedRegistry] = {}
        self._lock = RLock()

    def validated(
        self, payload: bytes, *, context: Mapping[object, object], validate: Callable[[], RegistrySnapshot]
    ) -> RegistrySnapshot:
        """Return the :class:`RegistrySnapshot` validated from ``payload`` on a cache miss."""
        owner = governed_facts_in_scope()
        revision_ids = context.get(MODELO_REVISION_IDS_CONTEXT)
        if (
            owner is None
            or any(key in context for key in _REGISTRY_VALIDATION_CONTEXT_KEYS)
            or not (revision_ids is None or _is_revision_id_set(revision_ids))
        ):
            return validate()
        key: _RegistryKey = (id(owner), sha256_hex(payload), revision_ids)
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry.owner() is owner:
                return entry.snapshot
        snapshot = validate()
        try:
            owner_ref = ref(owner)
        except TypeError:
            return snapshot
        with self._lock:
            for stale in [item for item, held in self._entries.items() if held.owner() is None]:
                self._forget(stale)
            retained = sum(held.payload_bytes for held in self._entries.values())
            if key not in self._entries and retained + len(payload) <= self._max_payload_bytes:
                entry = _VerifiedRegistry(owner=owner_ref, snapshot=snapshot, payload_bytes=len(payload))
                self._entries[key] = entry
                self._by_snapshot[id(snapshot)] = entry
        return snapshot

    def registry_digest(self, snapshot: RegistrySnapshot, compute: Callable[[], str]) -> str:
        """Return the content digest of a :class:`RegistrySnapshot`, computing it once."""
        entry = self._entry(snapshot)
        if entry is None:
            return compute()
        if entry.registry_digest is None:
            entry.registry_digest = compute()
        return entry.registry_digest

    def rendering_digest(
        self,
        snapshot: RegistrySnapshot,
        labels: tuple[SavedRenderingLabel, ...],
        directory_ids: tuple[RevisionId, ...] | None,
        compute: Callable[[], str],
    ) -> str:
        """Return the labels and directory digest pinned to a :class:`RegistrySnapshot`."""
        entry = self._entry(snapshot)
        if entry is None:
            return compute()
        key = (tuple((label.key, label.text) for label in labels), directory_ids)
        digest = entry.rendering_digests.get(key)
        if digest is None:
            digest = compute()
            entry.rendering_digests[key] = digest
        return digest

    def _entry(self, snapshot: RegistrySnapshot) -> _VerifiedRegistry | None:
        with self._lock:
            entry = self._by_snapshot.get(id(snapshot))
        if entry is None or entry.snapshot is not snapshot or entry.owner() is None:
            return None
        return entry

    def _forget(self, key: _RegistryKey) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None and self._by_snapshot.get(id(entry.snapshot)) is entry:
            del self._by_snapshot[id(entry.snapshot)]


def _is_revision_id_set(value: object) -> TypeGuard[frozenset[str]]:
    return (
        is_object_set_or_frozenset(value)
        and isinstance(value, frozenset)
        and all(isinstance(item, str) for item in value)
    )


#: About 175 MiB resident: a validated snapshot occupies roughly 5.5 times its
#: saved JSON. This covers a year of quarterly and annual returns; one
#: catalogue read already holds all of its snapshots at once.
_VERIFIED_REGISTRY = _VerifiedRegistryMemo(max_payload_bytes=32 * 1024 * 1024)


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
        context: dict[object, object] = dict(info.context) if is_object_mapping(info.context) else {}
        if directory_ids is not None:
            identifiers = TypeAdapter(tuple[RevisionId, ...]).validate_python(directory_ids)
            context[MODELO_REVISION_IDS_CONTEXT] = frozenset(identifiers)
        if info.mode == "json":
            payload = TypeAdapter(object).dump_json(value)
            return _VERIFIED_REGISTRY.validated(
                payload,
                context=context,
                validate=lambda: RegistrySnapshot.model_validate_json(payload, context=context),
            )
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
        snapshot = self.registry_snapshot
        if (
            _VERIFIED_REGISTRY.registry_digest(snapshot, lambda: content_hash_hex(snapshot.model_dump(mode="json")))
            != self.registry_digest
        ):
            raise ValueError("saved rendering registry digest does not match its captured snapshot")
        if self.revision_directory_ids is not None and frozenset(self.revision_directory_ids) != (
            self.registry_snapshot.modelo.directory_revision_ids
        ):
            raise ValueError("saved rendering directory identities disagree with its captured snapshot")
        if (
            _VERIFIED_REGISTRY.rendering_digest(
                snapshot,
                self.labels,
                self.revision_directory_ids,
                lambda: content_hash_hex(
                    _rendering_payload(snapshot, self.labels, self.revision_directory_ids, context=info.context)
                ),
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
