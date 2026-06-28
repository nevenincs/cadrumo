"""AEAT host predicates shared by registry live-surface guards."""

from __future__ import annotations

from ....core.config import Settings

_AEAT_LEGACY_HOST_SUFFIX = "aeat.es"


def aeat_host_suffixes() -> tuple[str, ...]:
    """Return host suffixes treated as AEAT-owned infrastructure."""
    configured = Settings.external_constants().aeat.domains.host_suffix
    return (configured, _AEAT_LEGACY_HOST_SUFFIX)


def is_aeat_host(host: str) -> bool:
    """Return whether ``host`` is under an AEAT-owned suffix."""
    normalized = host.lower()
    return any(normalized == suffix or normalized.endswith(f".{suffix}") for suffix in aeat_host_suffixes())


def first_aeat_host(hosts: tuple[str, ...]) -> str | None:
    """Return the first AEAT-owned host in ``hosts`` or ``None``."""
    return next((host for host in hosts if is_aeat_host(host)), None)
