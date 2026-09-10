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
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

__all__ = [
    "ArtifactDiagnostic",
    "ArtifactDiagnosticKind",
    "ArtifactDisposition",
    "ArtifactIdentity",
    "ArtifactRole",
    "DerivedArtifact",
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
class ArtifactDisposition:
    """A non-payload declaration that names its target and the reason for it."""

    target_path: PurePosixPath
    reason: str

    def __post_init__(self) -> None:
        """Require the declared non-payload classification to be actionable."""
        object.__setattr__(self, "target_path", _bundled_path(self.target_path, field_name="target_path"))
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")


@dataclass(frozen=True, slots=True)
class ArtifactDiagnostic:
    """One catalog compilation finding, retained without a boolean collapse."""

    kind: ArtifactDiagnosticKind
    path: PurePosixPath | None
    message: str


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

    URL-only historical exclusions name no bundled target, so return no target
    disposition; the compiler will classify their declaration file separately.
    """
    parent = _bundled_path(declaration_path, field_name="declaration_path").parent
    if "reason" in declaration:
        reason = _string_value(declaration, "reason")
    else:
        reason = _string_value(declaration, "disposition")
    direct_target = declaration.get("target_path")
    if direct_target is not None:
        if not isinstance(direct_target, str):
            raise ValueError("disposition 'target_path' must be a string")
        return (ArtifactDisposition(target_path=_bundled_path(direct_target, field_name="target_path"), reason=reason),)

    artefacts = declaration.get("artefacts")
    if artefacts is None:
        return ()
    if not isinstance(artefacts, list) or not all(isinstance(item, Mapping) for item in artefacts):
        raise ValueError("disposition 'artefacts' must be a list of objects")
    return tuple(
        ArtifactDisposition(
            target_path=parent / _bundled_path(_string_value(row, "stored_path"), field_name="stored_path"),
            reason=reason,
        )
        for row in artefacts
    )
