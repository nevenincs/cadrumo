"""Typed, read-only identity records for bundled corpus artifacts.

This module deliberately does not resolve registry authority or read a corpus
tree.  It gives acquisition, derivation, and coverage tooling one vocabulary
for the facts they share.  Filing consumers continue to use
``ValidatedRegistryAuthority`` and ``SourceReference``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import PurePosixPath
from urllib.parse import urlparse

__all__ = [
    "ArtifactDiagnostic",
    "ArtifactDiagnosticKind",
    "ArtifactDisposition",
    "ArtifactIdentity",
    "ArtifactRole",
    "DerivedArtifact",
]


_SHA256 = re.compile(r"[0-9a-f]{64}")


def _bundled_path(value: PurePosixPath, *, field_name: str) -> PurePosixPath:
    """Validate and return a canonical bundled-data-relative POSIX path."""
    raw = str(value)
    path = PurePosixPath(raw)
    if not raw or "\\" in raw or path.is_absolute() or any(part in {".", ".."} for part in path.parts):
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
