"""Typed, read-only identity records for bundled corpus artifacts.

This module deliberately does not resolve registry authority or read a corpus
tree.  It gives acquisition, derivation, and coverage tooling one vocabulary
for the facts they share.  Filing consumers continue to use
``ValidatedRegistryAuthority`` and ``SourceReference``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

__all__ = [
    "ArtifactCatalogue",
    "ArtifactDiagnostic",
    "ArtifactDiagnosticKind",
    "ArtifactDisposition",
    "ArtifactIdentity",
    "ArtifactRole",
    "DerivedArtifact",
    "SemanticAnnotation",
    "compile_artifact_catalogue",
    "declared_dispositions",
    "einvoice_manifest_identities",
    "manual_manifest_identity",
    "record_design_manifest_identities",
    "registry_source_identity",
]

if TYPE_CHECKING:
    from .schema_references import SourceReference


_SHA256 = re.compile(r"[0-9a-f]{64}")


def _bundled_path(value: str | PurePosixPath, *, field_name: str) -> PurePosixPath:
    """Validate and return a canonical bundled-data-relative POSIX path."""
    raw = str(value)
    path = PurePosixPath(raw)
    if (
        not raw
        or not path.parts
        or raw != path.as_posix()
        or "\\" in raw
        or path.is_absolute()
        or any(part in {".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be a bundled-data-relative POSIX path")
    return path


def _sha256(value: str, *, field_name: str) -> str:
    """Refuse a digest that is not the canonical lowercase SHA-256 spelling."""
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hexadecimal digest")
    return value


class ArtifactRole(StrEnum):
    """The one catalogued role assigned to a bundled artifact."""

    OFFICIAL_ARTIFACT = "official_artifact"
    DERIVED_ARTIFACT = "derived_artifact"
    SEMANTIC_ANNOTATION = "semantic_annotation"
    DISPOSITION = "disposition"
    FIXTURE = "fixture"


class ArtifactDiagnosticKind(StrEnum):
    """A failure class emitted by a future catalog compiler."""

    MISSING_IDENTITY = "missing_identity"
    MALFORMED_IDENTITY = "malformed_identity"
    CONFLICTING_IDENTITY = "conflicting_identity"
    ORPHANED_TARGET = "orphaned_target"
    UNKNOWN_FILE = "unknown_file"
    STALE_DERIVATIVE = "stale_derivative"
    BROKEN_REGISTRY_BINDING = "broken_registry_binding"


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Immutable acquisition identity for one canonical bundled path.

    ``path`` is always the bundled-data-relative POSIX path (for example,
    ``corpus/manuals/iva/2025/source.pdf``), never an operating-system path.
    It is deliberately distinct from :class:`SourceReference`: this record
    has no filing applicability, evidence tier, or review semantics.
    """

    path: PurePosixPath
    sha256: str
    bytes: int
    source_url: str
    publisher: str | None
    retrieved_at: date

    def __post_init__(self) -> None:
        """Reject non-canonical identity claims at the declaration boundary."""
        object.__setattr__(self, "path", _bundled_path(self.path, field_name="path"))
        object.__setattr__(self, "sha256", _sha256(self.sha256, field_name="sha256"))
        if self.bytes <= 0:
            raise ValueError("bytes must be positive")
        parsed = urlparse(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP(S) URL")
        if self.publisher is not None and not self.publisher.strip():
            raise ValueError("publisher must be non-empty when declared")


@dataclass(frozen=True, slots=True)
class DerivedArtifact:
    """A bundled derivative with the exact source identity and producer it uses."""

    path: PurePosixPath
    input_path: PurePosixPath
    input_sha256: str
    producer: str

    def __post_init__(self) -> None:
        """Require one canonical input and a named producing process."""
        object.__setattr__(self, "path", _bundled_path(self.path, field_name="path"))
        object.__setattr__(self, "input_path", _bundled_path(self.input_path, field_name="input_path"))
        object.__setattr__(self, "input_sha256", _sha256(self.input_sha256, field_name="input_sha256"))
        if not self.producer.strip():
            raise ValueError("producer must be non-empty")


@dataclass(frozen=True, slots=True)
class SemanticAnnotation:
    """A non-authoritative annotation whose subject remains explicit."""

    path: PurePosixPath
    target_path: PurePosixPath

    def __post_init__(self) -> None:
        """Keep annotations in the catalog without upgrading their authority."""
        object.__setattr__(self, "path", _bundled_path(self.path, field_name="path"))
        object.__setattr__(self, "target_path", _bundled_path(self.target_path, field_name="target_path"))


@dataclass(frozen=True, slots=True)
class ArtifactDisposition:
    """A non-payload declaration that names its target and the reason for it."""

    declaration_path: PurePosixPath
    target_path: PurePosixPath | None
    reason: str

    def __post_init__(self) -> None:
        """Require the declared non-payload classification to be actionable."""
        object.__setattr__(
            self,
            "declaration_path",
            _bundled_path(self.declaration_path, field_name="declaration_path"),
        )
        if self.target_path is not None:
            object.__setattr__(self, "target_path", _bundled_path(self.target_path, field_name="target_path"))
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")


@dataclass(frozen=True, slots=True)
class ArtifactDiagnostic:
    """One catalog compilation finding, retained without a boolean collapse."""

    kind: ArtifactDiagnosticKind
    path: PurePosixPath | None
    message: str


@dataclass(frozen=True, slots=True)
class ArtifactCatalogue:
    """Read-only catalog output and its non-collapsed diagnostic findings.

    This is intentionally a compilation result, not a registry authority.  It
    has no filesystem traversal: callers pass the bounded set of paths whose
    classification they want checked.
    """

    identities: Mapping[PurePosixPath, ArtifactIdentity]
    roles: Mapping[PurePosixPath, ArtifactRole]
    diagnostics: tuple[ArtifactDiagnostic, ...]


def compile_artifact_catalogue(
    *,
    known_paths: Sequence[str | PurePosixPath],
    official_identities: Sequence[ArtifactIdentity] = (),
    derived_artifacts: Sequence[DerivedArtifact] = (),
    semantic_annotations: Sequence[SemanticAnnotation] = (),
    dispositions: Sequence[ArtifactDisposition] = (),
    fixture_paths: Sequence[str | PurePosixPath] = (),
    registry_identities: Sequence[ArtifactIdentity] = (),
) -> ArtifactCatalogue:
    """Compile bounded artifact claims into roles and typed diagnostics.

    ``known_paths`` is deliberately supplied by the caller rather than found
    by walking a filesystem.  That keeps this module a deterministic compiler
    and lets each consumer decide the corpus boundary it owns.  Registry
    identities are compared only as byte-identity projections; this function
    neither validates nor publishes registry authority.
    """
    known = {_bundled_path(path, field_name="known_path") for path in known_paths}
    fixtures = {_bundled_path(path, field_name="fixture_path") for path in fixture_paths}
    diagnostics: list[ArtifactDiagnostic] = []
    identities: dict[PurePosixPath, ArtifactIdentity] = {}
    role_claims: dict[PurePosixPath, set[ArtifactRole]] = {}

    def diagnostic(kind: ArtifactDiagnosticKind, path: PurePosixPath | None, message: str) -> None:
        diagnostics.append(ArtifactDiagnostic(kind=kind, path=path, message=message))

    def claim_role(path: PurePosixPath, role: ArtifactRole) -> bool:
        if path not in known:
            diagnostic(
                ArtifactDiagnosticKind.ORPHANED_TARGET,
                path,
                "catalog role claim lies outside the supplied corpus boundary",
            )
            return False
        role_claims.setdefault(path, set()).add(role)
        return True

    for identity in official_identities:
        if not claim_role(identity.path, ArtifactRole.OFFICIAL_ARTIFACT):
            continue
        existing = identities.get(identity.path)
        if existing is not None and existing != identity:
            diagnostic(
                ArtifactDiagnosticKind.CONFLICTING_IDENTITY,
                identity.path,
                "multiple official identity declarations disagree for this bundled path",
            )
        else:
            identities.setdefault(identity.path, identity)
    for derivative in derived_artifacts:
        in_boundary = claim_role(derivative.path, ArtifactRole.DERIVED_ARTIFACT)
        source = identities.get(derivative.input_path)
        if not in_boundary:
            continue
        if source is None:
            diagnostic(
                ArtifactDiagnosticKind.STALE_DERIVATIVE,
                derivative.path,
                "derived artifact names an input that has no official identity",
            )
        elif source.sha256 != derivative.input_sha256:
            diagnostic(
                ArtifactDiagnosticKind.STALE_DERIVATIVE,
                derivative.path,
                "derived artifact input digest differs from the current official identity",
            )

    for annotation in semantic_annotations:
        in_boundary = claim_role(annotation.path, ArtifactRole.SEMANTIC_ANNOTATION)
        if not in_boundary:
            continue
        if annotation.target_path not in known:
            diagnostic(
                ArtifactDiagnosticKind.ORPHANED_TARGET,
                annotation.path,
                "semantic annotation names a target outside the supplied corpus boundary",
            )

    for fixture in fixtures:
        claim_role(fixture, ArtifactRole.FIXTURE)

    for disposition in dispositions:
        in_boundary = claim_role(disposition.declaration_path, ArtifactRole.DISPOSITION)
        if in_boundary and disposition.target_path is not None and disposition.target_path not in known:
            diagnostic(
                ArtifactDiagnosticKind.ORPHANED_TARGET,
                disposition.target_path,
                "disposition names a target outside the supplied corpus boundary",
            )

    for registry_identity in registry_identities:
        official_identity = identities.get(registry_identity.path)
        if official_identity != registry_identity:
            diagnostic(
                ArtifactDiagnosticKind.BROKEN_REGISTRY_BINDING,
                registry_identity.path,
                "registry source identity does not exactly bind an official catalog identity",
            )

    roles: dict[PurePosixPath, ArtifactRole] = {}
    for path, claims in role_claims.items():
        if len(claims) != 1:
            diagnostic(
                ArtifactDiagnosticKind.CONFLICTING_IDENTITY,
                path,
                "a bundled path has more than one catalog role",
            )
            continue
        roles[path] = next(iter(claims))

    for path in sorted(known - set(role_claims), key=str):
        diagnostic(
            ArtifactDiagnosticKind.UNKNOWN_FILE,
            path,
            "bundled path has no catalog role",
        )

    return ArtifactCatalogue(
        identities=MappingProxyType(dict(sorted(identities.items(), key=lambda item: str(item[0])))),
        roles=MappingProxyType(dict(sorted(roles.items(), key=lambda item: str(item[0])))),
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.kind.value, str(item.path), item.message))),
    )


def _mapping_value(record: Mapping[str, object], key: str) -> object:
    """Read one required manifest value without letting a missing key drift."""
    try:
        return record[key]
    except KeyError as error:
        raise ValueError(f"manifest record is missing required {key!r}") from error


def _string_value(record: Mapping[str, object], key: str) -> str:
    """Read one required non-empty manifest string."""
    value = _mapping_value(record, key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manifest record {key!r} must be a non-empty string")
    return value


def _integer_value(record: Mapping[str, object], key: str) -> int:
    """Read one required manifest integer, excluding booleans."""
    value = _mapping_value(record, key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"manifest record {key!r} must be an integer")
    return value


def _date_value(record: Mapping[str, object], key: str) -> date:
    """Normalize a manifest ISO date or timestamp to its acquisition date."""
    value = _string_value(record, key)
    try:
        return date.fromisoformat(value[:10])
    except ValueError as error:
        raise ValueError(f"manifest record {key!r} must begin with an ISO date") from error


def _artefacts_value(manifest: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
    """Return declared artefact rows and reject an untyped manifest shape."""
    value = _mapping_value(manifest, "artefacts")
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise ValueError("manifest 'artefacts' must be a list of objects")
    return cast(Sequence[Mapping[str, object]], value)


def _identity_from_manifest_row(
    row: Mapping[str, object], *, path: PurePosixPath, retrieved_at: date, publisher: str | None
) -> ArtifactIdentity:
    """Construct the common identity shared by official manifest row shapes."""
    return ArtifactIdentity(
        path=path,
        sha256=_string_value(row, "sha256"),
        bytes=_integer_value(row, "bytes"),
        source_url=_string_value(row, "url") if "url" in row else _string_value(row, "source_url"),
        publisher=publisher,
        retrieved_at=_date_value(row, "retrieved_at") if "retrieved_at" in row else retrieved_at,
    )


def record_design_manifest_identities(
    manifest: Mapping[str, object], *, manifest_path: str | PurePosixPath
) -> tuple[ArtifactIdentity, ...]:
    """Normalize one record-design manifest's ``stored_path`` rows."""
    parent = _bundled_path(manifest_path, field_name="manifest_path").parent
    publisher = _string_value(manifest, "source")
    fallback_retrieved_at = _date_value(manifest, "retrieved_at")
    return tuple(
        _identity_from_manifest_row(
            row,
            path=parent / _bundled_path(_string_value(row, "stored_path"), field_name="stored_path"),
            retrieved_at=fallback_retrieved_at,
            publisher=publisher,
        )
        for row in _artefacts_value(manifest)
    )


def manual_manifest_identity(manifest: Mapping[str, object], *, manifest_path: str | PurePosixPath) -> ArtifactIdentity:
    """Normalize one manual manifest, whose source fields live at its top level."""
    parent = _bundled_path(manifest_path, field_name="manifest_path").parent
    relative_pdf_path = _bundled_path(_string_value(manifest, "relative_pdf_path"), field_name="relative_pdf_path")
    return ArtifactIdentity(
        path=parent / relative_pdf_path,
        sha256=_string_value(manifest, "sha256"),
        bytes=_integer_value(manifest, "content_length"),
        source_url=_string_value(manifest, "source_pdf_url"),
        publisher=None,
        retrieved_at=_date_value(manifest, "fetched_at"),
    )


def einvoice_manifest_identities(
    manifest: Mapping[str, object], *, manifest_path: str | PurePosixPath
) -> tuple[ArtifactIdentity, ...]:
    """Normalize the e-invoice schema snapshot's ``path`` rows."""
    parent = _bundled_path(manifest_path, field_name="manifest_path").parent
    publisher = _string_value(manifest, "source")
    retrieved_at = _date_value(manifest, "retrieved_at")
    return tuple(
        _identity_from_manifest_row(
            row,
            path=parent / _bundled_path(_string_value(row, "path"), field_name="path"),
            retrieved_at=retrieved_at,
            publisher=publisher,
        )
        for row in _artefacts_value(manifest)
    )


def registry_source_identity(source: SourceReference) -> ArtifactIdentity:
    """Project registry byte identity without importing its filing semantics."""
    return ArtifactIdentity(
        path=_bundled_path(source.corpus_path, field_name="corpus_path"),
        sha256=str(source.sha256),
        bytes=source.bytes,
        source_url=source.source_url,
        publisher=str(source.authority),
        retrieved_at=source.retrieved_at,
    )


def declared_dispositions(
    declaration: Mapping[str, object], *, declaration_path: str | PurePosixPath
) -> tuple[ArtifactDisposition, ...]:
    """Normalize explicitly named non-payload targets from a declaration.

    URL-only historical exclusions have no bundled target, but still classify
    their declaration file as a disposition.
    """
    catalogued_declaration_path = _bundled_path(declaration_path, field_name="declaration_path")
    parent = catalogued_declaration_path.parent
    if "reason" in declaration:
        reason = _string_value(declaration, "reason")
    else:
        reason = _string_value(declaration, "disposition")
    direct_target = declaration.get("target_path")
    if direct_target is not None:
        if not isinstance(direct_target, str):
            raise ValueError("disposition 'target_path' must be a string")
        return (
            ArtifactDisposition(
                declaration_path=catalogued_declaration_path,
                target_path=_bundled_path(direct_target, field_name="target_path"),
                reason=reason,
            ),
        )

    artefacts = declaration.get("artefacts")
    if artefacts is None:
        return (ArtifactDisposition(declaration_path=catalogued_declaration_path, target_path=None, reason=reason),)
    if not isinstance(artefacts, list) or not all(isinstance(item, Mapping) for item in artefacts):
        raise ValueError("disposition 'artefacts' must be a list of objects")
    return tuple(
        ArtifactDisposition(
            declaration_path=catalogued_declaration_path,
            target_path=parent / _bundled_path(_string_value(row, "stored_path"), field_name="stored_path"),
            reason=reason,
        )
        for row in artefacts
    )
