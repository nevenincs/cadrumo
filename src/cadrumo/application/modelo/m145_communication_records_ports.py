"""Application-owned capabilities for Modelo 145 communication records.

The communication-record service owns the record DTOs, validation policy, and
state transitions.  Persistence and secure-object details stay outside this
package: an executable composition root supplies this required bundle for the
active bucket, and the outward adapter translates storage failures before they
cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.secure_object_write import SecureObjectWrite
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol

if TYPE_CHECKING:
    from .m145_communication_records import M145CommunicationRecord


class M145CommunicationRecordPersistenceError(CadrumoError):
    """Translated failure from a communication-record persistence capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"m145 communication record persistence operation failed: {operation}")


class M145CommunicationRecordRepositoryPort(Protocol):
    """Required encrypted-record operations for one Modelo 145 bucket."""

    def exists(self, communication_record_id: str) -> bool:
        """Return whether the addressed communication record exists."""
        ...

    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        """Load one record by its full content-addressed identifier."""
        ...

    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        """Resolve one full identifier or an unambiguous identifier prefix."""
        ...

    def save_with_secure_object_writes(
        self,
        record: M145CommunicationRecord,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist a record atomically with its related event-history writes."""
        ...


@dataclass(frozen=True, slots=True)
class M145CommunicationRecordsPorts:
    """Required authorities for one bucket-scoped communication-record call."""

    record_repository: M145CommunicationRecordRepositoryPort
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class M145CommunicationRecordsPortsFactory(Protocol):
    """Construct the complete communication-record capability bundle."""

    def __call__(self, *, bucket_id: str) -> M145CommunicationRecordsPorts:
        """Return all authorities required for the requested bucket."""
        ...


__all__ = [
    "M145CommunicationRecordPersistenceError",
    "M145CommunicationRecordRepositoryPort",
    "M145CommunicationRecordsPorts",
    "M145CommunicationRecordsPortsFactory",
]
