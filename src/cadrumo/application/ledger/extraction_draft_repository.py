"""The composed persistence port for pending extraction-draft policy."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ...core.config import Settings
    from .extraction_draft_store import ExtractionDraftDocument

__all__ = [
    "ExtractionDraftRepositoryFactory",
    "ExtractionDraftRepositoryProtocol",
    "bind_extraction_draft_repository_factory",
    "extraction_draft_repository",
]


class ExtractionDraftRepositoryProtocol(Protocol):
    """Persistence operations required by extraction-draft application policy."""

    def load(self, identifier: str) -> ExtractionDraftDocument | None:
        """Load the document stored under ``identifier``, when present."""
        ...

    def save(self, payload: ExtractionDraftDocument) -> None:
        """Persist one complete extraction-draft document."""
        ...


class ExtractionDraftRepositoryFactory(Protocol):
    """Construct a repository port for one bucket and storage configuration."""

    def __call__(self, *, bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
        """Return the encrypted repository for ``bucket_id``."""
        ...


_BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY: ContextVar[ExtractionDraftRepositoryFactory] = ContextVar(
    "cadrumo_extraction_draft_repository_factory"
)


@contextmanager
def bind_extraction_draft_repository_factory(
    factory: ExtractionDraftRepositoryFactory,
) -> Generator[ExtractionDraftRepositoryFactory]:
    """Bind one outward-composed repository factory for the host context."""
    token = _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.reset(token)


def extraction_draft_repository(bucket_id: str, settings: Settings) -> ExtractionDraftRepositoryProtocol:
    """Resolve the composed repository for one bucket and storage configuration."""
    try:
        factory = _BOUND_EXTRACTION_DRAFT_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise InternalInvariantError("extraction-draft persistence has not been composed") from error
    return factory(bucket_id=bucket_id, settings=settings)
