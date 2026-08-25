"""Explicit lifetime binding for Modelo work-unit catalogue persistence.

The domain owns the repository protocol and persistence owns its concrete
implementation.  Application operations that need to capture a catalogue bind
only the factory shape declared here; executable hosts compose the concrete
adapter for their own lifetime.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


class WorkUnitCatalogueRepositoryFactory(Protocol):
    """Construct the repository port for one resolved profile bucket."""

    def __call__(self, *, bucket_id: str) -> WorkUnitCatalogueRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_WORK_UNIT_CATALOGUE_REPOSITORY_FACTORY: ContextVar[WorkUnitCatalogueRepositoryFactory] = ContextVar(
    "cadrumo_work_unit_catalogue_repository_factory"
)


@contextmanager
def bind_work_unit_catalogue_repository_factory(
    factory: WorkUnitCatalogueRepositoryFactory,
) -> Generator[WorkUnitCatalogueRepositoryFactory]:
    """Bind one outward-composed repository factory for the host context."""
    token = _BOUND_WORK_UNIT_CATALOGUE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_WORK_UNIT_CATALOGUE_REPOSITORY_FACTORY.reset(token)


def work_unit_catalogue_repository(*, bucket_id: str) -> WorkUnitCatalogueRepositoryProtocol:
    """Resolve the explicitly composed repository for ``bucket_id``."""
    try:
        factory = _BOUND_WORK_UNIT_CATALOGUE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("work-unit catalogue persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "WorkUnitCatalogueRepositoryFactory",
    "bind_work_unit_catalogue_repository_factory",
    "work_unit_catalogue_repository",
]
