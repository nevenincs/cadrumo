"""Which endpoint URLs name this machine's loopback interface."""

from __future__ import annotations

import pytest

from ..loopback_endpoint import endpoint_host_is_loopback

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/api/chat",
        "http://127.0.0.1/api/chat",
        "http://127.1.2.3:11434/api/chat",
        "http://127.255.255.254:11434/api/chat",
        "https://127.0.0.1:11434/api/chat",
        "HTTP://127.0.0.1:11434/api/chat",
        "http://localhost:11434/api/chat",
        "http://LocalHost:11434/api/chat",
        "http://localhost.:11434/api/chat",
        "http://LOCALHOST./api/chat",
        "http://[::1]:11434/api/chat",
        "http://[::1]/api/chat",
        "http://[0:0:0:0:0:0:0:1]:11434/api/chat",
        "http://[::ffff:127.0.0.1]:11434/api/chat",
    ],
)
def test_loopback_endpoints_are_accepted(url: str) -> None:
    assert endpoint_host_is_loopback(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://0.0.0.0:11434/api/chat",
        "http://[::]:11434/api/chat",
        "http://localhost.example.com:11434/api/chat",
        "http://mylocalhost:11434/api/chat",
        "http://localhost.evil.test/api/chat",
        "http://notlocalhost./api/chat",
        "http://localhostt/api/chat",
        "http://gpu-box.lan:11434/api/chat",
        "http://192.168.1.10:11434/api/chat",
        "http://126.255.255.255:11434/api/chat",
        "http://128.0.0.1:11434/api/chat",
        "http://127.1:11434/api/chat",
        "http://2130706433:11434/api/chat",
        "http://0x7f000001:11434/api/chat",
        "http://[::ffff:192.168.1.10]:11434/api/chat",
        "http://[::ffff:0.0.0.0]:11434/api/chat",
        "http://[::2]:11434/api/chat",
        "http://[::1%25eth0]:11434/api/chat",
        "http://user:secret@evil.example.test/api/chat",
        "http://127.0.0.1@evil.example.test/api/chat",
        "http://localhost@evil.example.test/api/chat",
        "http://127.0.0.1:secret@evil.example.test/api/chat",
        "http://evil.example.test\\@127.0.0.1/api/chat",
        "http://127.0.0.1 .evil.example.test/api/chat",
        "http://127.0.0.1\n.evil.example.test/api/chat",
        "http:///api/chat",
        "http://:11434/api/chat",
        "/api/chat",
        "127.0.0.1:11434/api/chat",
        "",
        "http://[::1/api/chat",
    ],
)
def test_other_endpoints_are_refused(url: str) -> None:
    assert endpoint_host_is_loopback(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "unix:///var/run/reader.sock",
        "http+unix://%2Fvar%2Frun%2Freader.sock/api/chat",
        "file:///127.0.0.1/api/chat",
        "ftp://127.0.0.1/api/chat",
        "ws://127.0.0.1:11434/api/chat",
        "//127.0.0.1:11434/api/chat",
    ],
)
def test_non_http_schemes_are_refused_even_with_a_loopback_host(url: str) -> None:
    assert endpoint_host_is_loopback(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "http://user@127.0.0.1:11434/api/chat",
        "http://user:secret@localhost:11434/api/chat",
        "http://user:secret@[::1]:11434/api/chat",
    ],
)
def test_credentials_on_a_loopback_host_leave_the_host_loopback(url: str) -> None:
    assert endpoint_host_is_loopback(url) is True
