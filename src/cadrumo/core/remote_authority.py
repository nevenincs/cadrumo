"""Canonical authority checks for read-only AEAT remote hosts.

This module owns the narrow parsing and suffix predicates used by remote-read
guards and authenticated AEAT landings. It reads immutable external constants
directly so runtime settings cannot become a competing authority.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

from .external_constants import load_external_constants

#: The only scheme a remote AEAT read may use. AEAT publishes every public and
#: authenticated read surface over TLS, so a non-``https`` authority reaching a
#: guard or a landing predicate is a downgrade, never a legitimate surface.
REMOTE_READ_SCHEME: Final[str] = "https"


def canonical_remote_hostname(url: str) -> str | None:
    """Return the bare lower-cased hostname of ``url``, or ``None`` to refuse it.

    This is the single authority for turning a remote URL into the hostname a
    safety check may compare against an allow-list. It is fail-closed: ``None``
    is returned — and every caller MUST treat that as a refusal — when the URL
    is malformed, is not :data:`REMOTE_READ_SCHEME`, carries user-info
    credentials, or pins an explicit port.

    User-info and ports are *refused*, not stripped and not string-matched,
    because each of the two obvious shortcuts admits a different attack:

    * Matching the whole authority (``urlsplit(url).netloc``) admits
      ``https://evil@www6.agenciatributaria.gob.es/`` — the credential prefix
      rides along inside a string that still ends in the AEAT suffix, and the
      browser will send it.
    * Reading a *stripped* host (``pydantic.AnyUrl.host``) silently discards
      user-info and any port, so the same URL and an ``:8443`` redirect both
      read as a plain AEAT host.

    An authority that is not a bare host has no business reaching an
    authenticated AEAT surface, so it is refused rather than normalised.

    Args:
        url: The remote URL to canonicalise, as written by the caller.

    Returns:
        The lower-cased hostname when the authority is a bare host under
        :data:`REMOTE_READ_SCHEME`, otherwise ``None``.
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme.lower() != REMOTE_READ_SCHEME:
        return None
    try:
        # ``.port`` raises for a non-numeric or out-of-range port; an
        # unparsable authority is refused exactly like a declared one.
        if parsed.username is not None or parsed.password is not None or parsed.port is not None:
            return None
        host = parsed.hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.lower()


def aeat_host_suffixes() -> tuple[str, ...]:
    """Return host suffixes treated as AEAT-owned infrastructure."""
    domains = load_external_constants().aeat.domains
    return (domains.host_suffix, domains.legacy_host_suffix)


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
    clave = load_external_constants().aeat.domains.clave
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
