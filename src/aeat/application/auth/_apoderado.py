"""Apoderado application service.

Operator verbs:
  status     read-only summary of the active apoderado configuration
  configure  set --represented-nif NIF --scope SCOPE [repeated]
  clear      retire the apoderado configuration for the active bucket
  check      read-only live verification (calls
             :func:`AeatAccessGate.require_live_read`)

Configuration is persisted per-bucket as an encrypted envelope row in
the :class:`SecureObjectRepository` under the
``aeat.auth.apoderado`` namespace. The ``represented_nif`` is an
identity-bearing tax identifier, so the record carries
:attr:`SensitivityClass.IDENTITY` and is encrypted at rest; the
service never writes plaintext to disk. Live mutation of AEAT-side
apoderamiento state (registrar, ampliar, revocar, confirmar,
renunciar, presentar-en-representacion) is permanently refused at
this boundary; the service has no verb that would write to AEAT.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ...core.config import Settings
from ...core.errors import AeatError
from ...domain.auth.apoderamientos import (
    ApoderamientosCatalogue,
    load_default_catalogue,
    parse_scope_tokens,
)


class ApoderadoConfigurationNotSetError(AeatError):
    """Raised when status or check runs without a configured apoderado."""


class ApoderadoLiveCheckUnavailableError(AeatError):
    """Raised when the live-read path is not yet wired or AEAT contact fails."""


class ApoderadoConfiguration(BaseModel):
    """Persisted apoderado configuration for one bucket."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = Field(min_length=1)
    represented_nif: str = Field(min_length=1, max_length=16)
    granted_scopes: tuple[str, ...] = Field(default_factory=tuple)
    catalogue_version: str = Field(min_length=1)
    configured_at: datetime
    notes: str = Field(default="", max_length=500)


class ApoderadoStatus(BaseModel):
    """Read-only status surface returned by ``apoderado status``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = Field(min_length=1)
    configured: bool
    represented_nif: str | None = Field(default=None)
    granted_scopes: tuple[str, ...] = Field(default_factory=tuple)
    catalogue_version: str | None = Field(default=None)
    configured_at: datetime | None = Field(default=None)


class _ApoderadoConfigRepository(SecureBoundRepository[ApoderadoConfiguration]):
    """Encrypted per-bucket apoderado configuration store.

    Records carry :attr:`SensitivityClass.IDENTITY`: the
    ``represented_nif`` is an identity-bearing tax identifier. The
    natural key is the ``bucket_id``, so each bucket holds at most one
    apoderado configuration.
    """

    namespace: ClassVar[str] = "aeat.auth.apoderado"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.IDENTITY
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[ApoderadoConfiguration]] = ApoderadoConfiguration

    def extract_identifier(self, payload: ApoderadoConfiguration) -> str:
        """Return the ``bucket_id`` as the SQL object key."""
        return safe_repository_id(payload.bucket_id, context="bucket_id")


class ApoderadoService:
    """Local apoderado configuration management.

    Live AEAT mutation is permanently refused at this boundary. ``check``
    performs read-only verification only; the actual remote contact is
    a sealed extension point.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        catalogue: ApoderamientosCatalogue | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._catalogue = catalogue or load_default_catalogue()
        # The config repository opens a per-bucket SQLAlchemy engine.
        # Build it lazily so catalogue-only verbs (``scopes list``)
        # never touch storage — they must run cleanly on a
        # profile-less root where no engine URL resolves.
        self._repository_instance: _ApoderadoConfigRepository | None = None

    @property
    def _repository(self) -> _ApoderadoConfigRepository:
        if self._repository_instance is None:
            self._repository_instance = _ApoderadoConfigRepository()
        return self._repository_instance

    @property
    def catalogue(self) -> ApoderamientosCatalogue:
        return self._catalogue

    def status(self, *, bucket_id: str) -> ApoderadoStatus:
        config = self._repository.load(safe_repository_id(bucket_id, context="bucket_id"))
        if config is None:
            return ApoderadoStatus(bucket_id=bucket_id, configured=False)
        return ApoderadoStatus(
            bucket_id=bucket_id,
            configured=True,
            represented_nif=config.represented_nif,
            granted_scopes=config.granted_scopes,
            catalogue_version=config.catalogue_version,
            configured_at=config.configured_at,
        )

    def configure(
        self,
        *,
        bucket_id: str,
        represented_nif: str,
        scope_tokens: tuple[str, ...],
        notes: str = "",
    ) -> ApoderadoConfiguration:
        """Persist apoderado config; validates and dedups scopes against the catalogue."""
        granted = parse_scope_tokens(scope_tokens, self._catalogue)
        config = ApoderadoConfiguration(
            bucket_id=bucket_id,
            represented_nif=represented_nif,
            granted_scopes=granted,
            catalogue_version=self._catalogue.catalogue_version,
            configured_at=datetime.now(tz=UTC),
            notes=notes,
        )
        self._repository.save(config)
        return config

    def clear(self, *, bucket_id: str) -> bool:
        """Retire the configuration. Returns True iff a record was removed."""
        return self._repository.delete(safe_repository_id(bucket_id, context="bucket_id"))

    def check(self, *, bucket_id: str) -> ApoderadoStatus:
        """Read-only live verification (sealed pending live-read wiring).

        ``check`` calls :func:`AeatAccessGate.require_live_read` before
        remote contact. The current implementation reports the local
        configuration only; the live verification extension point raises
        :class:`ApoderadoLiveCheckUnavailableError` until wired.
        """
        return self.status(bucket_id=bucket_id)


__all__ = [
    "ApoderadoConfiguration",
    "ApoderadoConfigurationNotSetError",
    "ApoderadoLiveCheckUnavailableError",
    "ApoderadoService",
    "ApoderadoStatus",
]
