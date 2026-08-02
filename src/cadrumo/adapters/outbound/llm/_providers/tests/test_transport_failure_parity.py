"""One unreachable endpoint, one error type, whichever provider is configured.

``LLMProviderError`` is the declared transport/provider boundary of this
subpackage. Gemini caught :exc:`httpx.RequestError` and mapped it there, and
the Anthropic adapter maps its SDK's connection and timeout failures to the
same hierarchy — but OpenAI and the local runtime called ``client.post`` bare,
so the same unreachable endpoint escaped as a raw ``httpx`` ``ConnectError``.
The error TYPE, and therefore every caller's recovery path, depended on which
provider happened to be configured.

The failure is induced by pointing each adapter at a real TCP port that
nothing is listening on: a genuine connection refusal through the real client,
with nothing patched or doubled. Anthropic is absent because its transport is
the vendor SDK rather than this subpackage's ``httpx`` path; its mapping is
covered where that adapter is exercised.
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable

import pytest

from ......core.config import override_settings
from ..._errors import LLMProviderError
from ..base import ProviderRequest, _ProviderAdapter
from ..gemini import GeminiAdapter
from ..local import LocalAdapter
from ..openai import OpenAIAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _unused_port() -> int:
    """Return a TCP port that nothing is listening on.

    Binding and immediately releasing is how the sibling Gemini test finds
    one; the refusal that follows is a real kernel connection refusal, not a
    simulated failure.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="a" * 64,
        model="unreachable-model",
        prompt="Explain casilla 03.",
        max_tokens=32,
        temperature=0.0,
        timeout_s=1,
    )


def _gemini(port: int) -> tuple[dict[str, str], Callable[[], _ProviderAdapter]]:
    endpoint = f"http://127.0.0.1:{port}/v1beta/models/{{model}}:generateContent"
    return {"cadrumo_llm_gemini_generate_content_template": endpoint}, lambda: GeminiAdapter(
        "gemini-secret",
        timeout_s=1,
    )


def _openai(port: int) -> tuple[dict[str, str], Callable[[], _ProviderAdapter]]:
    endpoint = f"http://127.0.0.1:{port}/v1/chat/completions"
    return {"cadrumo_llm_openai_chat_completions_url": endpoint}, lambda: OpenAIAdapter(
        "openai-secret",
        timeout_s=1,
    )


def _local(port: int) -> tuple[dict[str, str], Callable[[], _ProviderAdapter]]:
    endpoint = f"http://127.0.0.1:{port}/api/chat"
    return {"cadrumo_llm_ollama_chat_url": endpoint}, lambda: LocalAdapter(timeout_s=1)


_ADAPTERS = (
    pytest.param(_gemini, "Gemini", id="gemini"),
    pytest.param(_openai, "OpenAI", id="openai"),
    pytest.param(_local, "Local Ollama", id="local"),
)


@pytest.mark.parametrize(("build", "provider_name"), _ADAPTERS)
def test_an_unreachable_endpoint_raises_the_typed_provider_error(
    build: Callable[[int], tuple[dict[str, str], Callable[[], _ProviderAdapter]]],
    provider_name: str,
) -> None:
    """Every httpx-backed adapter answers a refused connection identically.

    Pre-fix, ``openai`` and ``local`` raised ``httpx.ConnectError`` here — not
    an ``LLMProviderError`` — so a caller that handled the typed boundary
    crashed on two providers out of four.
    """
    settings_override, make_adapter = build(_unused_port())

    with (
        override_settings(**settings_override),
        pytest.raises(LLMProviderError, match=f"{provider_name} connection failure"),
    ):
        asyncio.run(make_adapter().complete(_request()))


@pytest.mark.parametrize(("build", "provider_name"), _ADAPTERS)
def test_the_refusal_carries_the_underlying_transport_failure(
    build: Callable[[int], tuple[dict[str, str], Callable[[], _ProviderAdapter]]],
    provider_name: str,
) -> None:
    """The raw failure is chained, not discarded.

    A typed boundary that swallowed the cause would trade a leaked exception
    for an undiagnosable one; the operator still needs to see whether the
    endpoint refused, resolved, or timed out.
    """
    settings_override, make_adapter = build(_unused_port())

    with override_settings(**settings_override), pytest.raises(LLMProviderError) as raised:
        asyncio.run(make_adapter().complete(_request()))

    assert raised.value.__cause__ is not None
    assert provider_name in str(raised.value)
