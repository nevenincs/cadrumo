"""Explicit metadata-only target objects for the application family roots."""

from ._app_lazy_registration import build_app_family

_TARGETS = {
    "diagnostics_app": "diagnostics",
    "ledger_app": "ledger",
    "live_app": "live",
    "maintenance_app": "maintenance",
    "modelo_app": "modelo",
    "overview_app": "overview",
    "registry_app": "registry",
    "review_app": "review",
}


def __getattr__(name: str) -> object:
    try:
        family = _TARGETS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = build_app_family(family)
    globals()[name] = value
    return value


__all__ = list(_TARGETS)
