"""Settings and active-profile storage scopes for auth operator services.

This module uses :class:`Settings` to derive the auth operator configuration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.config import LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD, Settings, load_settings
from ._catalogue import get_auth_provider, known_auth_provider_ids
from ._operator_results import AuthOperationScopeConflictError, AuthProviderNotConfiguredError

_AUTH_OPERATOR_SETTINGS_SCOPE_FIELDS = (
    "cadrumo_local_storage_root",
    "cadrumo_active_profile",
    "cadrumo_secret_store_backend",
    "cadrumo_secret_store_dir",
    "cadrumo_secret_passphrase",
    "cadrumo_token_dir",
    "cadrumo_auth_provider",
    LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD,
    "cadrumo_certificate_path",
    "cadrumo_certificate_password_secret",
    "cadrumo_certificate_friendly_name",
    "cadrumo_certificate_backend",
    "cadrumo_cert_warn_days",
    "cadrumo_cert_critical_days",
    "cadrumo_clave_movil_dni_nie",
    "cadrumo_clave_movil_dni_fecha",
    "cadrumo_clave_movil_nie_soporte",
    "cadrumo_clave_prefer_non_qr",
    "cadrumo_clave_movil_timeout_ms",
)


@contextmanager
def auth_operator_settings_scope(settings: Settings | None) -> Iterator[Settings]:
    """Yield a :class:`Settings` for auth-operator probes.

    Uses the supplied settings when provided, otherwise loads from the
    default path.
    """
    from ...core.config import override_settings

    if settings is None:
        yield load_settings()
        return
    overrides = {
        field: getattr(settings, field)
        for field in _AUTH_OPERATOR_SETTINGS_SCOPE_FIELDS
        if field in settings.model_fields_set
    }
    for route_field in ("cadrumo_local_storage_root", "cadrumo_active_profile"):
        if route_field not in overrides:
            overrides[route_field] = getattr(load_settings(), route_field)
    with override_settings(**overrides) as scoped:
        yield scoped


def active_bucket_id_from_settings(settings: Settings) -> str | None:
    """Resolve the active bucket for ``settings`` without falling through to process globals."""
    from ...core import read_pointer

    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    pointer = read_pointer(settings.cadrumo_local_storage_root)
    return pointer.bucket_id if pointer is not None else None


@contextmanager
def active_profile_storage_span(
    settings: Settings | None = None,
    *,
    target_bucket_id: str | None = None,
):
    """Return a storage context for the explicit target or active profile."""
    from ...adapters.persistence.storage.master_key import current_active_bucket_session
    from ..user_profile import profile_storage_session

    with auth_operator_settings_scope(settings) as resolved_settings:
        bucket_id = target_bucket_id or active_bucket_id_from_settings(resolved_settings)
        if bucket_id is None:
            with nullcontext():
                yield None
            return
        active_session = current_active_bucket_session()
        if active_session is not None and active_session.bucket_id == bucket_id:
            with nullcontext():
                yield bucket_id
            return
        with profile_storage_session(bucket_id) as active:
            yield active


class AuthOperationScope(BaseModel):
    """Resolved bucket and provider ids for an operator auth mutation."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    provider_ids: tuple[str, ...]


def resolve_auth_operation_scope(
    *,
    bucket_id: str,
    current_provider: str | None,
    provider: str | None,
    all_providers: bool,
) -> AuthOperationScope:
    """Resolve one explicit provider, every known provider, or the configured provider."""
    if provider is not None and all_providers:
        raise AuthOperationScopeConflictError(
            translated_message="application.auth.operator.errors.scope_conflict",
        )
    if all_providers:
        provider_ids = known_auth_provider_ids()
    elif provider is not None:
        provider_ids = (get_auth_provider(provider).id,)
    elif current_provider:
        provider_ids = (get_auth_provider(current_provider).id,)
    else:
        raise AuthProviderNotConfiguredError(
            translated_message="application.auth.operator.errors.provider_not_configured",
        )
    return AuthOperationScope(bucket_id=bucket_id, provider_ids=provider_ids)
