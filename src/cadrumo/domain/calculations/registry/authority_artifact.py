"""Typed authority values for indexed component generations.

Product runtime admits only the descriptor-selected SQLite generation and
decodes addressed immutable components from it. ``AuthorityArtifact`` is the
development compiler's in-memory typed handoff into that database builder.
This module knows no registry root and provides no eager runtime loader.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.ModeloDefinition`,
:class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol

from ....core.errors.hierarchy import CadrumoError
from ....core.frozen_mapping import FrozenMapping
from ....core.hashing import (
    sha256_hex,
)
from .provenance import NormativeCorpusProvenance
from .schema import (
    ModeloDefinition,
    RegistryCatalogues,
)

if TYPE_CHECKING:
    from ...user_profile.schema import ProfileSchemaDefinition

__all__ = [
    "AuthorityArtifact",
    "AuthorityComponentCodecError",
    "AuthorityComponentKind",
    "AuthorityComponentQuery",
    "AuthorityComponentReader",
    "AuthorityEvidenceProjection",
    "AuthorityGenerationPin",
    "EvidenceComponentQuery",
    "ExportLayoutComponentQuery",
    "FormLayoutComponentQuery",
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
]

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
    FORM_LAYOUT = "form_layout"
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
class FormLayoutComponentQuery:
    """Retrieve the one declared form layout of a revision, separated from it."""

    modelo_id: str
    revision_id: str
    kind: Final[AuthorityComponentKind] = AuthorityComponentKind.FORM_LAYOUT


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
    | FormLayoutComponentQuery
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


def _revision_layout_identity(query: AuthorityComponentQuery) -> tuple[AuthorityComponentKind, str] | None:
    if isinstance(query, ModeloRevisionComponentQuery):
        return query.kind, f"{query.modelo_id}\x1f{query.revision_id}"
    if isinstance(query, ExportLayoutComponentQuery):
        return query.kind, f"{query.modelo_id}\x1f{query.revision_id}\x1f{query.layout_id}"
    if isinstance(query, FormLayoutComponentQuery):
        return query.kind, f"{query.modelo_id}\x1f{query.revision_id}"
    return None


def _single_key_component_identity(query: AuthorityComponentQuery) -> tuple[AuthorityComponentKind, str] | None:
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
    return None


def authority_component_identity(query: AuthorityComponentQuery) -> tuple[AuthorityComponentKind, str]:
    """Return the stable database identity for one public typed query."""
    identity = _revision_layout_identity(query)
    if identity is None:
        identity = _single_key_component_identity(query)
    if identity is not None:
        return identity
    raise TypeError(f"unsupported authority component query {query!r}")


def _single_key_query_from_identity(
    component_kind: AuthorityComponentKind,
    key: str,
) -> AuthorityComponentQuery | None:
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
    return None


def _revision_layout_query_from_identity(
    component_kind: AuthorityComponentKind,
    key: str,
) -> AuthorityComponentQuery:
    if component_kind is AuthorityComponentKind.MODELO_REVISION:
        modelo_id, revision_id = key.split("\x1f", 1)
        return ModeloRevisionComponentQuery(modelo_id, revision_id)
    if component_kind is AuthorityComponentKind.FORM_LAYOUT:
        modelo_id, revision_id = key.split("\x1f", 1)
        return FormLayoutComponentQuery(modelo_id, revision_id)
    modelo_id, revision_id, layout_id = key.split("\x1f", 2)
    return ExportLayoutComponentQuery(modelo_id, revision_id, layout_id)


def authority_query_from_identity(kind: str, key: str) -> AuthorityComponentQuery:
    """Reconstruct a public typed query from one validated component directory row."""
    try:
        component_kind = AuthorityComponentKind(kind)
        query = _single_key_query_from_identity(component_kind, key)
        if query is not None:
            return query
        return _revision_layout_query_from_identity(component_kind, key)
    except (ValueError, TypeError) as exc:
        raise AuthorityComponentCodecError(f"invalid authority component identity {kind!r}/{key!r}") from exc


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


def _validate_legal_evidence_entries(legal: tuple[PublishedLegalEvidence, ...]) -> None:
    if not isinstance(legal, tuple) or not all(isinstance(item, PublishedLegalEvidence) for item in legal):
        raise TypeError("authority evidence projection legal entries must be PublishedLegalEvidence tuples")
    ids = tuple(item.legal_reference_id for item in legal)
    if len(ids) != len(set(ids)):
        raise ValueError("authority evidence projection legal reference ids must be unique")


def _validate_source_evidence_entries(sources: tuple[PublishedSourceEvidence, ...]) -> None:
    if not isinstance(sources, tuple) or not all(isinstance(item, PublishedSourceEvidence) for item in sources):
        raise TypeError("authority evidence projection source entries must be PublishedSourceEvidence tuples")
    source_ids = tuple(item.source_reference_id for item in sources)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("authority evidence projection source reference ids must be unique")


@dataclass(frozen=True, slots=True)
class AuthorityEvidenceProjection:
    """Immutable evidence needed by citation consumers after publication."""

    legal: tuple[PublishedLegalEvidence, ...] = ()
    sources: tuple[PublishedSourceEvidence, ...] = ()
    _legal_by_id: Mapping[str, PublishedLegalEvidence] = field(init=False, repr=False, compare=False)
    _sources_by_id: Mapping[str, PublishedSourceEvidence] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Reject non-deterministic or ambiguous evidence collections."""
        _validate_legal_evidence_entries(self.legal)
        _validate_source_evidence_entries(self.sources)
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

    def source_bytes(self, source_reference_id: str) -> bytes:
        """Return digest-checked runtime source bytes for one source reference."""
        item = self._sources_by_id.get(source_reference_id)
        if item is not None:
            return item.payload
        raise AuthorityComponentCodecError(
            f"published authority artifact has no evidence projection for source reference {source_reference_id!r}"
        )


def _validate_authority_artifact_payload(
    modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
    identity_digest: str,
    evidence: AuthorityEvidenceProjection,
) -> None:
    if not isinstance(modelos, tuple) or not all(isinstance(modelo, ModeloDefinition) for modelo in modelos):
        raise TypeError("authority artifact modelos must be a tuple of ModeloDefinition instances")
    if not isinstance(catalogues, RegistryCatalogues):
        raise TypeError("authority artifact catalogues must be a RegistryCatalogues instance")
    if _IDENTITY_DIGEST.fullmatch(identity_digest) is None:
        raise ValueError("authority artifact identity_digest must be a lowercase SHA-256 hexadecimal digest")
    if not isinstance(evidence, AuthorityEvidenceProjection):
        raise TypeError("authority artifact evidence must be an AuthorityEvidenceProjection")
    modelo_ids = tuple(modelo.id for modelo in modelos)
    if len(modelo_ids) != len(set(modelo_ids)):
        raise ValueError("authority artifact modelo identities must be unique")


@dataclass(frozen=True, slots=True)
class AuthorityArtifact:
    """Complete typed authority payload emitted only after registry validation.

    ``identity_digest`` is the content-addressed identity of the legal inputs
    development validated to produce this authority: the registry sources, the
    source evidence and the profile schema. It names the law the authority
    encodes, so nothing about the compiler or its environment enters it.
    The graph is deeply immutable: its models are frozen and its mappings are
    frozen mappings, so a consumer cannot change what any other holder of the
    same instance observes.
    """

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    identity_digest: str
    profile_schema: ProfileSchemaDefinition
    evidence: AuthorityEvidenceProjection = AuthorityEvidenceProjection()

    def __post_init__(self) -> None:
        """Reject partial or untyped content before publication."""
        _validate_authority_artifact_payload(self.modelos, self.catalogues, self.identity_digest, self.evidence)
        from ...user_profile.schema import ProfileSchemaDefinition

        if not isinstance(self.profile_schema, ProfileSchemaDefinition):
            raise TypeError("authority artifact profile_schema must be a ProfileSchemaDefinition")
