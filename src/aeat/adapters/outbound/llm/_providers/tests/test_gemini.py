"""Behaviour tests for the Gemini LLM provider adapter."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
from typing import ClassVar, override

import pytest

from ......core.config import override_settings
from ..._errors import LLMProviderError
from ..base import ProviderRequest
from ..gemini import GeminiAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _ObservedGeminiRequest(BaseHTTPRequestHandler):
    """Local Gemini-shaped endpoint used to inspect the real HTTP request."""

    events: ClassVar[Queue[dict[str, object]]]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put(
            {
                "path": self.path,
                "api_key_header": self.headers.get("x-goog-api-key"),
                "body": json.loads(body.decode("utf-8")),
            }
        )
        payload = {
            "candidates": [{"content": {"parts": [{"text": " Gemini response "}]}}],
            "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""


def _request() -> ProviderRequest:
    return ProviderRequest(
        request_id="req",
        model="gemini-test-model",
        prompt="hello",
        system="follow Spanish tax terminology",
        max_tokens=32,
        temperature=0.0,
        timeout_s=3,
    )


def test_gemini_uses_central_endpoint_setting_and_api_key_header() -> None:
    """The adapter must use settings for the URL and keep the API key out of the query string."""

    events: Queue[dict[str, object]] = Queue()
    _ObservedGeminiRequest.events = events
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ObservedGeminiRequest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1beta/models/{{model}}:generateContent"

    try:
        with override_settings(aeat_llm_gemini_generate_content_template=endpoint):
            completion = asyncio.run(GeminiAdapter("gemini-secret", timeout_s=3).complete(_request()))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    observed = events.get_nowait()
    body = observed["body"]
    assert completion.text == "Gemini response"
    assert completion.input_tokens == 7
    assert completion.output_tokens == 3
    assert observed["path"] == "/v1beta/models/gemini-test-model:generateContent"
    assert observed["api_key_header"] == "gemini-secret"
    assert "gemini-secret" not in str(observed["path"])
    assert isinstance(body, dict)
    assert body["generationConfig"] == {"temperature": 0.0, "maxOutputTokens": 32}  # ty: ignore[invalid-argument-type]  # narrowed by isinstance above


def test_gemini_transport_failure_raises_llm_provider_error() -> None:
    """Connection failures must not escape as raw httpx exceptions."""

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    endpoint = f"http://127.0.0.1:{unused_port}/v1beta/models/{{model}}:generateContent"

    with (
        override_settings(aeat_llm_gemini_generate_content_template=endpoint),
        pytest.raises(LLMProviderError, match="Gemini connection failure"),
    ):
        asyncio.run(GeminiAdapter("gemini-secret", timeout_s=1).complete(_request()))
