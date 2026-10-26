"""Application-owned capabilities for evidence-bundle verification.

The evidence service works with validated bundle models and a bucket-bound
work-unit existence check.  Encrypted storage and catalogue adapters are
composed outside the application package and implement these narrow contracts.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from .models import EvidenceBundle


class EvidenceBundlePersistenceError(CadrumoError):
    """Translated failure from an evidence-bundle persistence capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"evidence bundle persistence operation failed: {operation}")


class EvidenceBundleRepositoryPort(Protocol):
    """Bucket-bound persistence capability for evidence-bundle manifests."""

    def load(self, identifier: str) -> EvidenceBundle | None:
        """Load one bundle by its complete storage identifier."""
        ...

    def save(self, payload: EvidenceBundle) -> None:
        """Persist one validated bundle manifest."""
        ...

    def iter_records(self) -> Iterator[EvidenceBundle]:
        """Iterate persisted bundle manifests with integrity checks."""
        ...


class EvidenceBundleWorkUnitPort(Protocol):
    """Bucket-bound capability that answers whether a work unit exists."""

    def exists(self, work_unit_id: str) -> bool:
        """Return whether ``work_unit_id`` is present in the work-unit catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class EvidenceBundlePorts:
    """Required authorities for one evidence-bundle service invocation."""

    repository: EvidenceBundleRepositoryPort
    work_units: EvidenceBundleWorkUnitPort


__all__ = [
    "EvidenceBundlePersistenceError",
    "EvidenceBundlePorts",
    "EvidenceBundleRepositoryPort",
    "EvidenceBundleWorkUnitPort",
]
