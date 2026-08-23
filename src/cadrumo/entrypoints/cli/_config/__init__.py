"""Demand-loaded configuration command surface."""

from __future__ import annotations

from importlib import import_module

from ._lazy_registration import app

_COMPAT_EXPORTS: dict[str, tuple[str, str]] = {
    "_resolve_preflight_revision_id": ("._profile_inspect", "_resolve_preflight_revision_id"),
    "apoderado_app": ("._apoderado", "apoderado_app"),
    "auth_app": ("._auth", "auth_app"),
    "auth_diagnostics_app": ("._auth_diagnostics", "auth_diagnostics_app"),
    "certificate_app": ("._certificate", "certificate_app"),
    "offer_login_to_a_gated_verb": ("._login_frontend", "offer_login_to_a_gated_verb"),
    "register_apoderado_commands": ("._apoderado", "register_apoderado_commands"),
    "register_bucket_history_commands": ("._bucket_history", "register_bucket_history_commands"),
    "register_collab_commands": ("._collab", "register_collab_commands"),
    "register_custody_commands": ("._custody", "register_custody_commands"),
    "register_descendiente_commands": ("._descendiente", "register_descendiente_commands"),
    "register_repair_maintenance_commands": ("._repair_cli", "register_repair_maintenance_commands"),
    "register_repair_profile_command": ("._repair_profile", "register_repair_profile_command"),
    "register_reset_commands": ("._reset_cli", "register_reset_commands"),
    "storage_app": ("._storage_cli", "storage_app"),
    "tr": ("....core.i18n", "tr"),
}


def __getattr__(name: str) -> object:
    """Preserve the package facade without importing command families eagerly."""
    try:
        module_name, attribute = _COMPAT_EXPORTS[name]
    except KeyError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


__all__ = ["app", *_COMPAT_EXPORTS]
