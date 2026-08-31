"""Last-sync provenance: the typed record of a completed synchronisation run.

The public facade for the sync-run store. The parent
:mod:`application.storage` package is a namespace container that re-exports
nothing by design, so every cross-package consumer imports from here rather
than from the parent or from a private module.

The store answers "when was this surface last synchronised, and how much did
that run actually cover". It replaces reading provenance off whatever the
remote surface stamps on itself -- a remote stamp answers when the far side
last changed, which is a different question, and is unavailable entirely when a
run fails partway.

See Also:
    :class:`~core.SyncSurface`
        The closed two-member set of surfaces a run can cover.
    :data:`~adapters.persistence.storage.SYNC_RUN_RECORDS_NAMESPACE`
        Encrypted profile-local namespace these records are written to, whose
        key grammar keeps every run distinct rather than collapsing to a last
        one.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        The single-writer batch primitive a caller co-writes the record and its
        bucket event through, by binding both repositories to one instance.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
