"""Application-owned capability for persisted apoderado configuration.

The application service owns the configuration model and its policy.  This
module declares only the bucket-bound persistence surface that policy needs;
the encrypted envelope, storage namespace, object-key derivation, and backend
errors remain implementation details of an outward adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ...core.config import Settings
    from .apoderado_service import ApoderadoConfiguration


class ApoderadoConfigurationRepository(Protocol):
    """Bucket-bound persistence capability for one apoderado configuration."""

    def load(self) -> ApoderadoConfiguration | None:
        """Return this bucket's configuration, or ``None`` when absent."""
        ...

    def save(self, configuration: ApoderadoConfiguration) -> None:
        """Persist this bucket's configuration."""
        ...

    def delete(self) -> bool:
        """Retire this bucket's configuration, returning whether it existed."""
        ...


class ApoderadoConfigurationRepositoryFactory(Protocol):
    """Construct one bucket-bound apoderado configuration capability."""

    def __call__(self, *, bucket_id: str, settings: Settings) -> ApoderadoConfigurationRepository:
        """Return the capability routed to ``bucket_id`` and ``settings``."""
        ...


__all__ = [
    "ApoderadoConfigurationRepository",
    "ApoderadoConfigurationRepositoryFactory",
]
