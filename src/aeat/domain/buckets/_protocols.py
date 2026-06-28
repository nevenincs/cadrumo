"""Domain-level repository Protocol for the bucket-event-history catalogue.

Application-layer code that persists or loads bucket event catalogues
depends on this Protocol, not on the concrete adapter-backed
``BucketEventHistoryRepository``. This keeps the domain layer free of
adapter imports while still providing a typed port surface.

:class:`BucketEventHistoryRepositoryProtocol` abstracts ``exists`` / ``load`` /
``save`` operations over :class:`BucketEventHistoryCatalogue`, allowing
services to emit :class:`BucketEvent` history without importing the concrete
:class:`aeat.domain.buckets.BucketEventHistoryRepository`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._event import BucketEventHistoryCatalogue


@runtime_checkable
class BucketEventHistoryRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the bucket-event-history catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket event-history catalogue satisfies this protocol. The concrete
    secure-object-backed implementation lives in ``_event_repository.py``.
    """

    def exists(self) -> bool:
        """Return whether an event-history catalogue has been persisted."""
        ...

    def load(self) -> BucketEventHistoryCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The :class:`BucketEventHistoryCatalogue` loaded from storage.
        """
        ...

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist ``catalogue`` in the encrypted database object store."""
        ...


__all__ = ["BucketEventHistoryRepositoryProtocol"]
