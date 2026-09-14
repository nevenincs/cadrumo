"""Persistence adapters for the Modelo 145 communication-record capability.

The application service speaks only the focused records ports.  This module
binds those ports to the existing secure-object and bucket-event repositories,
translating their storage failures and keeping their envelope/blob details
outside the application boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, override

from ....application.modelo.m145_communication_records import (
    M145CommunicationRecord,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordNotFoundError,
    m145_communication_record_object_key,
)
from ....application.modelo.m145_communication_records_ports import (
    M145CommunicationRecordPersistenceError,
    M145CommunicationRecordRepositoryPort,
    M145CommunicationRecordsPorts,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.errors import BucketEventValidationError
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.buckets.event_repository import BucketEventHistoryPersistenceError
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..storage.secure_object_namespaces import M145_COMMUNICATION_RECORD_NAMESPACE
from .buckets import BucketEventHistoryRepository
from .snapshots import SecureSnapshotRepository


class _M145AdapterInputError(CadrumoError):
    """Adapter-only invariant error consumed by the translation boundary."""


T = TypeVar("T")


def _translate_adapter_failure(operation: str, action: Callable[[], T]) -> T:
    """Run one adapter operation and expose only the application contract."""
    try:
        return action()
    except (
        M145CommunicationRecordPersistenceError,
        M145CommunicationRecordNotFoundError,
        M145CommunicationRecordAmbiguousError,
        BucketEventValidationError,
    ):
        raise
    except (BucketEventHistoryPersistenceError, CadrumoError, OSError, ValueError, TypeError, KeyError) as exc:
        raise M145CommunicationRecordPersistenceError(operation) from exc


def _record_not_found(communication_record_id: str) -> M145CommunicationRecordNotFoundError:
    """Build the application lookup-miss error for the generic repository."""
    return M145CommunicationRecordNotFoundError(
        f"Modelo 145 communication record {communication_record_id!r} not found",
        context={"communication_record_id": communication_record_id},
    )


def _record_ambiguous(
    communication_record_id: str,
    full_ids: tuple[str, ...],
) -> M145CommunicationRecordAmbiguousError:
    """Build the application ambiguous-prefix error for the generic repository."""
    return M145CommunicationRecordAmbiguousError(
        f"Modelo 145 communication record prefix {communication_record_id!r} is ambiguous; matches {list(full_ids)!r}",
        context={"communication_record_id": communication_record_id, "match_count": len(full_ids)},
    )


class M145CommunicationRecordRepositoryAdapter(M145CommunicationRecordRepositoryPort):
    """Translate the generic secure snapshot repository to the records port."""

    def __init__(self, *, repository: SecureSnapshotRepository[M145CommunicationRecord]) -> None:
        self._repository = repository

    @override
    def exists(self, communication_record_id: str) -> bool:
        """Report record presence without exposing storage failures."""
        return _translate_adapter_failure(
            "communication_record_exists",
            lambda: self._repository.exists(communication_record_id),
        )

    @override
    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        """Load one record by full id while preserving application lookup errors."""
        return _translate_adapter_failure(
            "communication_record_load",
            lambda: self._repository.load(communication_record_id),
        )

    @override
    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        """Resolve one full id or unique prefix while hiding adapter errors."""
        return _translate_adapter_failure(
            "communication_record_resolve",
            lambda: self._repository.resolve(communication_record_id),
        )

    @override
    def save_with_secure_object_writes(
        self,
        record: M145CommunicationRecord,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Commit a record and its related secure writes atomically."""
        _translate_adapter_failure(
            "communication_record_save",
            lambda: self._repository.save_with_secure_object_writes(record, extra_writes),
        )


class M145CommunicationEventRepositoryAdapter(BucketEventHistoryRepositoryProtocol):
    """Translate bucket-event persistence to the records application contract."""

    def __init__(self, *, repository: BucketEventHistoryRepository) -> None:
        self._repository = repository

    @override
    def exists(self) -> bool:
        """Report event-history presence without exposing storage failures."""
        return _translate_adapter_failure("bucket_event_history_exists", self._repository.exists)

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        """Load event history through the application-facing port."""
        return _translate_adapter_failure("bucket_event_history_load", self._repository.load)

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Load event history together with its optimistic-concurrency revision."""
        return _translate_adapter_failure("bucket_event_history_load_revisioned", self._repository.load_revisioned)

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist event history while translating storage failures."""
        _translate_adapter_failure("bucket_event_history_save", lambda: self._repository.save(catalogue))

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare an event-history secure write for an atomic record commit."""
        return _translate_adapter_failure(
            "bucket_event_history_prepare_write",
            lambda: self._repository.to_secure_object_write(
                catalogue,
                expected_revision_id=expected_revision_id,
            ),
        )

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        """Append through the existing revision guard."""
        return _translate_adapter_failure(
            "bucket_event_history_append",
            lambda: self._repository.append_guarded(appender, attempts=attempts),
        )


def build_m145_communication_records_ports(*, bucket_id: str) -> M145CommunicationRecordsPorts:
    """Bind secure record and event repositories for one profile bucket."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return M145CommunicationRecordsPorts(
        record_repository=M145CommunicationRecordRepositoryAdapter(
            repository=SecureSnapshotRepository(
                bucket_id=normalized_bucket_id,
                payload_model=M145CommunicationRecord,
                namespace_definition=M145_COMMUNICATION_RECORD_NAMESPACE,
                object_key=m145_communication_record_object_key,
                not_found_factory=_record_not_found,
                ambiguous_prefix_factory=_record_ambiguous,
                domain_label="m145_communication_record",
                input_error_cls=_M145AdapterInputError,
                objects=objects,
            ),
        ),
        bucket_event_repository=M145CommunicationEventRepositoryAdapter(
            repository=BucketEventHistoryRepository(objects=objects),
        ),
    )


__all__ = [
    "M145CommunicationEventRepositoryAdapter",
    "M145CommunicationRecordRepositoryAdapter",
    "build_m145_communication_records_ports",
]
