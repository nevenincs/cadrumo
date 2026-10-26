"""Application-owned capability for deriving evidence shape from content bytes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...core.document_shape import DocumentShape


class EvidenceDocumentShapeProbe(Protocol):
    """Read-only capability that classifies evidence by its own bytes."""

    def __call__(self, data: bytes) -> DocumentShape:
        """Return the content-derived shape for ``data``."""
        ...


@dataclass(frozen=True, slots=True)
class EvidenceInputPorts:
    """Required capabilities for resolving stored evidence into memory."""

    document_shape_probe: EvidenceDocumentShapeProbe


__all__ = ["EvidenceDocumentShapeProbe", "EvidenceInputPorts"]
