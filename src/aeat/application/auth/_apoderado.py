"""Apoderado application service.

Operator verbs:
  status     read-only summary of the active apoderado configuration
  configure  set --represented-nif NIF --scope SCOPE [repeated]
  clear      retire the apoderado configuration for the active bucket
  check      read-only live verification (calls
             :func:`AeatAccessGate.require_live_read`)

Configuration is persisted per-bucket as a single JSON document under
``aeat_secret_store_dir/apoderado/<bucket_id>.json``. Live mutation of
AEAT-side apoderamiento state (registrar, ampliar, revocar, confirmar,
renunciar, presentar-en-representacion) is permanently refused at this
boundary; the service has no verb that would write to AEAT.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    root = settings.aeat_secret_store_dir / "apoderado"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.json"


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

    @property
    def catalogue(self) -> ApoderamientosCatalogue:
        return self._catalogue

    def status(self, *, bucket_id: str) -> ApoderadoStatus:
        path = _storage_path(self._settings, bucket_id)
        if not path.exists():
            return ApoderadoStatus(bucket_id=bucket_id, configured=False)
        config = ApoderadoConfiguration.model_validate_json(path.read_text(encoding="utf-8"))
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
        path = _storage_path(self._settings, bucket_id)
        path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        return config

    def clear(self, *, bucket_id: str) -> bool:
        """Retire the configuration. Returns True iff a record was removed."""
        path = _storage_path(self._settings, bucket_id)
        if not path.exists():
            return False
        path.unlink()
        return True

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
