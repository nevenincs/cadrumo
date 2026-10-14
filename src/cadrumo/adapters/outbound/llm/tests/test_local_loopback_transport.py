"""The local reader keeps a loopback request on this machine, whatever the environment says.

An automation's document read is allowed only when the reader's endpoint is
loopback. These tests send real requests from the real adapter to real local
servers, with proxy variables pointing at a recording server standing in for a
proxy, and prove the request reaches the endpoint and not the proxy, and is not
carried to another host by a redirect.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from queue import Empty, Queue
from typing import ClassVar, override

import pytest

from .....core.config import override_settings
from .....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    serving_loopback,
    write_json_response,
    write_raw_response,
)
from ..errors import LLMProviderError
from ..providers.base import ProviderCompletion, ProviderRequest
from ..providers.local import LocalAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROXY_VARIABLES = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)
_BYPASS_VARIABLES = ("NO_PROXY", "no_proxy")


class _Arrivals(SilentLoopbackHandler):
    """Records each arrival's request line target and answers like a reader."""

    arrivals: ClassVar[Queue[str]]
    reply: ClassVar[str]

    @override
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        self.arrivals.put(self.path)
        write_json_response(self, ollama_chat_reply(self.reply), status=HTTPStatus.OK)


class _Reader(_Arrivals):
    reply = "from the reader"


class _Proxy(_Arrivals):
    reply = "from the proxy"


class _Bystander(_Arrivals):
    reply = "from another host"


class _Redirecting(SilentLoopbackHandler):
    """Answers every chat post with a redirect to ``location``."""

    arrivals: ClassVar[Queue[str]]
    location: ClassVar[str]

    @override
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        self.arrivals.put(self.path)
        write_raw_response(
            self,
            b"",
            status=HTTPStatus.TEMPORARY_REDIRECT,
            extra_headers={"location": self.location},
        )


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="req",
        model="gpt-oss",
        prompt="Read the invoice.",
        system=None,
        max_tokens=64,
        temperature=0.0,
        timeout_s=3,
    )


def _complete() -> ProviderCompletion:
    return asyncio.run(LocalAdapter(timeout_s=3).complete(_request()))


def _route_through_proxy(monkeypatch: pytest.MonkeyPatch, proxy_url: str) -> None:
    proxy = proxy_url.removesuffix("/api/chat")
    for name in _PROXY_VARIABLES:
        monkeypatch.setenv(name, proxy)
    for name in _BYPASS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _fresh() -> Queue[str]:
    return Queue()


def _nothing_arrived(arrivals: Queue[str]) -> bool:
    try:
        arrivals.get_nowait()
    except Empty:
        return True
    return False


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "user:secret@127.0.0.1"])
def test_loopback_request_ignores_proxy_environment(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    reader_arrivals, proxy_arrivals = _fresh(), _fresh()
    _Reader.arrivals = reader_arrivals
    _Proxy.arrivals = proxy_arrivals
    with (
        serving_loopback(_Proxy, path="/api/chat") as proxy_url,
        serving_loopback(_Reader, path="/api/chat") as reader_url,
    ):
        _route_through_proxy(monkeypatch, proxy_url)
        endpoint = reader_url.replace("127.0.0.1", host)
        with override_settings(cadrumo_llm_ollama_chat_url=endpoint):
            completion = _complete()

    assert completion.text == "from the reader"
    assert reader_arrivals.get_nowait() == "/api/chat"
    assert _nothing_arrived(proxy_arrivals)


def test_remote_request_keeps_environment_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reader the person reaches through a proxy still goes through it."""
    proxy_arrivals = _fresh()
    _Proxy.arrivals = proxy_arrivals
    with serving_loopback(_Proxy, path="/api/chat") as proxy_url:
        _route_through_proxy(monkeypatch, proxy_url)
        with override_settings(cadrumo_llm_ollama_chat_url="http://reader.example.test:11434/api/chat"):
            completion = _complete()

    assert completion.text == "from the proxy"
    assert proxy_arrivals.get_nowait() == "http://reader.example.test:11434/api/chat"


def test_loopback_request_does_not_follow_a_redirect_to_another_host() -> None:
    redirect_arrivals, bystander_arrivals = _fresh(), _fresh()
    _Redirecting.arrivals = redirect_arrivals
    _Bystander.arrivals = bystander_arrivals
    with (
        serving_loopback(_Bystander, path="/api/chat") as bystander_url,
        serving_loopback(_Redirecting, path="/api/chat") as redirecting_url,
    ):
        _Redirecting.location = bystander_url
        with (
            override_settings(cadrumo_llm_ollama_chat_url=redirecting_url),
            pytest.raises(LLMProviderError),
        ):
            _complete()

    assert redirect_arrivals.get_nowait() == "/api/chat"
    assert _nothing_arrived(bystander_arrivals)
