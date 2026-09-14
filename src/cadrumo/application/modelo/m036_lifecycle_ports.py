"""Application-owned capabilities for the Modelo 036 declaration lifecycle.

The M036 application service owns declaration validation, sequencing, and event
derivation.  This module is the inward contract for the persistence and
bucket-event capabilities it requires; executable composition supplies the
bucket-scoped implementation and the outward adapter translates storage
failures before they cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ...core.secure_object_write import SecureObjectWrite
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol

if TYPE_CHECKING:
    from .m036_lifecycle import M036DeclarationResult


class M036DeclarationPersistenceError(RuntimeError):
    """Translated failure from a declaration persistence capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"m036 declaration persistence operation failed: {operation}")


class M036DeclarationRepositoryPort(Protocol):
    """Required encrypted-record operations for one Modelo 036 bucket."""

    def exists(self, declaration_id: str) -> bool:
        """Return whether the addressed declaration exists."""
        ...

    def load(self, declaration_id: str) -> M036DeclarationResult:
        """Load one declaration by its full content-addressed identifier."""
        ...

    def list_snapshots(self) -> tuple[M036DeclarationResult, ...]:
        """List every declaration stored for the bound bucket."""
        ...

    def resolve(self, declaration_id: str) -> M036DeclarationResult:
        """Resolve one full identifier or an unambiguous identifier prefix."""
        ...

    def save(self, declaration: M036DeclarationResult) -> None:
        """Persist one declaration record."""
        ...

    def save_with_secure_object_writes(
        self,
        declaration: M036DeclarationResult,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist a declaration atomically with its related event-history writes."""
        ...


@dataclass(frozen=True, slots=True)
class M036LifecyclePorts:
    """Required authorities for one bucket-scoped M036 lifecycle call."""

    declaration_repository: M036DeclarationRepositoryPort
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class M036LifecyclePortsFactory(Protocol):
    """Construct the complete M036 lifecycle capability bundle."""

    def __call__(self, *, bucket_id: str) -> M036LifecyclePorts:
        """Return all authorities required for the requested bucket."""
        ...


__all__ = [
    "M036DeclarationPersistenceError",
    "M036DeclarationRepositoryPort",
    "M036LifecyclePorts",
    "M036LifecyclePortsFactory",
]
