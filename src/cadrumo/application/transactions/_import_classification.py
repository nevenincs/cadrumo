"""The one verdict on what an imported row is: new, seen before, or a collision.

Two classifiers once answered this question and disagreed. The diagnostics path
treated a fingerprint repeated WITHIN one file as a duplicate and counted it
skipped; the persisting path deliberately imported both, reasoning that two
identical same-day movements -- a pair of matching retainers or subscriptions --
are two genuine movements, and that dropping one silently under-declares. Since
``--verify`` ran the first and the actual import ran the second, the operator was
warned about a row the import would happily persist, and the preview count was
wrong in the direction that hides money.

The persisting path holds the reasoned position, so it is the one preserved here:
under-declaration is the worse error, and an intra-batch repeat is surfaced as an
ADVISORY the operator can review rather than a skip that removes the row.

The two intra-batch cases are NOT the same, which is the distinction the
diagnostics path was missing entirely:

* a repeated **fingerprint** is two rows describing movements that look alike;
  the provider synthesises a distinct row-index-bearing transaction id for each,
  so both persist, and both must;
* a repeated **transaction id** is two rows resolving to the same catalogue key.
  The later would overwrite the earlier, so only one can persist and the count
  must say so.

See Also:
    :class:`~cadrumo.application.transactions.LedgerImportDiagnosticKind`
        The category an unimported verdict is reported under.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from enum import StrEnum

__all__ = ["ImportRowVerdict", "classify_import_row"]


class ImportRowVerdict(StrEnum):
    """What one parsed row is, relative to the catalogue and the rest of its batch."""

    NEW = "new"
    """Not seen in the catalogue nor earlier in this batch. Imports."""

    DUPLICATE_OF_STORED = "duplicate-of-stored"
    """Its fingerprint is already in the catalogue -- the same movement seen before.

    A re-imported statement, or the same movement re-exported in another file
    format. Skipped: the fingerprint survives later edits, so this recognises the
    row even after the stored copy was amended.
    """

    REPEATED_IN_BATCH = "repeated-in-batch"
    """An earlier row in this same file carries the same fingerprint. Still imports.

    Two identical same-day movements are two movements. Reported as an advisory so
    the operator can rule out a genuine double-count in the source file, never
    dropped on their behalf.
    """

    COLLIDING_TRANSACTION_ID = "colliding-transaction-id"
    """An earlier row in this batch resolves to the same transaction id. Skipped.

    The catalogue keys on that id, so the later row would overwrite the earlier
    one. Only one can persist and the count says one.
    """

    @property
    def imports(self) -> bool:
        """Return whether a row with this verdict is persisted.

        The single place the import/skip split is decided, so a caller counting
        skips and a caller building rows cannot drift apart.
        """
        return self in {ImportRowVerdict.NEW, ImportRowVerdict.REPEATED_IN_BATCH}


def classify_import_row(
    *,
    fingerprint: str,
    transaction_id: str,
    stored_fingerprints: AbstractSet[str],
    batch_fingerprints: AbstractSet[str],
    batch_transaction_ids: AbstractSet[str],
) -> ImportRowVerdict:
    """Return the verdict for one parsed row.

    Pure: it reads the three sets and nothing else, so both the preview and the
    persisting path reach the same answer from the same inputs.

    Args:
        fingerprint: The row's stable import fingerprint, derived by the caller
            with the direction the provider read at the parse boundary.
        transaction_id: The row's derived catalogue key.
        stored_fingerprints: Every fingerprint already in the catalogue.
        batch_fingerprints: Fingerprints of the rows classified so far in this
            batch, in document order.
        batch_transaction_ids: Transaction ids of the rows ACCEPTED so far in
            this batch.

    Returns:
        The verdict. Order matters: an already-stored fingerprint is a re-import
        whatever else the batch contains, and an id collision outranks a
        fingerprint repeat because it is the one that cannot persist.
    """
    if fingerprint in stored_fingerprints:
        return ImportRowVerdict.DUPLICATE_OF_STORED
    if transaction_id in batch_transaction_ids:
        return ImportRowVerdict.COLLIDING_TRANSACTION_ID
    if fingerprint in batch_fingerprints:
        return ImportRowVerdict.REPEATED_IN_BATCH
    return ImportRowVerdict.NEW
