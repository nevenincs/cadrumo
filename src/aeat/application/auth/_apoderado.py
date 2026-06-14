"""Apoderado application service.

Operator verbs:

``status``
    Read-only summary of the active apoderado configuration.
``configure``
    Set ``--represented-nif NIF --scope SCOPE`` (repeated).
``clear``
    Retire the apoderado configuration for the active bucket.
``check``
    Live verification of the stored apoderamiento against the AEAT
    sede. The live-read path is not wired, so this verb refuses with
    :class:`ApoderadoLiveCheckUnavailableError`; use ``status`` for the
    offline configuration read.

Configuration is persisted per-bucket as an encrypted envelope row in
the :class:`SecureObjectRepository` under the
``aeat.auth.apoderado`` namespace. The ``represented_nif`` is an
identity-bearing tax identifier, so the record carries
:class:`SensitivityClass` ``IDENTITY`` and is encrypted at rest; the
service never writes plaintext to disk. Live mutation of AEAT-side
apoderamiento state (registrar, ampliar, revocar, confirmar,
renunciar, presentar-en-representacion) is permanently refused at
this boundary; the service has no verb that would write to AEAT.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import (
    AUTH_APODERADO_CONFIGURATION_NAMESPACE,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core.config import Settings
from ...core.errors import AeatError
from ...core.identity import BucketId
from ...core.time import now
from ...domain.auth import (
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

    bucket_id: BucketId
    represented_nif: str = Field(min_length=1, max_length=16)
    granted_scopes: tuple[str, ...] = Field(default_factory=tuple)
    catalogue_version: str = Field(min_length=1)
    configured_at: datetime
    notes: str = Field(default="", max_length=500)


class ApoderadoStatus(BaseModel):
    """Read-only status surface returned by ``apoderado status``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: BucketId
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

    namespace: ClassVar[str] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = AUTH_APODERADO_CONFIGURATION_NAMESPACE.schema_version

    @override
    @classmethod
    def payload_model(cls) -> type[ApoderadoConfiguration]:
        return ApoderadoConfiguration

    @override
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
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # bypasses the context-var.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._catalogue = catalogue or load_default_catalogue()
        # Build repositories lazily per requested bucket so catalogue-only
        # verbs never touch storage and a long-lived service cannot route
        # bucket B's apoderado NIF into bucket A's database.
        self._repository_instances: dict[str, _ApoderadoConfigRepository] = {}

    def _repository_for(self, bucket_id: str) -> _ApoderadoConfigRepository:
        safe_bucket_id = safe_repository_id(bucket_id, context="bucket_id")
        repository = self._repository_instances.get(safe_bucket_id)
        if repository is None:
            repository = _ApoderadoConfigRepository(bucket_id=safe_bucket_id, settings=self._settings)
            self._repository_instances[safe_bucket_id] = repository
        return repository

    @property
    def catalogue(self) -> ApoderamientosCatalogue:
        """Return the AEAT apoderamiento scope :class:`ApoderamientosCatalogue` in use by this service."""
        return self._catalogue

    def status(self, *, bucket_id: str) -> ApoderadoStatus:
        """Return the current :class:`ApoderadoStatus` for ``bucket_id``.

        Reads the persisted :class:`ApoderadoConfiguration` (if any) and
        projects it into a read-only status record. Does not contact AEAT.

        Args:
            bucket_id: The profile bucket's UUIDv4 identifier.
        """
        safe_bucket_id = safe_repository_id(bucket_id, context="bucket_id")
        config = self._repository_for(safe_bucket_id).load(safe_bucket_id)
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
        """Persist apoderado config and return the resulting :class:`ApoderadoConfiguration`.

        Validates and dedups scopes against the catalogue.
        """
        granted = parse_scope_tokens(scope_tokens, self._catalogue)
        config = ApoderadoConfiguration(
            bucket_id=bucket_id,
            represented_nif=represented_nif,
            granted_scopes=granted,
            catalogue_version=self._catalogue.catalogue_version,
            configured_at=now(),
            notes=notes,
        )
        self._repository_for(config.bucket_id).save(config)
        return config

    def clear(self, *, bucket_id: str) -> bool:
        """Retire the configuration. Returns True iff a record was removed."""
        safe_bucket_id = safe_repository_id(bucket_id, context="bucket_id")
        return self._repository_for(safe_bucket_id).delete(safe_bucket_id)

    def check(self, *, bucket_id: str) -> ApoderadoStatus:
        """Read-only live verification (sealed pending live-read wiring).

        ``check`` is the live-verification verb: it would contact the
        AEAT sede to confirm the stored apoderamiento is still granted.
        That live-read path is not wired (live AEAT reads are refused at
        this boundary per the safety gate), so ``check`` raises
        :class:`ApoderadoLiveCheckUnavailableError` unconditionally rather
        than silently re-reading stored configuration and presenting it as
        a live result. Use ``status`` for the offline configuration read.

        Returns the live :class:`ApoderadoStatus` once the live-read path is
        wired; until then it raises.

        :raises ApoderadoLiveCheckUnavailableError: always, until the
            live-read path is wired.
        """
        raise ApoderadoLiveCheckUnavailableError


__all__ = [
    "ApoderadoConfiguration",
    "ApoderadoConfigurationNotSetError",
    "ApoderadoLiveCheckUnavailableError",
    "ApoderadoService",
    "ApoderadoStatus",
]
