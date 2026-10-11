"""Whether an HTTP endpoint names this machine's own loopback interface."""

from __future__ import annotations

import ipaddress
from typing import Final
from urllib.parse import urlsplit

__all__ = ["endpoint_host_is_loopback", "endpoint_is_loopback"]

_HTTP_SCHEMES: Final = frozenset({"http", "https"})
_LOCALHOST: Final = "localhost"
_IPV4_LOOPBACK: Final = ipaddress.IPv4Network("127.0.0.0/8")
_IPV6_LOOPBACK: Final = ipaddress.IPv6Address("::1")


def endpoint_host_is_loopback(url: str) -> bool:
    """Return whether ``url`` is an HTTP(S) endpoint whose host is this machine's loopback.

    Loopback is the IPv4 range ``127.0.0.0/8``, IPv6 ``::1`` (including its
    IPv4-mapped form of a ``127.0.0.0/8`` address) and the name ``localhost``,
    with or without a trailing dot, in any letter case. Everything else is not
    loopback: the unspecified address ``0.0.0.0``, a name that merely contains
    or ends with ``localhost``, shorthand or numerically encoded IPv4 forms,
    scoped IPv6 literals and an empty host.

    The host is the one left after the standard parser separates any user
    information, so credentials on a loopback host do not change the answer and
    credentials in front of another host never make it loopback. The test is on
    the URL text alone. Any URL the parser cannot read unambiguously is refused
    rather than interpreted: a scheme other than ``http`` or ``https`` (a
    Unix-socket or file URL has no network host to compare) and one carrying a
    backslash, whitespace or a control or non-ASCII character, where different
    parsers disagree about where the host ends. It never raises; a URL that does
    not parse is not loopback.

    Use it to describe where an endpoint is, and to choose a transport that must
    not leave the machine. Use :func:`endpoint_is_loopback` to authorise a
    request.

    Args:
        url: Endpoint URL to classify.

    Returns:
        ``True`` only when the URL provably names this machine's loopback host.
    """
    if not url.isascii() or not url.isprintable() or any(char in url for char in " \\"):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme.lower() not in _HTTP_SCHEMES or not host:
        return False
    return _host_is_loopback(host.lower())


def endpoint_is_loopback(url: str) -> bool:
    """Return whether a request to ``url`` may be treated as staying on this machine.

    Stricter than :func:`endpoint_host_is_loopback`: a URL that carries
    credentials is refused even when its host is loopback, because an
    authorisation to send a person's documents has no use for them and a
    credentialed URL is the shape parsers most often disagree about.

    Args:
        url: Endpoint URL to classify.

    Returns:
        ``True`` only when the host is loopback and the URL carries no user
        information.
    """
    return endpoint_host_is_loopback(url) and "@" not in urlsplit(url).netloc


def _host_is_loopback(host: str) -> bool:
    if host.removesuffix(".") == _LOCALHOST:
        return True
    if "%" in host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return address.ipv4_mapped in _IPV4_LOOPBACK
        return address == _IPV6_LOOPBACK
    return address in _IPV4_LOOPBACK
