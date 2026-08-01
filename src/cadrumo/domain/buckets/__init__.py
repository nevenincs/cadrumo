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
* :class:`BucketEventHistoryRepositoryProtocol` — narrow read/write
  port over the catalogue; the concrete encrypted-SQL implementation
  (:class:`adapters.persistence.profile.buckets.BucketEventHistoryRepository`)
  lives in the persistence adapter and stores a ``FINANCIAL``
  :class:`adapters.persistence.storage.Envelope` singleton through
  :class:`adapters.persistence.storage.SecureObjectRepository`.
* :func:`derive_bucket_event_id` — deterministic SHA-256 event id.
* :func:`append_bucket_event` — pure helper to insert one event
  into a catalogue (idempotent on identical content).
* :func:`emit_bucket_event` — the derive-append-save primitive every
  emitting domain shares, so no caller re-derives the id contract.
  ``payload_version`` is required: each domain versions its own payload,
  and that field alone is outside the derived id, so it cannot be
  defaulted here without silently misdeclaring some domain's contract.

The adapter repository also exposes a ``to_secure_object_write`` method so
sibling catalogue updates can co-emit the same encrypted event-history write.
Ordinary operators consume this history through profile and application services
such as :mod:`application.bucket_maintenance`; this domain facade does not create
an operator-facing bucket command root.

See Also:
    :class:`BucketEvent`
        Append-only event record emitted by workflow, modelo, ledger, profile,
        and bucket-maintenance transitions.
    :class:`BucketEventHistoryRepositoryProtocol`
        Narrow read/write port for the append-only history; its concrete
        encrypted per-bucket implementation lives in the persistence adapter.
    :class:`BucketEventHistoryPersistenceError`
        Storage-boundary error raised when the encrypted catalogue cannot be
        loaded or persisted safely.
    :mod:`application.bucket_maintenance`
        Application facade that composes profile lifecycle operations and emits
        bucket-maintenance events through this domain history.
    :mod:`application.workflow`
        Active-profile state and bucket-pointer workflows that provide the
        current storage slice observed by bucket event consumers.
    :mod:`application.modelo`
        Work-unit calculation, verification, filing, import, export, and
        reconciliation services that emit modelo events while persisting
        modelo catalogues separately.
    :mod:`application.ledger`
        Ledger transaction lifecycle that emits bucket events for imports,
        edits, classifications, evidence attachment, and removal.
    :mod:`application.invoices`
        Invoice import, reconciliation, and ledger-link workflows whose events
        reference invoice and transaction objects without replacing catalogues.
"""

from __future__ import annotations

from ._errors import (
    BucketArchiveRefusedError,
    BucketBrowseError,
    BucketDeleteRefusedError,
    BucketEventValidationError,
    BucketExportError,
    BucketImportError,
    BucketMaintenanceError,
    BucketRenameError,
    BucketRestoreRefusedError,
    BucketsError,
)
from ._event import (
    BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH,
    BucketActorLabel,
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventId,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
    payload_value_fits,
)
from ._event_repository import (
    BucketEventHistoryPersistenceError,
    append_bucket_event,
    emit_bucket_event,
)
from ._protocols import BucketEventHistoryRepositoryProtocol

__all__ = [
    "BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH",
    "BucketActorLabel",
    "BucketArchiveRefusedError",
    "BucketBrowseError",
    "BucketDeleteRefusedError",
    "BucketEvent",
    "BucketEventHistoryCatalogue",
    "BucketEventHistoryPersistenceError",
    "BucketEventHistoryRepositoryProtocol",
    "BucketEventId",
    "BucketEventObjectType",
    "BucketEventType",
    "BucketEventValidationError",
    "BucketExportError",
    "BucketImportError",
    "BucketMaintenanceError",
    "BucketRenameError",
    "BucketRestoreRefusedError",
    "BucketsError",
    "append_bucket_event",
    "derive_bucket_event_id",
    "emit_bucket_event",
    "payload_value_fits",
]
