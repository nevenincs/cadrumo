"""Bucket-scoped append-only event history.

A bucket is the storage slice associated with the active profile.
Material workflow transitions (modelo calculation / verification /
filing, ledger imports, profile lifecycle, etc.) emit immutable
:class:`BucketEvent` records into a bucket-scoped history so the
operator can reconstruct *how* current state was reached, not only
*what* it is now.

Public surface:

* :class:`BucketEvent` — one append-only event record.
* :class:`BucketEventType` — closed catalogue of event kinds.
* :class:`BucketEventHistoryCatalogue` — frozen mapping of every
  event in storage, with bucket / object / type queries.
* :class:`BucketEventHistoryRepository` — encrypted SQL repository
  over :class:`SecureObjectRepository`.
* :func:`derive_bucket_event_id` — deterministic SHA-256 event id.
* :func:`append_bucket_event` — pure helper to insert one event
  into a catalogue (idempotent on identical content).
"""

from __future__ import annotations

from ._errors import (
    BucketBrowseError,
    BucketDeleteRefusedError,
    BucketEventValidationError,
    BucketExportError,
    BucketImportError,
    BucketMaintenanceError,
    BucketRenameError,
    BucketsError,
)
from ._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ._event_repository import (
    BucketEventHistoryPersistenceError,
    BucketEventHistoryRepository,
    append_bucket_event,
)

__all__ = [
    "BucketBrowseError",
    "BucketDeleteRefusedError",
    "BucketEvent",
    "BucketEventHistoryCatalogue",
    "BucketEventHistoryPersistenceError",
    "BucketEventHistoryRepository",
    "BucketEventObjectType",
    "BucketEventType",
    "BucketEventValidationError",
    "BucketExportError",
    "BucketImportError",
    "BucketMaintenanceError",
    "BucketRenameError",
    "BucketsError",
    "append_bucket_event",
    "derive_bucket_event_id",
]
