"""Support types and defaults for the central settings facade.

This module holds the closed settings enums and derived records consumed
by :class:`~core.config.Settings`: secret storage selection
(:class:`~core.config.SecretStoreBackend`), LLM provider selection
(:class:`~core.config.LLMProvider`), and database routing via
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

from .models import STRICT_FROZEN_CONFIG
from .external_constants import OutputLanguage, load_external_constants
from .identity import BucketId

_EXTERNAL_CONSTANTS = load_external_constants()

AEAT_CERTIFICATE_PROTECTED_ORIGIN = _EXTERNAL_CONSTANTS.aeat.domains.www6
"""Exact Playwright client-certificate origin for AEAT certificate authentication."""

AEAT_CERTIFICATE_PROTECTED_PATH = _EXTERNAL_CONSTANTS.aeat.sede_paths.expedientes_resumen
"""Exact protected AEAT resource path used to prove certificate authentication."""

AEAT_CERTIFICATE_PROTECTED_URL = f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}{AEAT_CERTIFICATE_PROTECTED_PATH}"
"""Canonical protected navigation URL for certificate authentication."""


def assert_canonical_protected_resource(value: str, *, subject: str) -> str:
    """Return ``value`` if it is the canonical protected resource, else raise.

    Certificate authentication is proved by reaching one specific AEAT
    resource, so a record claiming proof against any other URL is not evidence
    of anything. Both the persisted proof and the live session detail assert
    this, and they asserted it with separate copies of the comparison until
    this became its one home — beside the constant it is about, where a change
    to the route and a change to the rule cannot separate.

    Args:
        value: The protected-resource URL the record carries.
        subject: What is being validated, for the refusal message — the two
            call sites name different records and the operator needs to know
            which one refused.

    Returns:
        ``value`` unchanged.

    Raises:
        ValueError: ``value`` is not the canonical protected resource. A plain
            ``ValueError`` because both call sites are pydantic validators,
            which fold it into the model's own ``ValidationError``.
    """
    if value != AEAT_CERTIFICATE_PROTECTED_URL:
        raise ValueError(f"{subject} must use the canonical protected resource")
    return value


class SecretStoreBackend(StrEnum):
    """Whether at-rest material is protected by real custody or a published key.

    :class:`~core.config.Settings` exposes this closed set through
    ``cadrumo_secret_store_backend``. It is a two-state axis, not a choice
    among storage mechanisms: there is exactly one secured route, the profile's
    own password custody, and one deliberately unsecured route for testing and
    tutorial scenarios.

    The set previously also offered ``keyring`` and ``file``, naming a
    keychain-backed and a passphrase-derived file-backed master-key provider.
    Both providers were deleted in the per-profile custody cutover, and nothing
    ever branched on either member, so the two spellings selected nothing while
    reading as storage modes an operator could choose between.
    """

    AUTO = "auto"
    UNSECURED = "unsecured"


class TuiAppearance(StrEnum):
    """Supported appearances for the full-screen terminal surfaces.

    :class:`~core.config.Settings` exposes this closed set through
    ``cadrumo_tui_appearance`` so the profile manager, the paged flow
    frontend, and the read-only status page share one spelling for the
    operator's light/dark preference. ``AUTO`` defers to the host terminal
    rather than pinning an appearance.
    """

    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


def unwrap_optional_secret(value: SecretStr | None) -> str:
    """Return the cleartext of an optional :class:`pydantic.SecretStr`.

    Optional Cl@ve and certificate settings use this helper at adapter
    boundaries so unset secrets materialise as ``""`` rather than leaking
    :class:`pydantic.SecretStr` wrappers into string handling.
    """
    return value.get_secret_value() if value is not None else ""


class LLMProvider(StrEnum):
    """The closed set of model-transport identities, declared once, here.

    Canonical home for the value set, not a settings-only convenience. Two
    byte-identical copies of it existed -- this one and a second in the
    inference package's request models -- so a reader could not tell which was
    authoritative and a value added to one would silently not exist in the
    other.

    It lives in ``core`` because a closed value set is declared in ``core`` by
    the architecture boundary, and because the direction is forced: the
    inference package may import ``core`` (inward), while ``core`` importing
    the optional inference package is refused by contract. The package consumes
    this enum; it does not redeclare it.
    """

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
    bucket_id: BucketId | None = None


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
    validation can decide how to fall back or report the bad value. A
    non-string value (e.g. a bare ``bool``, which is a subtype of ``int`` and
    would otherwise reach ``.lower()``) is invalid input, not a crash.
    """
    if not isinstance(value, str) or not value:
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
    "LLMProvider",
    "SecretStoreBackend",
    "StorageRouteClassification",
    "StorageRouteKind",
    "assert_canonical_protected_resource",
    "coerce_output_language_setting",
    "default_aeat_sede_origin",
    "default_aeat_sede_origin_with_slash",
    "default_clave_sede_access_url_template",
    "default_sede_expedientes_path",
    "default_status_detail_url_template",
    "default_status_notificaciones_path",
    "unwrap_optional_secret",
]
