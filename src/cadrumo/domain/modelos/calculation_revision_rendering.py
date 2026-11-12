"""Original calculation authority retained for later immutable form presentation.

:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial
from threading import RLock
from typing import Annotated, Final, Literal, Self, TypeGuard
from weakref import ReferenceType, ref

from pydantic import (
    BaseModel,
    Field,
    FieldSerializationInfo,
    GetCoreSchemaHandler,
    GetPydanticSchema,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic_core import CoreSchema, SchemaSerializer, core_schema

from ...core.hashing import content_hash_hex, sha256_hex
from ...core.hex import Hex64Str
from ...core.i18n.render import lookup_translation
from ...core.identity.documents import TAX_ID_FORMAT_CONTEXT
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.type_guards import is_object_dict, is_object_list_or_tuple, is_object_mapping, is_object_set_or_frozenset
from ..calculations.registry.facts.atoms import TAGGED_FACT_ATOM_CONTEXT
from ..calculations.registry.field_absence import absent_when_none, later_absent_when_none
from ..calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ..calculations.registry.ids import RevisionId
from ..calculations.registry.revision_contracts import DeclaredPredecessor, NoPredecessor
from ..calculations.registry.schema import (
    MODELO_REVISION_IDS_CONTEXT,
    RegistrySnapshot,
)
from ..calculations.registry.schema_formula import bracket_kind_is_default

_OBJECT_MAPPING_ADAPTER: TypeAdapter[dict[object, object]] = TypeAdapter(dict[object, object])
_OBJECT_SEQUENCE_ADAPTER: TypeAdapter[tuple[object, ...]] = TypeAdapter(tuple[object, ...])
_STRING_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

_REVISION_ID_SEQUENCE_ADAPTER: TypeAdapter[tuple[RevisionId, ...]] = TypeAdapter(tuple[RevisionId, ...])
_SAVED_JSON_ADAPTER: TypeAdapter[object] = TypeAdapter(object)
# The exclusions of fields added after snapshots were saved: each leaves its field out at the
# value an earlier snapshot implies, so that snapshot's dumps and digests are unchanged.
_LATER_FIELD_EXCLUSIONS: Final = (absent_when_none, later_absent_when_none, bracket_kind_is_default)


def _complete_registry_value(value: object) -> object:
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        # These types own the authored wire form accepted by their discriminator.
        return _complete_registry_value(value.model_dump(mode="python"))
    if isinstance(value, BaseModel):
        return _complete_model_fields(value)
    if isinstance(value, Mapping):
        mapping = _OBJECT_MAPPING_ADAPTER.validate_python(value)
        return {key: _complete_registry_value(item) for key, item in mapping.items()}
    if isinstance(value, tuple | list):
        items = _OBJECT_SEQUENCE_ADAPTER.validate_python(value)
        return tuple(_complete_registry_value(item) for item in items)
    return value


def _complete_model_fields(value: BaseModel) -> dict[str, object]:
    completed: dict[str, object] = {}
    for name, model_field in type(value).model_fields.items():
        item = getattr(value, name)
        if model_field.exclude_if in _LATER_FIELD_EXCLUSIONS and model_field.exclude_if(item):
            continue
        completed[name] = _complete_registry_value(item)
    return completed


def retain_registry_schema_fields(value: object, *, predecessor: bool = False) -> None:
    """Retain every declared field in a private copy of the registry serialization schema."""
    if is_object_dict(value):
        predecessor = _retain_schema_node_fields(value, predecessor=predecessor)
        for item in value.values():
            retain_registry_schema_fields(item, predecessor=predecessor)
    elif is_object_list_or_tuple(value):
        for item in value:
            retain_registry_schema_fields(item, predecessor=predecessor)


def _retain_schema_node_fields(node: dict[object, object], *, predecessor: bool) -> bool:
    """Drop one schema node's field exclusions and return the predecessor scope for its children."""
    if node.get("type") == "model":
        model = node.get("cls")
        predecessor = model is DeclaredPredecessor or model is NoPredecessor
        if not predecessor:
            node.pop("serialization", None)
    if node.get("type") == "model-field" and not predecessor:
        node.pop("serialization_exclude", None)
        # A field added after snapshots were saved stays out while absent or at
        # its default, so an earlier snapshot's complete payload is unchanged.
        if node.get("serialization_exclude_if") not in _LATER_FIELD_EXCLUSIONS:
            node.pop("serialization_exclude_if", None)
    return predecessor


def write_absent_fields_as_null(value: object) -> None:
    """Drop only the ``absent_when_none`` exclusion from a private copy of a serialization schema.

    Builds between the declaration of such a field and its exclusion dumped it as
    ``null``, so a snapshot they saved is bound by digests of that form.
    """
    if is_object_dict(value):
        if value.get("type") == "model-field" and value.get("serialization_exclude_if") is absent_when_none:
            value.pop("serialization_exclude_if", None)
        for item in value.values():
            write_absent_fields_as_null(item)
    elif is_object_list_or_tuple(value):
        for item in value:
            write_absent_fields_as_null(item)


def _public_schema_copy() -> CoreSchema:
    adapter = TypeAdapter(RegistrySnapshot)
    adapter.rebuild()
    return deepcopy(adapter.core_schema)


def compile_registry_serializer() -> SchemaSerializer:
    """Compile a complete serializer from an independent copy of the current public schema."""
    schema = _public_schema_copy()
    retain_registry_schema_fields(schema)
    # The original prebuilt serializers omit presentation fields. Reusing them
    # here would silently discard the modifications on this schema copy.
    return SchemaSerializer(schema, _use_prebuilt=False)


def compile_absent_as_null_serializer(*, complete: bool) -> SchemaSerializer:
    """Compile the dump of a build that wrote a field excluded only while absent as ``null``.

    ``complete`` keeps every declared field, as a saved rendering's metadata
    digest covers it; otherwise the ordinary dump's other exclusions hold.
    """
    schema = _public_schema_copy()
    if complete:
        retain_registry_schema_fields(schema)
    write_absent_fields_as_null(schema)
    # The original prebuilt serializers omit presentation fields. Reusing them
    # here would silently discard the modifications on this schema copy.
    return SchemaSerializer(schema, _use_prebuilt=False)


class RegistrySerializerMemo:
    """Hold the complete serializer of the schema :class:`RegistrySnapshot` currently declares.

    The serializer is derived from the declared model alone and retains no
    snapshot, so no authority generation or taxpayer value can reach it. A model
    rebuild replaces the core schema object and so compiles again.
    """

    __slots__ = ("_compile", "_compiled_for", "_serializer")

    def __init__(self, compile_serializer: Callable[[], SchemaSerializer] | None = None) -> None:
        """Start with nothing compiled, so reads without a saved rendering pay no build cost.

        Without ``compile_serializer`` the memo holds the complete serializer.
        """
        self._compile = compile_serializer
        self._compiled_for: object = None
        self._serializer: SchemaSerializer | None = None

    def serializer(self) -> SchemaSerializer:
        """Return the serializer of the current schema, compiling it on a change."""
        serializer = self._serializer
        if serializer is None or self._compiled_for is not RegistrySnapshot.__pydantic_core_schema__:
            serializer = compile_registry_serializer() if self._compile is None else self._compile()
            self._compiled_for = RegistrySnapshot.__pydantic_core_schema__
            self._serializer = serializer
        return serializer


REGISTRY_SERIALIZER = RegistrySerializerMemo()
#: The ordinary and complete dumps as builds that wrote absent fields as
#: ``null`` produced them; read only to verify a snapshot one of them saved.
_ABSENT_AS_NULL_DUMP = RegistrySerializerMemo(partial(compile_absent_as_null_serializer, complete=False))
_ABSENT_AS_NULL_COMPLETE = RegistrySerializerMemo(partial(compile_absent_as_null_serializer, complete=True))


def registry_payload(snapshot: RegistrySnapshot) -> dict[str, object]:
    """Serialize a registry snapshot to a JSON-mode mapping.

    ``snapshot`` is a :class:`RegistrySnapshot`. Each call returns a mapping of
    its own; the serialization is computed once per live snapshot object and
    serializer, and later calls rebuild an equal mapping from it.
    """
    serializer = REGISTRY_SERIALIZER.serializer()
    return VERIFIED_REGISTRY.registry_payload(
        snapshot,
        serializer,
        lambda: _STRING_MAPPING_ADAPTER.validate_python(
            serializer.to_python(snapshot, mode="json", by_alias=False, exclude_computed_fields=True)
        ),
    )


def _reproducible_json(payload: dict[str, object]) -> str | None:
    """Encode ``payload`` when decoding the text gives back an equal mapping, else ``None``.

    A JSON-mode serialization holds only JSON values, but anything the text
    would not give back unchanged -- a tuple, a non-finite number -- keeps the
    payload out of the memo rather than altering what a later call returns.
    """
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    return encoded if json.loads(encoded) == payload else None


type _LabelIdentity = tuple[tuple[str, str], ...]
type _RenderingDigestKey = tuple[_LabelIdentity, tuple[RevisionId, ...] | None]
type _RegistryKey = tuple[int, str, frozenset[str] | None]

#: Caller context that changes how a registry snapshot validates. A read that
#: supplies one is validated in full every time rather than matched to a memo.
_REGISTRY_VALIDATION_CONTEXT_KEYS: tuple[str, ...] = (TAX_ID_FORMAT_CONTEXT, TAGGED_FACT_ATOM_CONTEXT)


@dataclass(slots=True, eq=False)
class _VerifiedRegistry:
    """One validated public registry snapshot and the size of the bytes it stands for."""

    owner: ReferenceType[GovernedFactSource]
    snapshot: RegistrySnapshot
    payload_bytes: int


@dataclass(slots=True, eq=False)
class _SnapshotDigests:
    """Digests computed over one live, frozen snapshot object."""

    snapshot: ReferenceType[RegistrySnapshot]
    registry_digest: str | None = None
    rendering_digests: dict[_RenderingDigestKey, str] = field(default_factory=dict)
    registry_payload: tuple[SchemaSerializer, str] | None = None


class VerifiedRegistryMemo:
    """Reuse the validation of saved registry snapshot bytes that were already validated.

    Every saved calculation revision carries the complete public registry
    snapshot it was calculated under: embedded whole in a revision stored
    before bodies were stored once per rendering digest, and supplied from
    that one stored body afterwards. Without this memo a read revalidated each
    saved snapshot and recomputed both digests over it. The outcome depends only
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

    Digests belong to the snapshot object they were computed over, whichever way
    it was obtained, and end with it. A calculation captures and then revalidates
    the same object several times; a saved claim is still compared with them on
    every read, and any other bytes produce another object.
    """

    def __init__(self, *, max_payload_bytes: int) -> None:
        """Start empty with a bound on the saved bytes of retained snapshots."""
        self._max_payload_bytes = max_payload_bytes
        self._entries: dict[_RegistryKey, _VerifiedRegistry] = {}
        self._digests: dict[int, _SnapshotDigests] = {}
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
        self._retain_validated(key, owner_ref, snapshot, len(payload))
        return snapshot

    def _retain_validated(
        self,
        key: _RegistryKey,
        owner: ReferenceType[GovernedFactSource],
        snapshot: RegistrySnapshot,
        payload_bytes: int,
    ) -> None:
        """Evict dead owners and admit one validated snapshot within the shared byte bound."""
        with self._lock:
            for stale in [item for item, held in self._entries.items() if held.owner() is None]:
                self._forget(stale)
            retained = sum(held.payload_bytes for held in self._entries.values())
            if key not in self._entries and retained + payload_bytes <= self._max_payload_bytes:
                self._entries[key] = _VerifiedRegistry(owner=owner, snapshot=snapshot, payload_bytes=payload_bytes)

    def registry_digest(self, snapshot: RegistrySnapshot, compute: Callable[[], str]) -> str:
        """Return the content digest of a :class:`RegistrySnapshot`, computing it once."""
        digests = self._digests_of(snapshot)
        if digests is None:
            return compute()
        if digests.registry_digest is None:
            digests.registry_digest = compute()
        return digests.registry_digest

    def rendering_digest(
        self,
        snapshot: RegistrySnapshot,
        labels: tuple[SavedRenderingLabel, ...],
        directory_ids: tuple[RevisionId, ...] | None,
        compute: Callable[[], str],
    ) -> str:
        """Return the labels and directory digest pinned to a :class:`RegistrySnapshot`."""
        digests = self._digests_of(snapshot)
        if digests is None:
            return compute()
        key = (tuple((label.key, label.text) for label in labels), directory_ids)
        digest = digests.rendering_digests.get(key)
        if digest is None:
            digest = compute()
            if len(digests.rendering_digests) < _MAX_RENDERING_DIGESTS_PER_SNAPSHOT:
                digests.rendering_digests[key] = digest
        return digest

    def registry_payload(
        self,
        snapshot: RegistrySnapshot,
        serializer: SchemaSerializer,
        compute: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        """Return a fresh JSON-mode mapping of a :class:`RegistrySnapshot` under ``serializer``.

        Every saved revision of a declaration carries the same snapshot, and
        each serialization of it within one operation would traverse it again. The serialization is kept
        as JSON text for the snapshot object and the serializer it came from, and
        each later call decodes its own mapping from that text, so no caller
        shares or can alter what another receives.
        """
        digests = self._digests_of(snapshot)
        if digests is None:
            return compute()
        held = digests.registry_payload
        if held is not None and held[0] is serializer:
            return _STRING_MAPPING_ADAPTER.validate_python(json.loads(held[1]))
        payload = compute()
        encoded = _reproducible_json(payload)
        if encoded is not None:
            digests.registry_payload = (serializer, encoded)
        return payload

    def _digests_of(self, snapshot: RegistrySnapshot) -> _SnapshotDigests | None:
        key = id(snapshot)
        with self._lock:
            digests = self._digests.get(key)
            if digests is not None and digests.snapshot() is snapshot:
                return digests
            try:
                reference = ref(snapshot, partial(self._release_digests, key))
            except TypeError:
                return None
            digests = _SnapshotDigests(snapshot=reference)
            self._digests[key] = digests
            return digests

    def _release_digests(self, key: int, reference: ReferenceType[RegistrySnapshot]) -> None:
        # Runs inside garbage collection on any thread, so it must not wait for the lock.
        held = self._digests.get(key)
        if held is not None and held.snapshot is reference:
            self._digests.pop(key, None)

    def _forget(self, key: _RegistryKey) -> None:
        self._entries.pop(key, None)


def _is_revision_id_set(value: object) -> TypeGuard[frozenset[str]]:
    return (
        is_object_set_or_frozenset(value)
        and isinstance(value, frozenset)
        and all(isinstance(item, str) for item in value)
    )


#: Distinct label sets remembered for one snapshot; a saved revision has one.
_MAX_RENDERING_DIGESTS_PER_SNAPSHOT = 4

#: About 175 MiB resident: a validated snapshot occupies roughly 5.5 times its
#: saved JSON. This covers a year of quarterly and annual returns; one
#: catalogue read already holds all of its snapshots at once.
VERIFIED_REGISTRY = VerifiedRegistryMemo(max_payload_bytes=32 * 1024 * 1024)


class SavedRenderingLabel(BaseModel):
    """Original human wording behind one registry localization key."""

    model_config = STRICT_FROZEN_CONFIG
    key: str
    text: str


def _model_label_keys(value: BaseModel) -> set[str]:
    """Collect scalar and tuple localization keys while recursively visiting other fields."""
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


def _label_keys(value: object) -> set[str]:
    if isinstance(value, BaseModel):
        return _model_label_keys(value)
    if isinstance(value, tuple | list):
        items = _OBJECT_SEQUENCE_ADAPTER.validate_python(value)
        sequence_keys: set[str] = set()
        for item in items:
            sequence_keys.update(_label_keys(item))
        return sequence_keys
    return set()


def _canonical_directory_ids(value: tuple[RevisionId, ...] | None) -> tuple[RevisionId, ...] | None:
    if value is not None and (not value or tuple(sorted(set(value))) != value):
        raise ValueError("saved rendering directory identities must be sorted, unique and nonempty")
    return value


def _saved_registry_snapshot(value: object, info: ValidationInfo) -> object:
    """Validate a saved registry snapshot under the directory identities saved beside it."""
    directory_ids = info.data.get("revision_directory_ids")
    if isinstance(value, RegistrySnapshot):
        return value
    context: dict[object, object] = dict(info.context) if is_object_mapping(info.context) else {}
    if directory_ids is not None:
        identifiers = _REVISION_ID_SEQUENCE_ADAPTER.validate_python(directory_ids)
        context[MODELO_REVISION_IDS_CONTEXT] = frozenset(identifiers)
    if info.mode == "json":
        payload = _SAVED_JSON_ADAPTER.dump_json(value)
        return VERIFIED_REGISTRY.validated(
            payload,
            context=context,
            validate=lambda: RegistrySnapshot.model_validate_json(payload, context=context),
        )
    return RegistrySnapshot.model_validate(value, context=context)


def _complete_registry_fields(value: RegistrySnapshot, info: FieldSerializationInfo) -> dict[str, object]:
    if info.mode == "python":
        return _STRING_MAPPING_ADAPTER.validate_python(_complete_registry_value(value))
    return registry_payload(value)


def _require_consistent_body(
    snapshot: RegistrySnapshot,
    labels: tuple[SavedRenderingLabel, ...],
    directory_ids: tuple[RevisionId, ...] | None,
) -> None:
    if len({label.key for label in labels}) != len(labels):
        raise ValueError("saved rendering labels contain duplicate identities")
    if directory_ids is not None and frozenset(directory_ids) != snapshot.modelo.directory_revision_ids:
        raise ValueError("saved rendering directory identities disagree with its captured snapshot")


#: Field naming how a saved revision stores its rendering. A rendering embedded
#: whole, as in every revision stored before this field existed, has no such
#: field; a reader never infers the form from any other missing field.
SAVED_RENDERING_FORM_FIELD = "form"
#: The stored form other than the embedded one: a reference by rendering digest.
SAVED_RENDERING_REFERENCE_FORM = "rendering_digest_reference"
#: Serialization context key under which each saved rendering is written as its reference.
SAVED_RENDERING_REFERENCE_SERIALIZATION = "calculation_rendering_by_reference"
#: Validation context key carrying the verified :class:`SavedRenderingBody` of each referenced digest.
SAVED_RENDERING_BODIES_CONTEXT = "calculation_rendering_bodies"


class SavedRenderingBody(BaseModel):
    """The shareable part of a saved rendering: registry payload, saved labels and directory identities.

    Renderings with the same rendering digest have equal bodies, so a profile
    stores each distinct body once. A body carries no authority generation, no
    digest claim and no grade: those stay on each revision's reference, and
    nothing resolves calculation authority from a body.
    """

    model_config = STRICT_FROZEN_CONFIG

    revision_directory_ids: tuple[RevisionId, ...] | None = Field(default=None, exclude_if=lambda value: value is None)
    registry_snapshot: RegistrySnapshot
    labels: tuple[SavedRenderingLabel, ...] = ()

    @field_validator("revision_directory_ids")
    @classmethod
    def _require_canonical_directory_ids(cls, value: tuple[RevisionId, ...] | None) -> tuple[RevisionId, ...] | None:
        return _canonical_directory_ids(value)

    @field_validator("registry_snapshot", mode="before")
    @classmethod
    def _restore_directory_validation(cls, value: object, info: ValidationInfo) -> object:
        return _saved_registry_snapshot(value, info)

    @field_serializer("registry_snapshot")
    def _retain_registry_fields(self, value: RegistrySnapshot, info: FieldSerializationInfo) -> dict[str, object]:
        """Persist excluded localization/schema fields required to decode original geometry."""
        return _complete_registry_fields(value, info)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _require_consistent_body(self.registry_snapshot, self.labels, self.revision_directory_ids)
        return self

    def holds_rendering_digest(self, digest: str) -> bool:
        """Whether ``digest``, the key this body is stored under, is the rendering digest of this body.

        A body saved by a build that dumped absent registry fields as ``null``
        is keyed by the digest of that dump, as its revisions' references are.
        """
        return _rendering_digest_holds(self.registry_snapshot, self.labels, self.revision_directory_ids, digest)


class SavedRenderingReference(BaseModel):
    """A saved revision's rendering held by the digest of its stored :class:`SavedRenderingBody`."""

    model_config = STRICT_FROZEN_CONFIG

    form: Literal["rendering_digest_reference"]
    schema_version: Literal[1] = 1
    authority_generation: Hex64Str
    registry_digest: Hex64Str
    rendering_digest: Hex64Str


def saved_rendering_reference_digest(value: object) -> str | None:
    """Return the digest a stored rendering refers to, or ``None`` when it is embedded or absent.

    Raises:
        ValueError: The rendering names a storage form this reader does not know,
            or a reference carries no digest.
    """
    if not is_object_mapping(value) or SAVED_RENDERING_FORM_FIELD not in value:
        return None
    if value.get(SAVED_RENDERING_FORM_FIELD) != SAVED_RENDERING_REFERENCE_FORM:
        raise ValueError("saved rendering names an unknown storage form")
    digest = value.get("rendering_digest")
    if not isinstance(digest, str):
        raise ValueError("saved rendering reference carries no rendering digest")
    return digest


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
        return _canonical_directory_ids(value)

    @field_validator("registry_snapshot", mode="before")
    @classmethod
    def _restore_directory_validation(cls, value: object, info: ValidationInfo) -> object:
        return _saved_registry_snapshot(value, info)

    @field_serializer("registry_snapshot")
    def _retain_registry_fields(self, value: RegistrySnapshot, info: FieldSerializationInfo) -> dict[str, object]:
        """Persist excluded localization/schema fields required to decode original geometry."""
        return _complete_registry_fields(value, info)

    @model_serializer(mode="wrap")
    def _by_reference_when_stored_once(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> object:
        """Write only the reference when the caller stores the body on its own, else the whole rendering."""
        context = info.context
        if is_object_mapping(context) and context.get(SAVED_RENDERING_REFERENCE_SERIALIZATION) is True:
            return self.saved_reference().model_dump(mode=info.mode)
        return handler(self)

    @model_validator(mode="after")
    def _registry_digest_matches(self) -> Self:
        if len({label.key for label in self.labels}) != len(self.labels):
            raise ValueError("saved rendering labels contain duplicate identities")
        snapshot = self.registry_snapshot
        if not _registry_digest_holds(snapshot, self.registry_digest):
            raise ValueError("saved rendering registry digest does not match its captured snapshot")
        _require_consistent_body(snapshot, self.labels, self.revision_directory_ids)
        if not _rendering_digest_holds(snapshot, self.labels, self.revision_directory_ids, self.rendering_digest):
            raise ValueError("saved rendering metadata digest does not match its captured schema and labels")
        return self

    def saved_body(self) -> SavedRenderingBody:
        """Return the shareable body a profile stores once per rendering digest."""
        return SavedRenderingBody(
            revision_directory_ids=self.revision_directory_ids,
            registry_snapshot=self.registry_snapshot,
            labels=self.labels,
        )

    def saved_reference(self) -> SavedRenderingReference:
        """Return the reference a saved revision persists in place of its body."""
        return SavedRenderingReference(
            form=SAVED_RENDERING_REFERENCE_FORM,
            schema_version=self.schema_version,
            authority_generation=self.authority_generation,
            registry_digest=self.registry_digest,
            rendering_digest=self.rendering_digest,
        )

    @classmethod
    def from_saved_body(cls, reference: SavedRenderingReference, body: SavedRenderingBody) -> Self:
        """Rebuild a saved rendering from its reference and stored body, rechecking both digests."""
        return cls(
            schema_version=reference.schema_version,
            authority_generation=reference.authority_generation,
            registry_digest=reference.registry_digest,
            revision_directory_ids=body.revision_directory_ids,
            registry_snapshot=body.registry_snapshot,
            labels=body.labels,
            rendering_digest=reference.rendering_digest,
        )

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
            registry_digest=_registry_digest(snapshot),
            registry_snapshot=snapshot,
            revision_directory_ids=directory_ids,
            labels=labels,
            rendering_digest=_rendering_digest(snapshot, labels, directory_ids),
        )


def _registry_digest(snapshot: RegistrySnapshot) -> str:
    return VERIFIED_REGISTRY.registry_digest(snapshot, lambda: content_hash_hex(snapshot.model_dump(mode="json")))


def _rendering_digest(
    snapshot: RegistrySnapshot,
    labels: tuple[SavedRenderingLabel, ...],
    directory_ids: tuple[RevisionId, ...] | None,
) -> str:
    return VERIFIED_REGISTRY.rendering_digest(
        snapshot,
        labels,
        directory_ids,
        lambda: content_hash_hex(_rendering_payload(snapshot, labels, directory_ids)),
    )


def _registry_digest_holds(snapshot: RegistrySnapshot, claimed: str) -> bool:
    """Whether ``claimed`` is the registry digest of ``snapshot`` as the current or an earlier build dumped it.

    A build that wrote absent fields as ``null`` bound its snapshots by digests
    of that form; the snapshot itself is the same either way.
    """
    if _registry_digest(snapshot) == claimed:
        return True
    earlier = _ABSENT_AS_NULL_DUMP.serializer().to_python(snapshot, mode="json")
    return content_hash_hex(earlier) == claimed


def _rendering_digest_holds(
    snapshot: RegistrySnapshot,
    labels: tuple[SavedRenderingLabel, ...],
    directory_ids: tuple[RevisionId, ...] | None,
    claimed: str,
) -> bool:
    """Whether ``claimed`` is the rendering digest as the current or an earlier build dumped it."""
    if _rendering_digest(snapshot, labels, directory_ids) == claimed:
        return True
    earlier = _STRING_MAPPING_ADAPTER.validate_python(
        _ABSENT_AS_NULL_COMPLETE.serializer().to_python(
            snapshot, mode="json", by_alias=False, exclude_computed_fields=True
        )
    )
    return content_hash_hex(_rendering_payload(snapshot, labels, directory_ids, registry=earlier)) == claimed


def _rendering_payload(
    snapshot: RegistrySnapshot,
    labels: tuple[SavedRenderingLabel, ...],
    directory_ids: tuple[RevisionId, ...] | None,
    *,
    registry: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "registry": registry_payload(snapshot) if registry is None else registry,
        "labels": [label.model_dump(mode="json") for label in labels],
    }
    if directory_ids is not None:
        payload["revision_directory_ids"] = directory_ids
    return payload


def _rendering_from_reference(reference: SavedRenderingReference, info: ValidationInfo) -> CalculationRenderingSnapshot:
    """Rebuild a referenced rendering from the verified body its reader supplied under the context."""
    bodies = info.context.get(SAVED_RENDERING_BODIES_CONTEXT) if is_object_mapping(info.context) else None
    body = bodies.get(reference.rendering_digest) if is_object_mapping(bodies) else None
    if not isinstance(body, SavedRenderingBody):
        raise ValueError("saved rendering reference has no supplied body")
    return CalculationRenderingSnapshot.from_saved_body(reference, body)


def _stored_rendering_schema(source: type[object], handler: GetCoreSchemaHandler) -> CoreSchema:
    # An embedded rendering keeps its own strict JSON validation; only when it
    # does not validate is the value read as a reference. A before or wrap
    # validator would hand the embedded JSON on as Python input and lose that.
    return core_schema.union_schema(
        [
            handler(source),
            core_schema.with_info_after_validator_function(
                _rendering_from_reference, handler.generate_schema(SavedRenderingReference)
            ),
        ],
        mode="left_to_right",
    )


#: A saved revision's rendering as storage holds it: embedded whole, as every
#: revision stored before references existed, or as a :class:`SavedRenderingReference`
#: rebuilt from the body supplied under :data:`SAVED_RENDERING_BODIES_CONTEXT`.
#: After validation it is always the whole :class:`CalculationRenderingSnapshot`.
StoredCalculationRendering = Annotated[CalculationRenderingSnapshot, GetPydanticSchema(_stored_rendering_schema)]
