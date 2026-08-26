"""Explicit lifetime binding for bucket event-history persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ..domain.buckets import BucketEventHistoryRepositoryProtocol


class BucketEventHistoryRepositoryFactory(Protocol):
    """Construct the event-history repository port for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_BUCKET_EVENT_HISTORY_REPOSITORY_FACTORY: ContextVar[BucketEventHistoryRepositoryFactory] = ContextVar(
    "cadrumo_bucket_event_history_repository_factory"
)


@contextmanager
def bind_bucket_event_history_repository_factory(
    factory: BucketEventHistoryRepositoryFactory,
) -> Generator[BucketEventHistoryRepositoryFactory]:
    """Bind one outward-composed bucket event-history repository factory."""
    token = _BOUND_BUCKET_EVENT_HISTORY_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_BUCKET_EVENT_HISTORY_REPOSITORY_FACTORY.reset(token)


def bucket_event_history_repository(*, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
    """Resolve the explicitly composed event-history repository for ``bucket_id``."""
    try:
        factory = _BOUND_BUCKET_EVENT_HISTORY_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("bucket event-history persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "BucketEventHistoryRepositoryFactory",
    "bind_bucket_event_history_repository_factory",
    "bucket_event_history_repository",
]
