"""Domain-level repository Protocol for the bucket-event-history catalogue.

Application-layer code that persists or loads bucket event catalogues
depends on :class:`BucketEventHistoryRepositoryProtocol`, not on the concrete
secure-object-backed :class:`BucketEventHistoryRepository`. This keeps callers
typed against the narrow port while the concrete repository owns the adapter
integration.

:class:`BucketEventHistoryRepositoryProtocol` abstracts ``exists`` / ``load`` /
``save`` operations over :class:`BucketEventHistoryCatalogue`, allowing
services to emit :class:`BucketEvent` history without importing the concrete
:class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._event import BucketEventHistoryCatalogue


@runtime_checkable
class BucketEventHistoryRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the bucket-event-history catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`BucketEventHistoryCatalogue` satisfies this protocol. The
    production implementation is :class:`BucketEventHistoryRepository`.
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
        """Persist ``catalogue`` in the encrypted database object store.

        Args:
            catalogue: The :class:`BucketEventHistoryCatalogue` to persist.
        """
        ...


__all__ = ["BucketEventHistoryRepositoryProtocol"]
