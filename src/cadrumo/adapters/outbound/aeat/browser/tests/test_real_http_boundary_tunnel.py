"""The boundary's proxy serves only the hosts it stands in for.

Playwright continues a redirect hop without routing it, so the boundary is also
the browser's proxy. These cases drive that proxy over real loopback sockets:
what it serves is recorded like any routed request, and a host it does not
stand in for is refused rather than answered or passed on.
"""

from __future__ import annotations

import http.client
import ssl
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest

from ......core.config_support import AEAT_CERTIFICATE_PROTECTED_PATH
from .real_http_boundary import EXTERNAL, LocalHttpBoundary

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_STOOD_IN_HOST = urlsplit(EXTERNAL.aeat.domains.www1).netloc
_FOREIGN_HOST = "www.example.com"


@pytest.fixture
def boundary() -> Iterator[LocalHttpBoundary]:
    served = LocalHttpBoundary()
    try:
        yield served
    finally:
        served.close()


def _proxy_address(boundary: LocalHttpBoundary) -> tuple[str, int]:
    proxy = urlsplit(boundary.proxy_url)
    assert proxy.hostname is not None
    assert proxy.port is not None
    return proxy.hostname, proxy.port


def _tunnel_to(boundary: LocalHttpBoundary, host: str) -> http.client.HTTPSConnection:
    """Open a real CONNECT tunnel that trusts only the boundary's own certificate."""
    trust = ssl.create_default_context(cafile=boundary.tunnel_certificate)
    # The certificate names the boundary, not each host it stands in for.
    trust.check_hostname = False
    proxy_host, proxy_port = _proxy_address(boundary)
    connection = http.client.HTTPSConnection(proxy_host, proxy_port, context=trust, timeout=10)
    connection.set_tunnel(host, 443)
    return connection


def test_a_stood_in_host_is_served_through_the_tunnel_and_recorded(boundary: LocalHttpBoundary) -> None:
    connection = _tunnel_to(boundary, _STOOD_IN_HOST)
    try:
        connection.request("GET", AEAT_CERTIFICATE_PROTECTED_PATH)
        response = connection.getresponse()
        response.read()
    finally:
        connection.close()

    assert response.status == 200
    assert boundary.requested_urls == [f"https://{_STOOD_IN_HOST}{AEAT_CERTIFICATE_PROTECTED_PATH}"]


def test_a_foreign_host_is_refused_and_never_recorded(boundary: LocalHttpBoundary) -> None:
    """DETECTOR TEETH: an unrouted hop to any other host must not be served or passed on."""
    connection = _tunnel_to(boundary, _FOREIGN_HOST)
    try:
        with pytest.raises(OSError, match="403"):
            connection.request("GET", "/")
    finally:
        connection.close()

    assert boundary.requested_urls == []


def test_a_proxied_plain_http_request_to_a_foreign_host_is_refused(boundary: LocalHttpBoundary) -> None:
    """The same rule holds for plain HTTP, which a proxy receives as an absolute URL."""
    connection = http.client.HTTPConnection(*_proxy_address(boundary), timeout=10)
    try:
        connection.request("GET", f"http://{_FOREIGN_HOST}/")
        response = connection.getresponse()
        response.read()
    finally:
        connection.close()

    assert response.status == 403
    assert boundary.requested_urls == []
