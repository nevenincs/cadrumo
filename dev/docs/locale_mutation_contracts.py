"""Typed documentation catalogue mutations and refusal contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

_SCHEMA_VERSION: Final[int] = 1


class DocumentationLocaleMutationError(ValueError):
    """Raised when a docs translation manifest cannot be applied safely."""


@dataclass(frozen=True)
class ManifestMessage:
    """One validated message replacement from the manifest."""

    context: str | None
    msgid: str
    expected: str
    replacement: str
    expected_fuzzy: bool
    clear_fuzzy: bool


@dataclass(frozen=True)
class ManifestStale:
    """One exact stale catalogue identity scheduled for removal."""

    context: str | None
    msgid: str
    msgid_plural: str | None


@dataclass(frozen=True)
class ManifestUpdate:
    """One validated catalogue update from the manifest."""

    locale: str
    catalogue: str
    source_sha256: str
    catalogue_sha256: str
    messages: tuple[ManifestMessage, ...]
    remove_stale: tuple[ManifestStale, ...]
    remove_obsolete: tuple[ManifestStale, ...]


@dataclass
class PreparedCatalogue:
    """A validated in-memory Babel catalogue waiting for publication."""

    path: Path
    original: str
    rendered: str
    changed_messages: int
    cleared_fuzzy_messages: int
    removed_stale_messages: int
    removed_obsolete_messages: int
