"""Bucket-event history exposed through an application-owned failure contract.

Several declaration lifecycles commit their bucket events beside their own
records. Each binds the same encrypted history repository to the application
port and differs only in which application error a storage failure becomes, so
the binding is written once and the translation is supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, override

from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from .buckets import BucketEventHistoryRepository


class AdapterFailureTranslator(Protocol):
    """Run one adapter operation, re-raising storage failures as an application error."""

    def __call__[T](self, operation: str, action: Callable[[], T], /) -> T:
        """Return ``action()`` or raise the caller's application-contract error."""
        ...


class TranslatedBucketEventHistoryRepository(BucketEventHistoryRepositoryProtocol):
    """Translate bucket-event persistence to one application contract."""

    def __init__(self, *, repository: BucketEventHistoryRepository, translate: AdapterFailureTranslator) -> None:
        """Bind the encrypted history repository and the caller's failure translation."""
        self._repository = repository
        self._translate = translate

    @override
    def exists(self) -> bool:
        """Report event-history presence without exposing storage failures."""
        return self._translate("bucket_event_history_exists", self._repository.exists)

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        """Load event history through the application-facing port."""
        return self._translate("bucket_event_history_load", self._repository.load)

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Load event history together with its optimistic-concurrency revision."""
        return self._translate("bucket_event_history_load_revisioned", self._repository.load_revisioned)

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist event history while translating storage failures."""
        self._translate("bucket_event_history_save", lambda: self._repository.save(catalogue))

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare an event-history secure write for an atomic commit."""
        return self._translate(
            "bucket_event_history_prepare_write",
            lambda: self._repository.to_secure_object_write(
                catalogue,
                expected_revision_id=expected_revision_id,
            ),
        )


__all__ = ["AdapterFailureTranslator", "TranslatedBucketEventHistoryRepository"]
