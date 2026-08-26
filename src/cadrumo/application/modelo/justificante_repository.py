"""Explicit lifetime binding for justificante persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.justificante import JustificanteRepositoryProtocol


class JustificanteRepositoryFactory(Protocol):
    """Construct the justificante repository port for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> JustificanteRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_JUSTIFICANTE_REPOSITORY_FACTORY: ContextVar[JustificanteRepositoryFactory] = ContextVar(
    "cadrumo_justificante_repository_factory"
)


@contextmanager
def bind_justificante_repository_factory(
    factory: JustificanteRepositoryFactory,
) -> Generator[JustificanteRepositoryFactory]:
    """Bind one outward-composed justificante repository factory."""
    token = _BOUND_JUSTIFICANTE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_JUSTIFICANTE_REPOSITORY_FACTORY.reset(token)


def justificante_repository(*, bucket_id: str) -> JustificanteRepositoryProtocol:
    """Resolve the explicitly composed justificante repository for ``bucket_id``."""
    try:
        factory = _BOUND_JUSTIFICANTE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("justificante persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "JustificanteRepositoryFactory",
    "bind_justificante_repository_factory",
    "justificante_repository",
]
