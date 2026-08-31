"""Typed certificate credentials passed from application orchestration to adapters."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, SecretStr

from ..core.config import Settings
from ..core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN


class ActiveCertificateCredentials(BaseModel):
    """The exact certificate identity and secret selected for one auth attempt."""

    model_config = _STRICT_FROZEN

    certificate_path: Path | None = None
    password: SecretStr | None = None
    friendly_name: str | None = None
    source_name: str | None = None


def unnamed_certificate_credentials(settings: Settings) -> ActiveCertificateCredentials:
    """Build the typed credential for the unnamed single-certificate settings."""
    return ActiveCertificateCredentials(
        certificate_path=settings.cadrumo_certificate_path,
        password=settings.cadrumo_certificate_password_secret,
        friendly_name=settings.cadrumo_certificate_friendly_name,
        source_name=None,
    )


__all__ = ["ActiveCertificateCredentials", "unnamed_certificate_credentials"]
