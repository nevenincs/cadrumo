"""Settings and active-profile storage scopes for auth operator services.

This module uses :class:`Settings` to derive the auth operator configuration.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext

from ...core.config import LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD, Settings, load_settings

_AUTH_OPERATOR_SETTINGS_SCOPE_FIELDS = (
    "aeat_local_storage_root",
    "aeat_active_profile",
    "aeat_secret_store_backend",
    "aeat_secret_store_dir",
    "aeat_secret_passphrase",
    "aeat_auth_provider",
    LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD,
    "aeat_certificate_path",
    "aeat_certificate_password_secret",
    "aeat_certificate_friendly_name",
    "aeat_certificate_backend",
    "aeat_cert_warn_days",
    "aeat_cert_critical_days",
    "aeat_clave_movil_dni_nie",
    "aeat_clave_movil_dni_fecha",
    "aeat_clave_movil_nie_soporte",
    "aeat_clave_prefer_non_qr",
    "aeat_clave_movil_timeout_ms",
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
    for route_field in ("aeat_local_storage_root", "aeat_active_profile"):
        if route_field not in overrides:
            overrides[route_field] = getattr(load_settings(), route_field)
    with override_settings(**overrides) as scoped:
        yield scoped


def active_bucket_id_from_settings(settings: Settings) -> str | None:
    """Resolve the active bucket for ``settings`` without falling through to process globals."""
    from ...core import read_pointer

    override = (settings.aeat_active_profile or "").strip()
    if override:
        return override
    pointer = read_pointer(settings.aeat_local_storage_root)
    return pointer.bucket_id if pointer is not None else None


@contextmanager
def active_profile_storage_span(settings: Settings | None = None):
    """Return a storage context for the active profile, or a no-op when absent."""
    from ...adapters.persistence.storage import has_active_bucket_session
    from ..user_profile._orchestration import profile_storage_session

    with auth_operator_settings_scope(settings) as resolved_settings:
        bucket_id = active_bucket_id_from_settings(resolved_settings)
        if bucket_id is None:
            with nullcontext():
                yield None
            return
        if has_active_bucket_session():
            with nullcontext():
                yield bucket_id
            return
        with profile_storage_session(bucket_id) as active:
            yield active
