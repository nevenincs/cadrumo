"""Explicit lifetime binding for Modelo filing-record persistence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol

from ...domain.modelos.protocols import ModeloRecordCatalogueRepositoryProtocol


class ModeloRecordCatalogueRepositoryFactory(Protocol):
    """Construct the filing-record repository port for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ModeloRecordCatalogueRepositoryProtocol:
        """Return the repository bound to ``bucket_id``."""
        ...


_BOUND_MODELO_RECORD_CATALOGUE_REPOSITORY_FACTORY: ContextVar[ModeloRecordCatalogueRepositoryFactory] = ContextVar(
    "cadrumo_modelo_record_catalogue_repository_factory"
)


@contextmanager
def bind_modelo_record_catalogue_repository_factory(
    factory: ModeloRecordCatalogueRepositoryFactory,
) -> Generator[ModeloRecordCatalogueRepositoryFactory]:
    """Bind one outward-composed filing-record repository factory."""
    token = _BOUND_MODELO_RECORD_CATALOGUE_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_MODELO_RECORD_CATALOGUE_REPOSITORY_FACTORY.reset(token)


def modelo_record_catalogue_repository(*, bucket_id: str) -> ModeloRecordCatalogueRepositoryProtocol:
    """Resolve the explicitly composed filing repository for ``bucket_id``."""
    try:
        factory = _BOUND_MODELO_RECORD_CATALOGUE_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise RuntimeError("modelo filing-record catalogue persistence has not been composed") from error
    return factory(bucket_id=bucket_id)


__all__ = [
    "ModeloRecordCatalogueRepositoryFactory",
    "bind_modelo_record_catalogue_repository_factory",
    "modelo_record_catalogue_repository",
]
