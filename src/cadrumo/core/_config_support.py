"""Support types and defaults for the central settings facade.

This module holds the closed settings enums and derived records consumed
by :class:`~core.config.Settings`: secret storage selection
(:class:`~core.config.SecretStoreBackend`), LLM provider selection
(:class:`~core.config.LLMProviderSetting`), and database routing via
:class:`~core.config.StorageRouteKind` and
:class:`~core.config.StorageRouteClassification`.

The route records are produced by
:func:`~core.config.classify_storage_route`; output language strings are
coerced to :class:`~core.external_constants.OutputLanguage`; and AEAT URL
defaults are read from :func:`~core.external_constants.load_external_constants`.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr

from ._models import STRICT_FROZEN_CONFIG
from .external_constants import OutputLanguage, load_external_constants

_EXTERNAL_CONSTANTS = load_external_constants()

AEAT_CERTIFICATE_PROTECTED_ORIGIN = _EXTERNAL_CONSTANTS.aeat.domains.www6
"""Exact Playwright client-certificate origin for AEAT certificate authentication."""

AEAT_CERTIFICATE_PROTECTED_PATH = _EXTERNAL_CONSTANTS.aeat.sede_paths.expedientes_resumen
"""Exact protected AEAT resource path used to prove certificate authentication."""

AEAT_CERTIFICATE_PROTECTED_URL = f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}{AEAT_CERTIFICATE_PROTECTED_PATH}"
"""Canonical protected navigation URL for certificate authentication."""


class SecretStoreBackend(StrEnum):
    """Supported backends for the master-key secret store.

    :class:`~core.config.Settings` exposes this closed set through
    ``cadrumo_secret_store_backend`` so storage custody and operator setup share
    one spelling for automatic, keyring, file-backed, and explicitly unsecured
    secret storage.
    """

    AUTO = "auto"
    KEYRING = "keyring"
    FILE = "file"
    UNSECURED = "unsecured"


def unwrap_optional_secret(value: SecretStr | None) -> str:
    """Return the cleartext of an optional :class:`pydantic.SecretStr`.

    Optional Cl@ve and certificate settings use this helper at adapter
    boundaries so unset secrets materialise as ``""`` rather than leaking
    :class:`pydantic.SecretStr` wrappers into string handling.
    """
    return value.get_secret_value() if value is not None else ""


class LLMProviderSetting(StrEnum):
    """Closed set of LLM provider names accepted by :class:`~core.config.Settings`."""

    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    GEMINI = "GEMINI"
    LOCAL = "LOCAL"


class StorageRouteKind(StrEnum):
    """Resolved primary database route classification.

    Members distinguish operator-supplied database URLs from computed active
    bucket routes and cold root-fallback routes. The storage write policy
    consumes this value through
    :func:`~application.storage_write_policy.inspect_storage_write_policy`.
    """

    EXPLICIT_DATABASE_URL = "explicit_database_url"
    ACTIVE_BUCKET_DATABASE = "active_bucket_database"
    ROOT_FALLBACK_DATABASE = "root_fallback_database"


class StorageRouteClassification(BaseModel):
    """Strict classification of the effective primary database route.

    Instances are returned by :func:`~core.config.classify_storage_route`
    and carry the effective :class:`StorageRouteKind`, original database URL,
    SQLite path when derivable, and active bucket id for bucket-attached routes.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: StorageRouteKind
    database_url: str = Field(min_length=1)
    database_path: Path | None = None
    bucket_id: str = ""


def default_clave_sede_access_url_template() -> str:
    """Return the configured Cl@ve Movil selector access URL template."""
    return load_external_constants().aeat.clave_movil.selector_access_url_template


def default_clave_permanente_sede_access_url_template() -> str:
    """Return the configured Cl@ve Permanente selector access URL template."""
    return load_external_constants().aeat.clave_permanente.selector_access_url_template


def default_sede_expedientes_path() -> str:
    """Return the configured AEAT Sede expedientes summary path."""
    return load_external_constants().aeat.sede_paths.expedientes_resumen


def default_status_detail_url_template() -> str:
    """Return the configured AEAT expediente status detail URL template."""
    return load_external_constants().aeat.sede_paths.expediente_detail_template


def default_status_notificaciones_path() -> str:
    """Return the configured AEAT notifications status path."""
    return load_external_constants().aeat.sede_paths.notificaciones


def default_aeat_sede_origin() -> str:
    """Return the configured AEAT Sede origin."""
    return load_external_constants().aeat.domains.sede


def default_aeat_sede_origin_with_slash() -> str:
    """Return the configured AEAT Sede origin with a trailing slash."""
    return f"{default_aeat_sede_origin()}/"


class JustificanteParserBackendSetting(StrEnum):
    """Settings-shape selector for the justificante PDF parsing backend."""

    PDFPLUMBER = "pdfplumber"


def coerce_output_language_setting(value: str) -> OutputLanguage | None:
    """Coerce an env-var output-language string to an :class:`OutputLanguage`.

    Returns ``None`` for invalid input so :class:`~core.config.Settings`
    validation can decide how to fall back or report the bad value.
    """
    if not value:
        return None
    normalized = value.lower().strip()
    try:
        return OutputLanguage(normalized)
    except ValueError:
        return None


__all__ = [
    "AEAT_CERTIFICATE_PROTECTED_ORIGIN",
    "AEAT_CERTIFICATE_PROTECTED_PATH",
    "AEAT_CERTIFICATE_PROTECTED_URL",
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
