"""Inert namespace for completed-sync provenance.

The ``records`` and ``persist`` modules own the sync-run contracts and
operations. Cross-package consumers import from those defining modules; this
package initializer exports nothing.

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
