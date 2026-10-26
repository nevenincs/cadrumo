"""The composed persistence port for confirmation-record policy."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Protocol

from ...core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from ...core.config import Settings
    from .confirmation_record import ConfirmationRecordDocument

__all__ = [
    "ConfirmationRecordRepositoryFactory",
    "ConfirmationRecordRepositoryProtocol",
    "bind_confirmation_record_repository_factory",
    "confirmation_record_repository",
]


class ConfirmationRecordRepositoryProtocol(Protocol):
    """Persistence operations required by confirmation-record policy."""

    def load(self, identifier: str) -> ConfirmationRecordDocument | None:
        """Load the document stored under ``identifier``, when present."""
        ...

    def save(self, payload: ConfirmationRecordDocument) -> None:
        """Persist one complete confirmation-record document."""
        ...


class ConfirmationRecordRepositoryFactory(Protocol):
    """Construct a confirmation repository for one bucket and storage configuration."""

    def __call__(
        self,
        *,
        bucket_id: str,
        settings: Settings | None,
    ) -> ConfirmationRecordRepositoryProtocol:
        """Return the encrypted repository bound to ``bucket_id``."""
        ...


_BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY: ContextVar[ConfirmationRecordRepositoryFactory] = ContextVar(
    "cadrumo_confirmation_record_repository_factory"
)


@contextmanager
def bind_confirmation_record_repository_factory(
    factory: ConfirmationRecordRepositoryFactory,
) -> Generator[ConfirmationRecordRepositoryFactory]:
    """Bind one outward-composed confirmation repository factory."""
    token = _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.set(factory)
    try:
        yield factory
    finally:
        _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.reset(token)


def confirmation_record_repository(bucket_id: str, settings: Settings | None) -> ConfirmationRecordRepositoryProtocol:
    """Resolve the composed repository for one bucket and storage configuration."""
    try:
        factory = _BOUND_CONFIRMATION_RECORD_REPOSITORY_FACTORY.get()
    except LookupError as error:
        raise InternalInvariantError("confirmation-record persistence has not been composed") from error
    return factory(bucket_id=bucket_id, settings=settings)
