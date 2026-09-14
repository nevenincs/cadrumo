"""Application-owned capabilities for Modelo work-unit lifecycle operations.

The lifecycle service coordinates the work-unit catalogue with the bucket event
history that records each durable transition.  It receives both authorities as
one required bundle so application code does not construct or discover a
persistence adapter.  Outer composition roots bind the domain protocols to the
secure-object-backed repositories for the requested profile bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


@dataclass(frozen=True, slots=True)
class WorkLifecyclePorts:
    """Required persistence authorities for one bucket-scoped lifecycle call."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class WorkLifecyclePortsFactory(Protocol):
    """Construct the lifecycle authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> WorkLifecyclePorts:
        """Return both required lifecycle authorities for ``bucket_id``."""
        ...


class ActiveWorkLifecyclePortsFactory(Protocol):
    """Construct lifecycle authorities for the active execution profile."""

    def __call__(self) -> WorkLifecyclePorts:
        """Return both required authorities for the active profile."""
        ...


__all__ = [
    "ActiveWorkLifecyclePortsFactory",
    "WorkLifecyclePorts",
    "WorkLifecyclePortsFactory",
]
