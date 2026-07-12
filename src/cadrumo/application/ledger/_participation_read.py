"""Read action: surface the modelo participations of one ledger transaction.

The inverse of the forward ``source_transaction_ids`` link. Loads the
per-transaction :class:`TransactionRevisionParticipationIndex` from encrypted
storage and returns it for the CLI surface to project into a typed payload. The
index records only finalized-revision participations (borrador inclusion is
deferred), so the read is the audit-trail answer to "where was this transaction
declared".
"""

from __future__ import annotations

from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...domain.modelos import TransactionRevisionParticipationIndex


def get_transaction_participation(
    *,
    transaction_id: str,
    bucket_id: str | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
) -> TransactionRevisionParticipationIndex:
    """Return the finalized-revision participation index for one ledger transaction.

    Returns an empty :class:`TransactionRevisionParticipationIndex` (no
    participations) when the transaction has never contributed to a finalized
    revision, rather than raising — an auditable "no declarations" answer.

    Args:
        transaction_id: The ledger transaction id to look up.
        bucket_id: Optional explicit profile bucket; resolves the active bucket
            when omitted.
        participation_index_repository: Optional repository override (tests).
    """
    repository = participation_index_repository or TransactionParticipationIndexRepository(bucket_id=bucket_id)
    return repository.load(transaction_id)


__all__ = ["get_transaction_participation"]
