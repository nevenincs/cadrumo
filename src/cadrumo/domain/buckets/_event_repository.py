"""Domain boundary error and pure helper for the bucket-event-history catalogue.

:class:`BucketEventHistoryPersistenceError` is the storage-boundary error the
persistence adapter raises when the encrypted
:class:`BucketEventHistoryCatalogue` cannot be loaded or persisted safely;
:func:`append_bucket_event` is the pure insertion helper over a catalogue. The
concrete encrypted-SQL repository lives in the persistence adapter
(:class:`cadrumo.adapters.persistence.profile.buckets.BucketEventHistoryRepository`),
behind :class:`BucketEventHistoryRepositoryProtocol`; this module owns only the
domain error and the pure helper.
"""

from __future__ import annotations

from ._errors import BucketsError
from ._event import BucketEvent, BucketEventHistoryCatalogue


class BucketEventHistoryPersistenceError(BucketsError):
    """Raised when the bucket-event-history catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from the persistence adapter's
    :class:`cadrumo.adapters.persistence.profile.buckets.BucketEventHistoryRepository`
    while preserving translated recovery context for callers.
    """


def append_bucket_event(catalogue: BucketEventHistoryCatalogue, event: BucketEvent) -> BucketEventHistoryCatalogue:
    """Return a new :class:`BucketEventHistoryCatalogue` with ``event`` inserted.

    Content-addressed: a re-emission of the same :class:`BucketEvent` collapses
    to the same ``event_id`` and the existing entry is left in place.
    """
    mapping = dict(catalogue.events)
    mapping[event.event_id] = event
    return BucketEventHistoryCatalogue(events=mapping)


__all__ = [
    "BucketEventHistoryPersistenceError",
    "append_bucket_event",
]
