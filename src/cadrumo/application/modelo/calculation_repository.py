"""Explicit lifetime binding for Modelo calculation-revision persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol


class CalculationRevisionCatalogueRepositoryFactory(Protocol):
    """Construct the calculation-revision repository port for one bucket."""

    def __call__(
        self, *, bucket_id: str, operation: PinnedAuthorityOperation | None
    ) -> CalculationRevisionCatalogueRepositoryProtocol:
        """Return the repository bound to ``bucket_id`` and its held authority context."""
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
    operation: PinnedAuthorityOperation | None,
) -> CalculationRevisionCatalogueRepositoryProtocol:
    """Resolve the explicitly composed repository for one bucket and held operation."""
    try:
        factory = _BOUND_CALCULATION_REVISION_CATALOGUE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise InternalInvariantError("calculation-revision catalogue persistence has not been composed") from error
    return factory(bucket_id=bucket_id, operation=operation)


__all__ = [
    "CalculationRevisionCatalogueRepositoryFactory",
    "bind_calculation_revision_catalogue_repository_factory",
    "calculation_revision_catalogue_repository",
]
