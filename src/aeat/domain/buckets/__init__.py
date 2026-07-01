"""Public facade for bucket-scoped append-only event history.

A bucket is the storage slice associated with the active profile.
Material workflow transitions (modelo calculation / verification /
filing, ledger imports, profile lifecycle, etc.) emit immutable
:class:`BucketEvent` records into a bucket-scoped history so the
operator can reconstruct *how* current state was reached, not only
*what* it is now. The history is audit context, not the source of
relational truth for ledger, profile, modelo, or filing state.
Those domains keep their current-state catalogues; bucket history preserves the
structured transition record and object references that tie them together.

Each :class:`BucketEvent` is content-addressed by bucket id,
:class:`BucketEventType`, occurrence time, actor,
:class:`BucketEventObjectType`, object id, and payload. ``payload_version``
tracks the per-event payload contract, while the closed event and object
taxonomies prevent emitters from persisting ad-hoc strings.

Public surface:

* :class:`BucketEvent` — one append-only event record.
* :class:`BucketEventType` — closed catalogue of event kinds.
* :class:`BucketEventObjectType` — closed catalogue of affected object kinds.
* :class:`BucketEventHistoryCatalogue` — frozen mapping of every
  event in storage, with bucket / object / type queries.
* :class:`BucketEventHistoryRepository` — encrypted SQL repository
  over
  :class:`~aeat.adapters.persistence.storage.SecureObjectRepository`,
  storing a ``FINANCIAL``
  :class:`~aeat.adapters.persistence.storage.Envelope` singleton.
* :func:`derive_bucket_event_id` — deterministic SHA-256 event id.
* :func:`append_bucket_event` — pure helper to insert one event
  into a catalogue (idempotent on identical content).

The repository also exposes
:meth:`BucketEventHistoryRepository.to_secure_object_write` so sibling
catalogue updates can co-emit the same encrypted event-history write. Ordinary
operators consume this history through profile and application services such as
:mod:`~aeat.application.bucket_maintenance`; this domain facade does not create
an operator-facing bucket command root.

See Also:
    :class:`BucketEvent`
        Append-only event record emitted by workflow, modelo, ledger, profile,
        and bucket-maintenance transitions.
    :class:`BucketEventHistoryRepository`
        Encrypted per-bucket repository for the append-only history.
    :class:`~aeat.domain.buckets.BucketEventHistoryPersistenceError`
        Storage-boundary error raised when the encrypted catalogue cannot be
        loaded or persisted safely.
    :mod:`~aeat.application.bucket_maintenance`
        Application facade that composes profile lifecycle operations and emits
        bucket-maintenance events through this domain history.
    :mod:`~aeat.application.workflow`
        Active-profile state and bucket-pointer workflows that provide the
        current storage slice observed by bucket event consumers.
    :mod:`aeat.application.modelo`
        Work-unit calculation, verification, filing, import, export, and
        reconciliation services that emit modelo events while persisting
        modelo catalogues separately.
    :mod:`aeat.application.ledger`
        Ledger transaction lifecycle that emits bucket events for imports,
        edits, classifications, evidence attachment, and removal.
    :mod:`aeat.application.invoices`
        Invoice import, reconciliation, and ledger-link workflows whose events
        reference invoice and transaction objects without replacing catalogues.
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
from ._protocols import BucketEventHistoryRepositoryProtocol

__all__ = [
    "BucketBrowseError",
    "BucketDeleteRefusedError",
    "BucketEvent",
    "BucketEventHistoryCatalogue",
    "BucketEventHistoryPersistenceError",
    "BucketEventHistoryRepository",
    "BucketEventHistoryRepositoryProtocol",
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
