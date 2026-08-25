"""Explicit lifetime binding for Modelo calculation-revision persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.modelos import CalculationRevisionCatalogueRepositoryProtocol


class CalculationRevisionCatalogueRepositoryFactory(Protocol):
    """Construct the calculation-revision repository port for one bucket."""

    def __call__(self, *, bucket_id: str) -> CalculationRevisionCatalogueRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_CALCULATION_REVISION_CATALOGUE_REPOSITORY_FACTORY: ContextVar[CalculationRevisionCatalogueRepositoryFactory] = (
    ContextVar("cadrumo_calculation_revision_catalogue_repository_factory")
)


@contextmanager
def bind_calculation_revision_catalogue_repository_factory(
    factory: CalculationRevisionCatalogueRepositoryFactory,
) -> Generator[CalculationRevisionCatalogueRepositoryFactory]:
    """Bind one outward-composed calculation-revision repository factory."""
    token = _BOUND_CALCULATION_REVISION_CATALOGUE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_CALCULATION_REVISION_CATALOGUE_REPOSITORY_FACTORY.reset(token)


def calculation_revision_catalogue_repository(
    *,
    bucket_id: str,
) -> CalculationRevisionCatalogueRepositoryProtocol:
    """Resolve the explicitly composed calculation repository for ``bucket_id``."""
    try:
        factory = _BOUND_CALCULATION_REVISION_CATALOGUE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("calculation-revision catalogue persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "CalculationRevisionCatalogueRepositoryFactory",
    "bind_calculation_revision_catalogue_repository_factory",
    "calculation_revision_catalogue_repository",
]
