"""Typed authority values and the indexed component codec.

Product runtime admits only the descriptor-selected SQLite generation and
decodes addressed immutable components from it. ``AuthorityArtifact`` is the
development compiler's in-memory typed handoff into that database builder.
This module knows no registry root and provides no eager runtime loader.
"""

from __future__ import annotations

import json
import re
from base64 import b64decode, b64encode
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import PurePath
from typing import TYPE_CHECKING, Final, Protocol, cast, get_args

from pydantic import BaseModel, TypeAdapter, ValidationError

from ....core.errors.hierarchy import CadrumoError
from ....core.frozen_mapping import FrozenMapping
from ....core.hashing import (
    canonical_json_bytes,
    content_hash_hex,
    reject_duplicate_json_members,
    reject_json_constant,
    sha256_hex,
)
from ....core.identity.documents import TAX_ID_FORMAT_CONTEXT
from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from .facts.schema import (
    TAGGED_FACT_ATOM_CONTEXT,
    FactAtomField,
    GovernedFact,
    GovernedFactCatalogue,
    OptionalFactAtomField,
    tagged_fact_atom_json,
)
from .governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from .provenance import NormativeCorpusProvenance
from .revision_contracts import DeclaredPredecessor, NoPredecessor
from .runtime_catalogues import RuntimeRegistryCatalogues
from .schema import ModeloDefinition, ModeloRevision, RegistryCatalogues, SnapshotGlobalCatalogues
from .schema_exports import ExportLayoutDefinition
from .tax_id_format import tax_id_format_from_catalogue
from .temporal import ModeloRevisionDirectory

if TYPE_CHECKING:
    from ...user_profile.schema import ProfileSchemaDefinition

__all__ = [
    "AuthorityArtifact",
    "AuthorityBuildIdentity",
    "AuthorityComponentCodecError",
    "AuthorityComponentKind",
    "AuthorityComponentQuery",
    "AuthorityComponentReader",
    "AuthorityEvidenceProjection",
    "AuthorityGenerationPin",
    "EvidenceComponentQuery",
    "ExportLayoutComponentQuery",
    "GovernedFactComponentQuery",
    "ModeloDirectoryComponentQuery",
    "ModeloRevisionComponentQuery",
    "ProfileCreateContext",
    "ProfileDecodeContext",
    "ProfileSchemaComponentQuery",
    "PublishedLegalEvidence",
    "PublishedSourceEvidence",
    "ReferenceComponentQuery",
    "RuntimeCatalogueComponentQuery",
    "SnapshotGlobalsComponentQuery",
    "authority_component_identity",
    "authority_query_from_identity",
    "decode_authority_component",
    "encode_authority_component",
]

#: The validators that mark a governed-fact atom position, read from the schema's own field types.
_FACT_ATOM_VALIDATORS: Final = frozenset(
    (get_args(FactAtomField)[1], get_args(OptionalFactAtomField)[1]),
)
_TAGGED_DECODE_CONTEXT: Final = {TAGGED_FACT_ATOM_CONTEXT: True}
_IDENTITY_DIGEST = re.compile(r"[0-9a-f]{64}")


class AuthorityComponentKind(StrEnum):
    """Closed component families addressable in one authority generation."""

    MODELO_REVISION = "modelo_revision"
    MODELO_DIRECTORY = "modelo_directory"
    GOVERNED_FACT = "governed_fact"
    PROFILE_SCHEMA = "profile_schema"
    RUNTIME_CATALOGUE = "runtime_catalogue"
    LEGAL_REFERENCE = "legal_reference"
    SOURCE_REFERENCE = "source_reference"
    LEGAL_EVIDENCE = "legal_evidence"
    SOURCE_EVIDENCE = "source_evidence"
    EXPORT_LAYOUT = "export_layout"
    SNAPSHOT_GLOBALS = "snapshot_globals"


@dataclass(frozen=True, slots=True)
class AuthorityGenerationPin:
    """Immutable identity of the reader incarnation used by one operation."""

    logical_generation: str
    reader_incarnation: str

    def __post_init__(self) -> None:
        """Refuse identities that cannot name accepted generation content."""
        if _IDENTITY_DIGEST.fullmatch(self.logical_generation) is None:
            raise ValueError("authority generation pin requires a lowercase SHA-256 logical generation")
        if _IDENTITY_DIGEST.fullmatch(self.reader_incarnation) is None:
            raise ValueError("authority generation pin requires a lowercase SHA-256 reader incarnation")


@dataclass(frozen=True, slots=True)
class ModeloRevisionComponentQuery:
    """Retrieve one complete modelo revision by its canonical identity."""

    modelo_id: str
    revision_id: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.MODELO_REVISION


@dataclass(frozen=True, slots=True)
class ModeloDirectoryComponentQuery:
    """Retrieve complete canonical selection metadata for one modelo."""

    modelo_id: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.MODELO_DIRECTORY


@dataclass(frozen=True, slots=True)
class GovernedFactComponentQuery:
    """Retrieve one governed fact declaration and all its resolved variants."""

    fact_id: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.GOVERNED_FACT


@dataclass(frozen=True, slots=True)
class ProfileSchemaComponentQuery:
    """Retrieve the complete public profile declaration for a pinned operation."""

    schema_id: str = "cadrumo.user_profile"
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.PROFILE_SCHEMA


@dataclass(frozen=True, slots=True)
class RuntimeCatalogueComponentQuery:
    """Retrieve one named runtime catalogue without hydrating sibling families."""

    family: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.RUNTIME_CATALOGUE


@dataclass(frozen=True, slots=True)
class SnapshotGlobalsComponentQuery:
    """Retrieve the small registry-wide values needed by point snapshots."""

    key: Final[str] = "snapshot"
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.SNAPSHOT_GLOBALS


@dataclass(frozen=True, slots=True)
class ReferenceComponentQuery:
    """Retrieve one legal or public-source declaration by canonical id."""

    reference_id: str
    kind: AuthorityComponentKind

    def __post_init__(self) -> None:
        """Keep reference queries inside their two declaration families."""
        if self.kind not in (AuthorityComponentKind.LEGAL_REFERENCE, AuthorityComponentKind.SOURCE_REFERENCE):
            raise ValueError("reference queries require a legal_reference or source_reference component kind")


@dataclass(frozen=True, slots=True)
class ExportLayoutComponentQuery:
    """Retrieve one substantial export layout separated from its revision."""

    modelo_id: str
    revision_id: str
    layout_id: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.EXPORT_LAYOUT


@dataclass(frozen=True, slots=True)
class EvidenceComponentQuery:
    """Retrieve one legal or public-source evidence projection by canonical id."""

    reference_id: str
    kind: AuthorityComponentKind

    def __post_init__(self) -> None:
        """Keep the generic evidence query inside its two closed families."""
        if self.kind not in (AuthorityComponentKind.LEGAL_EVIDENCE, AuthorityComponentKind.SOURCE_EVIDENCE):
            raise ValueError("evidence queries require a legal_evidence or source_evidence component kind")


type AuthorityComponentQuery = (
    ModeloRevisionComponentQuery
    | ModeloDirectoryComponentQuery
    | GovernedFactComponentQuery
    | ProfileSchemaComponentQuery
    | RuntimeCatalogueComponentQuery
    | SnapshotGlobalsComponentQuery
    | ReferenceComponentQuery
    | EvidenceComponentQuery
    | ExportLayoutComponentQuery
)


class AuthorityComponentReader(Protocol):
    """Generation-pinned typed component access used by runtime consumers."""

    def pin(self) -> AuthorityGenerationPin:
        """Pin the currently published reader incarnation for one operation."""
        ...

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        """Load one component from exactly ``pin`` or refuse a stale/cross-reader pin."""

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        """Return deterministic addresses without hydrating component payloads."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileCreateContext:
    """Schema authority required when creating taxpayer profile values."""

    schema: ProfileSchemaDefinition
    generation: AuthorityGenerationPin


@dataclass(frozen=True, slots=True)
class ProfileDecodeContext:
    """Schema authority required when decoding encrypted persisted profile values."""

    schema: ProfileSchemaDefinition
    generation: AuthorityGenerationPin


class AuthorityComponentCodecError(CadrumoError):
    """One addressed component failed canonical encoding or strict decoding."""


def encode_authority_component(query: AuthorityComponentQuery, value: object) -> bytes:
    """Encode one typed component with the canonical authority value vocabulary."""
    try:
        payload: object
        if isinstance(value, PublishedLegalEvidence):
            payload = {
                "legal_reference_id": value.legal_reference_id,
                "anchored_text": value.anchored_text,
                "text_sha256": value.text_sha256,
                "provenance": value.provenance.value,
            }
        elif isinstance(value, PublishedSourceEvidence):
            payload = {
                "source_reference_id": value.source_reference_id,
                "payload_base64": b64encode(value.payload).decode("ascii"),
                "payload_sha256": value.payload_sha256,
            }
        else:
            payload = _json_value(value)
        return canonical_json_bytes(
            {"codec": "cadrumo-authority-component-v1", "kind": query.kind.value, "payload": payload}
        )
    except (TypeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"authority component {query!r} could not be encoded") from exc


def decode_authority_component(
    query: AuthorityComponentQuery,
    payload: bytes,
    *,
    dependencies: tuple[object, ...] = (),
    fact_query_observer: Callable[[GovernedFactQuery], None] | None = None,
) -> object:
    """Strictly decode one addressed component using only declared dependencies."""
    try:
        frame = _decode_json_object(payload, subject="authority component")
        _require_members(frame, {"codec", "kind", "payload"}, "component")
        if _required_string(frame, "codec") != "cadrumo-authority-component-v1":
            raise AuthorityComponentCodecError("authority component uses an unsupported codec")
        if _required_string(frame, "kind") != query.kind.value:
            raise AuthorityComponentCodecError("authority component kind does not match its query")
        document = frame["payload"]
        if isinstance(query, ProfileSchemaComponentQuery):
            from ...user_profile.schema import ProfileSchemaDefinition

            return ProfileSchemaDefinition.model_validate(document, strict=False)
        if isinstance(query, GovernedFactComponentQuery):
            return GovernedFact.model_validate(document, strict=False, context=_TAGGED_DECODE_CONTEXT)
        if isinstance(query, ModeloRevisionComponentQuery):
            facts = tuple(item for item in dependencies if isinstance(item, GovernedFact))
            fact_catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})
            tax_id_format = tax_id_format_from_catalogue(fact_catalogue)
            context = {**_TAGGED_DECODE_CONTEXT, TAX_ID_FORMAT_CONTEXT: tax_id_format}
            candidate = CandidateFactAuthority(fact_catalogue)
            source = _ObservedFactAuthority(candidate, fact_query_observer) if fact_query_observer else candidate
            with validating_governed_facts(source):
                return ModeloRevision.model_validate(document, strict=False, context=context)
        if isinstance(query, ModeloDirectoryComponentQuery):
            return ModeloRevisionDirectory.model_validate(document, strict=False)
        if isinstance(query, RuntimeCatalogueComponentQuery):
            field = RuntimeRegistryCatalogues.model_fields.get(query.family)
            if field is None or field.annotation is None:
                raise AuthorityComponentCodecError(f"unknown runtime catalogue family {query.family!r}")
            return TypeAdapter(field.annotation).validate_python(document, strict=False)
        if isinstance(query, SnapshotGlobalsComponentQuery):
            facts = tuple(item for item in dependencies if isinstance(item, GovernedFact))
            fact_catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in facts})
            candidate = CandidateFactAuthority(fact_catalogue)
            source = _ObservedFactAuthority(candidate, fact_query_observer) if fact_query_observer else candidate
            with validating_governed_facts(source):
                return SnapshotGlobalCatalogues.model_validate(document, strict=False)
        if isinstance(query, ReferenceComponentQuery):
            from .schema_references import LegalReference, SourceReference

            model = LegalReference if query.kind is AuthorityComponentKind.LEGAL_REFERENCE else SourceReference
            return model.model_validate(document, strict=False)
        if isinstance(query, EvidenceComponentQuery):
            row = _mapping_item(document, "payload")
            if query.kind is AuthorityComponentKind.LEGAL_EVIDENCE:
                return PublishedLegalEvidence(
                    legal_reference_id=_required_string(row, "legal_reference_id"),
                    anchored_text=_required_string(row, "anchored_text"),
                    text_sha256=_required_string(row, "text_sha256"),
                    provenance=NormativeCorpusProvenance(_required_string(row, "provenance")),
                )
            return PublishedSourceEvidence(
                source_reference_id=_required_string(row, "source_reference_id"),
                payload=_decode_base64(_required_string(row, "payload_base64")),
                payload_sha256=_required_string(row, "payload_sha256"),
            )
        if isinstance(query, ExportLayoutComponentQuery):
            return ExportLayoutDefinition.model_validate(document, strict=False)
        raise AuthorityComponentCodecError(f"unsupported authority component query {query!r}")
    except AuthorityComponentCodecError:
        raise
    except (ValidationError, TypeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"authority component {query!r} failed typed decoding") from exc


@dataclass(frozen=True, slots=True, weakref_slot=True)
class _ObservedFactAuthority:
    """Report the exact governed queries exercised by one component decode."""

    authority: CandidateFactAuthority
    observer: Callable[[GovernedFactQuery], None]

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.observer(query)
        return self.authority.resolve_governed_fact(query)


def authority_component_identity(query: AuthorityComponentQuery) -> tuple[AuthorityComponentKind, str]:
    """Return the stable database identity for one public typed query."""
    if isinstance(query, ModeloRevisionComponentQuery):
        return query.kind, f"{query.modelo_id}\x1f{query.revision_id}"
    if isinstance(query, ModeloDirectoryComponentQuery):
        return query.kind, query.modelo_id
    if isinstance(query, GovernedFactComponentQuery):
        return query.kind, query.fact_id
    if isinstance(query, ProfileSchemaComponentQuery):
        return query.kind, query.schema_id
    if isinstance(query, RuntimeCatalogueComponentQuery):
        return query.kind, query.family
    if isinstance(query, SnapshotGlobalsComponentQuery):
        return query.kind, query.key
    if isinstance(query, ReferenceComponentQuery):
        return query.kind, query.reference_id
    if isinstance(query, EvidenceComponentQuery):
        return query.kind, query.reference_id
    if isinstance(query, ExportLayoutComponentQuery):
        return query.kind, f"{query.modelo_id}\x1f{query.revision_id}\x1f{query.layout_id}"
    raise TypeError(f"unsupported authority component query {query!r}")


def authority_query_from_identity(kind: str, key: str) -> AuthorityComponentQuery:
    """Reconstruct a public typed query from one validated component directory row."""
    try:
        component_kind = AuthorityComponentKind(kind)
        if component_kind is AuthorityComponentKind.MODELO_REVISION:
            modelo_id, revision_id = key.split("\x1f", 1)
            return ModeloRevisionComponentQuery(modelo_id, revision_id)
        if component_kind is AuthorityComponentKind.MODELO_DIRECTORY:
            return ModeloDirectoryComponentQuery(key)
        if component_kind is AuthorityComponentKind.GOVERNED_FACT:
            return GovernedFactComponentQuery(key)
        if component_kind is AuthorityComponentKind.PROFILE_SCHEMA:
            return ProfileSchemaComponentQuery(key)
        if component_kind is AuthorityComponentKind.RUNTIME_CATALOGUE:
            return RuntimeCatalogueComponentQuery(key)
        if component_kind is AuthorityComponentKind.SNAPSHOT_GLOBALS:
            if key != "snapshot":
                raise AuthorityComponentCodecError(f"invalid snapshot globals key {key!r}")
            return SnapshotGlobalsComponentQuery()
        if component_kind in (AuthorityComponentKind.LEGAL_REFERENCE, AuthorityComponentKind.SOURCE_REFERENCE):
            return ReferenceComponentQuery(key, component_kind)
        if component_kind in (AuthorityComponentKind.LEGAL_EVIDENCE, AuthorityComponentKind.SOURCE_EVIDENCE):
            return EvidenceComponentQuery(key, component_kind)
        if component_kind is AuthorityComponentKind.EXPORT_LAYOUT:
            modelo_id, revision_id, layout_id = key.split("\x1f", 2)
            return ExportLayoutComponentQuery(modelo_id, revision_id, layout_id)
    except (ValueError, TypeError) as exc:
        raise AuthorityComponentCodecError(f"invalid authority component identity {kind!r}/{key!r}") from exc
    raise AuthorityComponentCodecError(f"unknown authority component identity {kind!r}/{key!r}")


@dataclass(frozen=True, slots=True)
class PublishedLegalEvidence:
    """One publisher-validated, anchor-scoped legal text projection.

    This is deliberately text and identity, rather than a corpus filename or
    source root.  The release artifact is the runtime evidence boundary.
    """

    legal_reference_id: str
    anchored_text: str
    text_sha256: str
    provenance: NormativeCorpusProvenance = NormativeCorpusProvenance.OUT_OF_SCOPE

    def __post_init__(self) -> None:
        """Reject incomplete or altered publisher-projected text."""
        if not self.legal_reference_id:
            raise ValueError("published legal evidence requires a legal reference id")
        if not self.anchored_text:
            raise ValueError("published legal evidence requires anchored text")
        if _IDENTITY_DIGEST.fullmatch(self.text_sha256) is None:
            raise ValueError("published legal evidence requires a lowercase SHA-256 text digest")
        if sha256_hex(self.anchored_text.encode("utf-8")) != self.text_sha256:
            raise ValueError("published legal evidence text digest does not match its anchored text")


@dataclass(frozen=True, slots=True)
class PublishedSourceEvidence:
    """Publisher-validated source bytes required by a shipped workflow.

    Corpus paths remain descriptive catalogue metadata.  A runtime reader gets
    bytes only through this digest-checked projection, never by joining that path to a
    package or checkout root.
    """

    source_reference_id: str
    payload: bytes
    payload_sha256: str

    def __post_init__(self) -> None:
        """Reject incomplete or altered publisher-projected source bytes."""
        if not self.source_reference_id:
            raise ValueError("published source evidence requires a source reference id")
        if not self.payload:
            raise ValueError("published source evidence requires payload bytes")
        if _IDENTITY_DIGEST.fullmatch(self.payload_sha256) is None:
            raise ValueError("published source evidence requires a lowercase SHA-256 payload digest")
        if sha256_hex(self.payload) != self.payload_sha256:
            raise ValueError("published source evidence payload digest does not match its bytes")


@dataclass(frozen=True, slots=True)
class AuthorityEvidenceProjection:
    """Immutable evidence needed by citation consumers after publication."""

    legal: tuple[PublishedLegalEvidence, ...] = ()
    sources: tuple[PublishedSourceEvidence, ...] = ()
    _legal_by_id: Mapping[str, PublishedLegalEvidence] = field(init=False, repr=False, compare=False)
    _sources_by_id: Mapping[str, PublishedSourceEvidence] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Reject non-deterministic or ambiguous evidence collections."""
        if not isinstance(self.legal, tuple) or not all(
            isinstance(item, PublishedLegalEvidence) for item in self.legal
        ):
            raise TypeError("authority evidence projection legal entries must be PublishedLegalEvidence tuples")
        ids = tuple(item.legal_reference_id for item in self.legal)
        if len(ids) != len(set(ids)):
            raise ValueError("authority evidence projection legal reference ids must be unique")
        if not isinstance(self.sources, tuple) or not all(
            isinstance(item, PublishedSourceEvidence) for item in self.sources
        ):
            raise TypeError("authority evidence projection source entries must be PublishedSourceEvidence tuples")
        source_ids = tuple(item.source_reference_id for item in self.sources)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("authority evidence projection source reference ids must be unique")
        object.__setattr__(self, "_legal_by_id", FrozenMapping({item.legal_reference_id: item for item in self.legal}))
        object.__setattr__(
            self, "_sources_by_id", FrozenMapping({item.source_reference_id: item for item in self.sources})
        )

    def legal_text(self, legal_reference_id: str) -> str:
        """Return publisher-validated text for one legal citation or refuse."""
        item = self._legal_by_id.get(legal_reference_id)
        if item is not None:
            return item.anchored_text
        raise AuthorityComponentCodecError(
            f"published authority artifact has no evidence projection for legal reference {legal_reference_id!r}"
        )

    def quotation_is_grounded(self, legal_reference_id: str, quotation: str) -> bool:
        """Answer a citation query without opening any authoring corpus path."""
        from ....core.corpus_text import normalise_corpus_text

        return bool(quotation.strip()) and normalise_corpus_text(quotation) in self.legal_text(legal_reference_id)

    def legal_provenance(self, legal_reference_id: str) -> NormativeCorpusProvenance:
        """Return the publisher-derived provenance for one legal reference."""
        item = self._legal_by_id.get(legal_reference_id)
        if item is not None:
            return item.provenance
        raise AuthorityComponentCodecError(
            f"published authority artifact has no evidence projection for legal reference {legal_reference_id!r}"
        )

    def source_bytes(self, source_reference_id: str) -> bytes:
        """Return digest-checked runtime source bytes for one source reference."""
        item = self._sources_by_id.get(source_reference_id)
        if item is not None:
            return item.payload
        raise AuthorityComponentCodecError(
            f"published authority artifact has no evidence projection for source reference {source_reference_id!r}"
        )


@dataclass(frozen=True, slots=True)
class AuthorityBuildIdentity:
    """Distinct source, compiler, and whole-generation dependency receipts."""

    source_identity_digest: str
    compiler_identity_digest: str
    component_dependency_digest: str

    def __post_init__(self) -> None:
        """Refuse malformed receipts or a dependency receipt for other inputs."""
        if any(
            _IDENTITY_DIGEST.fullmatch(value) is None
            for value in (
                self.source_identity_digest,
                self.compiler_identity_digest,
                self.component_dependency_digest,
            )
        ):
            raise ValueError("authority build identities must be lowercase SHA-256 digests")
        if self.component_dependency_digest != self._component_digest():
            raise ValueError("authority component dependency identity does not match its complete inputs")

    def _component_digest(self) -> str:
        return content_hash_hex(
            {
                "schema": "authority-component-dependencies/v1",
                "component": "complete-authority",
                "source_identity_digest": self.source_identity_digest,
                "compiler_identity_digest": self.compiler_identity_digest,
            }
        )

    @classmethod
    def from_inputs(cls, source_identity_digest: str, compiler_identity_digest: str) -> AuthorityBuildIdentity:
        """Create the dependency receipt for a full canonical compilation."""
        component = content_hash_hex(
            {
                "schema": "authority-component-dependencies/v1",
                "component": "complete-authority",
                "source_identity_digest": source_identity_digest,
                "compiler_identity_digest": compiler_identity_digest,
            }
        )
        return cls(source_identity_digest, compiler_identity_digest, component)

    @property
    def identity_digest(self) -> str:
        """Combine the distinct receipts into the runtime generation identity."""
        return content_hash_hex(
            {
                "schema": "authority-generation/v1",
                "source_identity_digest": self.source_identity_digest,
                "compiler_identity_digest": self.compiler_identity_digest,
                "component_dependency_digest": self.component_dependency_digest,
            }
        )


@dataclass(frozen=True, slots=True)
class AuthorityArtifact:
    """Complete typed authority payload emitted only after registry validation.

    ``identity_digest`` is the content-addressed identity of the registry and
    source-evidence inputs development validated to produce this authority.
    The graph is deeply immutable: its models are frozen and its mappings are
    frozen mappings, so a consumer cannot change what any other holder of the
    same instance observes.
    """

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    identity_digest: str
    build_identity: AuthorityBuildIdentity
    profile_schema: ProfileSchemaDefinition
    evidence: AuthorityEvidenceProjection = AuthorityEvidenceProjection()

    def __post_init__(self) -> None:
        """Reject partial or untyped content before publication."""
        if not isinstance(self.modelos, tuple) or not all(
            isinstance(modelo, ModeloDefinition) for modelo in self.modelos
        ):
            raise TypeError("authority artifact modelos must be a tuple of ModeloDefinition instances")
        if not isinstance(self.catalogues, RegistryCatalogues):
            raise TypeError("authority artifact catalogues must be a RegistryCatalogues instance")
        if _IDENTITY_DIGEST.fullmatch(self.identity_digest) is None:
            raise ValueError("authority artifact identity_digest must be a lowercase SHA-256 hexadecimal digest")
        if not isinstance(self.build_identity, AuthorityBuildIdentity):
            raise TypeError("authority artifact requires typed build identity")
        if self.identity_digest != self.build_identity.identity_digest:
            raise ValueError("authority generation identity does not match its build receipts")
        if not isinstance(self.evidence, AuthorityEvidenceProjection):
            raise TypeError("authority artifact evidence must be an AuthorityEvidenceProjection")
        from ...user_profile.schema import ProfileSchemaDefinition

        if not isinstance(self.profile_schema, ProfileSchemaDefinition):
            raise TypeError("authority artifact profile_schema must be a ProfileSchemaDefinition")
        modelo_ids = tuple(modelo.id for modelo in self.modelos)
        if len(modelo_ids) != len(set(modelo_ids)):
            raise ValueError("authority artifact modelo identities must be unique")

    def require_evidence_closure(self) -> None:
        """Require every runtime evidence projection to agree with its catalogue."""
        legal_ids = {item.legal_reference_id for item in self.evidence.legal}
        if legal_ids != set(self.catalogues.legal):
            raise ValueError("authority artifact legal evidence must cover exactly its legal catalogue")
        required_sources = {
            str(key) for key, source in self.catalogues.sources.items() if source.kind in {"dictionary", "xsd"}
        }
        source_ids = {item.source_reference_id for item in self.evidence.sources}
        if source_ids != required_sources:
            raise ValueError("authority artifact source evidence must cover exactly its runtime source catalogue")
        for item in self.evidence.sources:
            source = self.catalogues.sources[item.source_reference_id]
            if item.payload_sha256 != source.sha256 or len(item.payload) != source.bytes:
                raise ValueError(f"authority artifact source evidence disagrees with catalogue {source.id!r}")


def _json_value(value: object) -> object:
    """Project registry values to JSON, omitting only schema-declared defaults."""
    if isinstance(value, DeclaredPredecessor | NoPredecessor):
        # The predecessor union intentionally owns a compact authored wire
        # dialect. Its serializer is a semantic projection, unlike ordinary
        # presentation serializers that may hide fields needed for authority
        # reconstruction.
        return _json_value(value.model_dump(mode="json"))
    if isinstance(value, BaseModel):
        if type(value).__pydantic_decorators__.model_serializers:
            # A model that declares its own serialiser is authored in that
            # shape, and its parser accepts only that shape back.
            return _json_value(value.model_dump(mode="python"))
        return {
            field_name: (
                tagged_fact_atom_json(getattr(value, field_name))
                if _FACT_ATOM_VALIDATORS.intersection(field.metadata)
                else _json_value(getattr(value, field_name))
            )
            for field_name, field in type(value).model_fields.items()
            if not _field_equals_declared_default(value, field_name)
        }
    if isinstance(value, Mapping):
        return {_json_key(key): _json_value(item) for key, item in cast(Mapping[object, object], value).items()}
    if isinstance(value, (frozenset, set)):
        # Iteration order of a set follows per-process string hashing, so an
        # unordered collection is written in canonical-JSON order: the same
        # authority always publishes the same bytes.
        return sorted(
            (_json_value(item) for item in cast(set[object] | frozenset[object], value)), key=canonical_json_bytes
        )
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in cast(Sequence[object], value)]
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, PurePath):
        return value.as_posix()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"authority artifact cannot serialize {type(value).__name__}")


def _field_equals_declared_default(model: BaseModel, field_name: str) -> bool:
    """Return whether the schema explicitly permits this field to be omitted."""
    if field_name == "kind":
        # Registry discriminated unions use ``kind`` as their wire tag.  A
        # member commonly gives that Literal field a default so direct Python
        # construction stays ergonomic, but the parent union still requires
        # the tag when it rehydrates canonical JSON.
        return False
    field = type(model).model_fields[field_name]
    if field.is_required():
        return False
    try:
        comparison = getattr(model, field_name) == field.get_default(call_default_factory=True)
    except (TypeError, ValueError):
        # A context-sensitive default factory, or a value whose equality is not
        # scalar, is not sufficient authority to remove published information.
        return False
    return comparison if isinstance(comparison, bool) else False


def _json_key(key: object) -> str:
    """Project a mapping key through the JSON-safe value vocabulary."""
    value = _json_value(key)
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError("authority artifact mapping keys must be JSON scalar values")
    return str(value)


def _decode_json_object(raw: bytes, *, subject: str) -> dict[str, object]:
    """Decode JSON while refusing duplicate names and non-finite values."""
    try:
        decoded = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
    except (TypeError, UnicodeDecodeError, ValueError) as exc:
        raise AuthorityComponentCodecError(f"{subject} is not valid canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise AuthorityComponentCodecError(f"{subject} must be a JSON object")
    return cast(dict[str, object], decoded)


def _require_members(document: Mapping[str, object], expected: set[str], subject: str) -> None:
    """Refuse misspelled or unrecognized envelope fields before typed admission."""
    if set(document) != expected:
        raise AuthorityComponentCodecError(f"authority component {subject} has unexpected or missing members")


def _required_string(document: Mapping[str, object], field_name: str) -> str:
    """Return one non-empty string field or raise a format refusal."""
    value = document.get(field_name)
    if not isinstance(value, str) or not value:
        raise AuthorityComponentCodecError(f"authority component field {field_name!r} must be a non-empty string")
    return value


def _mapping_item(value: object, field_name: str) -> Mapping[str, object]:
    """Require one decoded JSON object."""
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in cast(Mapping[object, object], value)):
        raise AuthorityComponentCodecError(f"authority component field {field_name!r} must be an object")
    return cast(Mapping[str, object], value)


def _decode_base64(value: str) -> bytes:
    try:
        return b64decode(value.encode("ascii"), validate=True)
    except ValueError as exc:
        raise AuthorityComponentCodecError("authority component contains invalid base64 source evidence") from exc
