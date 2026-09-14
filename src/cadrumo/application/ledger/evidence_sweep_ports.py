"""Application-owned capabilities and boundary values for evidence sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError


@dataclass(frozen=True, slots=True)
class EvidenceSweepDocument:
    """The document metadata the application needs from a folder listing."""

    file_id: str
    name: str
    mime_type: str


class EvidenceSweepFileNotReachableError(CadrumoError):
    """The provider refused one file under the currently granted scope."""


class EvidenceSweepFetcher(Protocol):
    """Capability that fetches and stores one listed evidence document."""

    def __call__(self, document: EvidenceSweepDocument) -> str:
        """Return the stored attachment identifier for ``document``."""
        ...


__all__ = [
    "EvidenceSweepDocument",
    "EvidenceSweepFetcher",
    "EvidenceSweepFileNotReachableError",
]
