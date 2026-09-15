"""Persistence adapters for the Modelo 036 declaration lifecycle capability.

The application service speaks only the focused M036 lifecycle ports.  This
module binds those ports to the existing secure-object and bucket-event
repositories, translating storage failures and keeping envelope, namespace,
and object-store details outside the application boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, override

from ....application.modelo.m036_lifecycle import (
    M036DeclarationAmbiguousError,
    M036DeclarationNotFoundError,
    M036DeclarationResult,
    m036_declaration_object_key,
)
from ....application.modelo.m036_lifecycle_ports import (
    M036DeclarationPersistenceError,
    M036DeclarationRepositoryPort,
    M036LifecyclePorts,
)
from ....core.errors.hierarchy import CadrumoError
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.errors import BucketEventValidationError
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.buckets.event_repository import BucketEventHistoryPersistenceError
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ..storage.secure_object_namespaces import LIVE_M036_DECLARATION_NAMESPACE
from .buckets import BucketEventHistoryRepository
from .snapshots import SecureSnapshotRepository


class _M036AdapterInputError(CadrumoError):
    """Adapter-only invariant error consumed by the translation boundary."""


T = TypeVar("T")


def _translate_adapter_failure[T](operation: str, action: Callable[[], T]) -> T:
    """Run one adapter operation and expose only the application contract."""
    try:
        return action()
    except (
        M036DeclarationPersistenceError,
        M036DeclarationNotFoundError,
        M036DeclarationAmbiguousError,
        BucketEventValidationError,
    ):
        raise
    except (BucketEventHistoryPersistenceError, CadrumoError, OSError, ValueError, TypeError, KeyError) as exc:
        raise M036DeclarationPersistenceError(operation) from exc


def _record_not_found(declaration_id: str) -> M036DeclarationNotFoundError:
    """Build the application lookup-miss error for the generic repository."""
    return M036DeclarationNotFoundError(f"M036 declaration {declaration_id!r} not found")


def _record_ambiguous(
    declaration_id: str,
    full_ids: tuple[str, ...],
) -> M036DeclarationAmbiguousError:
    """Build the application ambiguous-prefix error for the generic repository."""
    return M036DeclarationAmbiguousError(
        f"M036 declaration prefix {declaration_id!r} is ambiguous; matches {list(full_ids)!r}",
    )


class M036DeclarationRepositoryAdapter(M036DeclarationRepositoryPort):
    """Translate the generic secure snapshot repository to the M036 port."""

    def __init__(self, *, repository: SecureSnapshotRepository[M036DeclarationResult]) -> None:
        """Bind the encrypted Modelo 036 declaration repository."""
        self._repository = repository

    @override
    def exists(self, declaration_id: str) -> bool:
        """Report declaration presence without exposing storage failures."""
        return _translate_adapter_failure(
            "m036_declaration_exists",
            lambda: self._repository.exists(declaration_id),
        )

    @override
    def load(self, declaration_id: str) -> M036DeclarationResult:
        """Load one declaration by full id while preserving lookup errors."""
        return _translate_adapter_failure(
            "m036_declaration_load",
            lambda: self._repository.load(declaration_id),
        )

    @override
    def list_snapshots(self) -> tuple[M036DeclarationResult, ...]:
        """List declarations while translating malformed storage failures."""
        return _translate_adapter_failure("m036_declaration_list", self._repository.list_snapshots)

    @override
    def resolve(self, declaration_id: str) -> M036DeclarationResult:
        """Resolve one full id or unique prefix while hiding adapter errors."""
        return _translate_adapter_failure(
            "m036_declaration_resolve",
            lambda: self._repository.resolve(declaration_id),
        )

    @override
    def save(self, declaration: M036DeclarationResult) -> None:
        """Persist one declaration through the secure-object repository."""
        _translate_adapter_failure(
            "m036_declaration_save",
            lambda: self._repository.save(declaration),
        )

    @override
    def save_with_secure_object_writes(
        self,
        declaration: M036DeclarationResult,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Commit a declaration and its related secure writes atomically."""
        _translate_adapter_failure(
            "m036_declaration_save",
            lambda: self._repository.save_with_secure_object_writes(declaration, extra_writes),
        )


class M036BucketEventRepositoryAdapter(BucketEventHistoryRepositoryProtocol):
    """Translate bucket-event persistence to the M036 application contract."""

    def __init__(self, *, repository: BucketEventHistoryRepository) -> None:
        """Bind the encrypted bucket-event history repository."""
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
        """Prepare an event-history secure write for an atomic declaration commit."""
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


def build_m036_lifecycle_ports(*, bucket_id: str) -> M036LifecyclePorts:
    """Bind secure declaration and event repositories for one profile bucket."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return M036LifecyclePorts(
        declaration_repository=M036DeclarationRepositoryAdapter(
            repository=SecureSnapshotRepository(
                bucket_id=normalized_bucket_id,
                payload_model=M036DeclarationResult,
                namespace_definition=LIVE_M036_DECLARATION_NAMESPACE,
                object_key=m036_declaration_object_key,
                not_found_factory=_record_not_found,
                ambiguous_prefix_factory=_record_ambiguous,
                domain_label="m036_declaration",
                input_error_cls=_M036AdapterInputError,
                objects=objects,
            ),
        ),
        bucket_event_repository=M036BucketEventRepositoryAdapter(
            repository=BucketEventHistoryRepository(objects=objects),
        ),
    )


__all__ = [
    "M036BucketEventRepositoryAdapter",
    "M036DeclarationRepositoryAdapter",
    "build_m036_lifecycle_ports",
]
