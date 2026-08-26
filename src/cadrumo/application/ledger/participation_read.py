"""Read action: surface the modelo participations of one ledger transaction.

The inverse of the forward ``source_transaction_ids`` link. Loads the
per-transaction :class:`TransactionRevisionParticipationIndex` from encrypted
storage and returns it for the CLI surface to project into a typed payload. The
index records only finalized-revision participations (borrador inclusion is
deferred), so the read is the audit-trail answer to "where was this transaction
declared".
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.modelos import (
    TransactionParticipationIndexRepositoryProtocol,
    TransactionRevisionParticipationIndex,
)


class TransactionParticipationIndexRepositoryFactory(Protocol):
    """Construct the participation-index repository port for one bucket."""

    def __call__(
        self,
        *,
        bucket_id: str | None = None,
    ) -> TransactionParticipationIndexRepositoryProtocol:
        """Return the repository resolved for ``bucket_id``."""
        ...


_BOUND_TRANSACTION_PARTICIPATION_INDEX_REPOSITORY_FACTORY: ContextVar[
    TransactionParticipationIndexRepositoryFactory
] = ContextVar("cadrumo_transaction_participation_index_repository_factory")


@contextmanager
def bind_transaction_participation_index_repository_factory(
    factory: TransactionParticipationIndexRepositoryFactory,
) -> Generator[TransactionParticipationIndexRepositoryFactory]:
    """Bind one outward-composed participation-index repository factory."""
    token = _BOUND_TRANSACTION_PARTICIPATION_INDEX_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_TRANSACTION_PARTICIPATION_INDEX_REPOSITORY_FACTORY.reset(token)


def transaction_participation_index_repository(
    *,
    bucket_id: str | None = None,
) -> TransactionParticipationIndexRepositoryProtocol:
    """Resolve the explicitly composed participation repository."""
    try:
        factory = _BOUND_TRANSACTION_PARTICIPATION_INDEX_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("transaction participation-index persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


def get_transaction_participation(
    *,
    transaction_id: str,
    bucket_id: str | None = None,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol | None = None,
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
    repository = (
        participation_index_repository
        if participation_index_repository is not None
        else transaction_participation_index_repository(bucket_id=bucket_id)
    )
    return repository.load(transaction_id)


__all__ = [
    "TransactionParticipationIndexRepositoryFactory",
    "bind_transaction_participation_index_repository_factory",
    "get_transaction_participation",
    "transaction_participation_index_repository",
]
