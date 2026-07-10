"""AEAT host predicates shared by registry live-surface guards."""

from __future__ import annotations

from urllib.parse import urlsplit

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


def sanctioned_gov_idp_host_suffixes() -> tuple[str, ...]:
    """Return host suffixes for sanctioned national-IdP surfaces (Cl@ve).

    Derived from the ``aeat.domains.clave`` central-config entry (Spain's Cl@ve
    government identity provider). This is a NARROW, opt-in allowance distinct
    from :func:`is_aeat_host`: it names the single national-IdP apex an
    authenticated AEAT flow structurally delegates to, never a data surface.
    """
    clave = Settings.external_constants().aeat.domains.clave
    return (urlsplit(clave).netloc,)


def is_sanctioned_gov_idp_host(host: str) -> bool:
    """Return whether ``host`` is under a sanctioned government-IdP apex (Cl@ve).

    Suffix-shaped so the observed login subdomain (``se-pasarela.clave.gob.es``)
    is covered without enumerating unstable IdP subdomains. Admission of such a
    host in a guard policy is gated separately on an explicit opt-in
    (see :class:`RemoteStateGuardPolicy.allows_gov_idp_hosts`).
    """
    normalized = host.lower()
    return any(
        normalized == suffix or normalized.endswith(f".{suffix}") for suffix in sanctioned_gov_idp_host_suffixes()
    )
