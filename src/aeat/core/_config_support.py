"""Support types and defaults for the central settings facade.

This module holds the closed settings enums and derived records consumed
by :class:`aeat.core.config.Settings`: authentication provider selectors
(:class:`AuthProviderKindSetting`, :class:`CertificateBackend`), secret
storage selection (:class:`SecretStoreBackend`), and database routing via
:class:`StorageRouteKind` and :class:`StorageRouteClassification`.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr

from ..core import STRICT_FROZEN_CONFIG
from .external_constants import OutputLanguage


class SecretStoreBackend(StrEnum):
    """Supported backends for the master-key secret store."""

    AUTO = "auto"
    KEYRING = "keyring"
    FILE = "file"
    UNSECURED = "unsecured"


def unwrap_optional_secret(value: SecretStr | None) -> str:
    """Return the cleartext of an optional secret, or ``""`` when unset."""
    return value.get_secret_value() if value is not None else ""


class LLMProviderSetting(StrEnum):
    """Closed set of provider names accepted by settings."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    LOCAL = "LOCAL"


class CertificateBackend(StrEnum):
    """Closed catalogue of supported AEAT certificate-handshake backends."""

    PLAYWRIGHT_CONTEXT = "playwright_context"
    HTTPX_FALLBACK = "httpx_fallback"


class AuthProviderKindSetting(StrEnum):
    """Settings-shape selector for the active AEAT authentication provider."""

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"


class StorageRouteKind(StrEnum):
    """Resolved primary database route classification."""

    EXPLICIT_DATABASE_URL = "explicit_database_url"
    ACTIVE_BUCKET_DATABASE = "active_bucket_database"
    ROOT_FALLBACK_DATABASE = "root_fallback_database"


class StorageRouteClassification(BaseModel):
    """Strict classification of the effective primary database route."""

    model_config = STRICT_FROZEN_CONFIG

    kind: StorageRouteKind
    database_url: str = Field(min_length=1)
    database_path: Path | None = None
    bucket_id: str = ""


def default_clave_sede_access_url_template() -> str:
    from .external_constants import load_external_constants

    return load_external_constants().aeat.clave_movil.selector_access_url_template


def default_sede_expedientes_path() -> str:
    from .external_constants import load_external_constants

    return load_external_constants().aeat.sede_paths.expedientes_resumen


def default_status_detail_url_template() -> str:
    from .external_constants import load_external_constants

    return load_external_constants().aeat.sede_paths.expediente_detail_template


def default_status_notificaciones_path() -> str:
    from .external_constants import load_external_constants

    return load_external_constants().aeat.sede_paths.notificaciones


def default_aeat_sede_origin() -> str:
    from .external_constants import load_external_constants

    return load_external_constants().aeat.domains.sede


def default_aeat_sede_origin_with_slash() -> str:
    return f"{default_aeat_sede_origin()}/"


class JustificanteParserBackendSetting(StrEnum):
    """Settings-shape selector for the justificante PDF parsing backend."""

    PDFPLUMBER = "pdfplumber"


def coerce_output_language_setting(value: str) -> OutputLanguage | None:
    """Coerce an env-var output-language string to an :class:`OutputLanguage` member, or ``None`` for invalid input."""
    if not value:
        return None
    normalized = value.lower().strip()
    try:
        return OutputLanguage(normalized)
    except ValueError:
        return None


__all__ = [
    "AuthProviderKindSetting",
    "CertificateBackend",
    "JustificanteParserBackendSetting",
    "LLMProviderSetting",
    "SecretStoreBackend",
    "StorageRouteClassification",
    "StorageRouteKind",
    "coerce_output_language_setting",
    "default_aeat_sede_origin",
    "default_aeat_sede_origin_with_slash",
    "default_clave_sede_access_url_template",
    "default_sede_expedientes_path",
    "default_status_detail_url_template",
    "default_status_notificaciones_path",
    "unwrap_optional_secret",
]
