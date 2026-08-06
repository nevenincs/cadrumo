"""Loopback tests for malformed successful LLM provider responses."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar, override

import pytest

from ......core.config import override_settings
from ..._errors import LLMProviderError
from ..base import ProviderRequest
from ..gemini import GeminiAdapter
from ..local import LocalAdapter
from ..openai import OpenAIAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _MalformedResponseEndpoint(BaseHTTPRequestHandler):
    """Loopback endpoint that returns a configured malformed JSON response."""

    payload: ClassVar[object]

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        encoded = json.dumps(self.payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""


@contextmanager
def _serve_malformed_response(payload: object) -> Iterator[str]:
    _MalformedResponseEndpoint.payload = payload
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MalformedResponseEndpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/completion"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="malformed-response",
        model="test-model",
        prompt="hello",
        max_tokens=32,
        temperature=0.0,
        timeout_s=3,
    )


def test_openai_empty_choices_becomes_provider_error() -> None:
    """An OpenAI-shaped 2xx response without a choice stays in the declared error boundary."""

    payload = {
        "id": "response-id",
        "model": "test-model",
        "choices": [],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }
    with (
        _serve_malformed_response(payload) as endpoint,
        override_settings(cadrumo_llm_openai_chat_completions_url=endpoint),
        pytest.raises(LLMProviderError, match="OpenAI returned no choices"),
    ):
        asyncio.run(OpenAIAdapter("openai-secret", timeout_s=3).complete(_request()))


def test_gemini_empty_candidates_becomes_provider_error() -> None:
    """A Gemini-shaped 2xx response without a candidate stays in the declared error boundary."""

    with (
        _serve_malformed_response({"candidates": []}) as endpoint,
        override_settings(cadrumo_llm_gemini_generate_content_template=f"{endpoint}/{{model}}"),
        pytest.raises(LLMProviderError, match="Gemini returned no candidates"),
    ):
        asyncio.run(GeminiAdapter("gemini-secret", timeout_s=3).complete(_request()))


@pytest.mark.parametrize("message", ({}, {"content": []}))
def test_local_missing_or_invalid_message_content_becomes_provider_error(message: object) -> None:
    """A local 2xx body with no usable message content raises a declared provider error."""

    with (
        _serve_malformed_response({"model": "test-model", "message": message}) as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
        pytest.raises(LLMProviderError, match="Local Ollama returned an invalid response"),
    ):
        asyncio.run(LocalAdapter(timeout_s=3).complete(_request()))
