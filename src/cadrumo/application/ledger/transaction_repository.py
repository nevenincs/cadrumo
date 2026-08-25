"""Explicit lifetime binding for ledger transaction catalogue persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.transactions import TransactionCatalogueRepositoryProtocol


class TransactionCatalogueRepositoryFactory(Protocol):
    """Construct the transaction repository port for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> TransactionCatalogueRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_TRANSACTION_CATALOGUE_REPOSITORY_FACTORY: ContextVar[TransactionCatalogueRepositoryFactory] = ContextVar(
    "cadrumo_transaction_catalogue_repository_factory"
)


@contextmanager
def bind_transaction_catalogue_repository_factory(
    factory: TransactionCatalogueRepositoryFactory,
) -> Generator[TransactionCatalogueRepositoryFactory]:
    """Bind one outward-composed transaction repository factory."""
    token = _BOUND_TRANSACTION_CATALOGUE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_TRANSACTION_CATALOGUE_REPOSITORY_FACTORY.reset(token)


def transaction_catalogue_repository(*, bucket_id: str) -> TransactionCatalogueRepositoryProtocol:
    """Resolve the explicitly composed transaction repository for ``bucket_id``."""
    try:
        factory = _BOUND_TRANSACTION_CATALOGUE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("transaction catalogue persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "TransactionCatalogueRepositoryFactory",
    "bind_transaction_catalogue_repository_factory",
    "transaction_catalogue_repository",
]
