"""Resolve :class:`PortalHost` origins from external constants.

These helpers keep hostnames centralized for :class:`PortalMetadata`
validation and portal-entry assembly rather than embedding AEAT domains in
individual catalogue entries.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from ...core.config import Settings
from .categories import PortalHost
from .errors import PortalValidationError


def portal_host_origin(subdomain: PortalHost) -> str:
    """Return the configured HTTPS origin for a :class:`PortalHost`."""
    domains = Settings.external_constants().aeat.domains
    if subdomain is PortalHost.SEDE:
        return domains.sede
    if subdomain is PortalHost.WWW1:
        return domains.www1
    if subdomain is PortalHost.WWW2:
        return domains.www2
    if subdomain is PortalHost.WWW3:
        return domains.www3
    if subdomain is PortalHost.AGENCIATRIBUTARIA_GOB:
        return domains.aeat_gob
    if subdomain is PortalHost.AGENCIATRIBUTARIA_ES:
        return domains.legacy_www
    if subdomain is PortalHost.CLAVE_GOB:
        return domains.clave
    raise PortalValidationError(f"unsupported AEAT portal subdomain {subdomain!r}")


def portal_host_name(subdomain: PortalHost) -> str:
    """Return the configured hostname for a :class:`PortalHost`."""
    host = urlsplit(portal_host_origin(subdomain)).netloc
    if not host:
        raise PortalValidationError(f"configured portal origin for {subdomain!r} has no host")
    return host


__all__ = ["portal_host_name", "portal_host_origin"]
