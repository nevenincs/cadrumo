"""On-host vision read: in-memory PDF rasterisation plus the LocalAdapter images path.

Proves a scan-only PDF is rasterised to base64 PNG pages fully in process memory
and that :class:`aeat.adapters.outbound.llm._providers.local.LocalAdapter`
forwards those images on the Ollama ``images`` message field to a loopback
endpoint -- so a local vision model can read the document with no byte leaving
the host (``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue
from typing import ClassVar, override

import pytest
from PIL import Image

from .....core.config import override_settings
from .._providers.base import ProviderRequest
from .._providers.local import LocalAdapter, rasterise_pdf_pages_to_base64_png

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _scan_only_pdf() -> bytes:
    """Build a one-page raster (text-layer-free) PDF in memory."""
    image = Image.new("RGB", (240, 140), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PDF")
    return buffer.getvalue()


def test_rasterise_pdf_pages_to_base64_png_returns_in_memory_png() -> None:
    """A scan-only PDF rasterises to a base64 PNG page, fully in memory."""
    pages = rasterise_pdf_pages_to_base64_png(_scan_only_pdf())

    assert len(pages) == 1
    decoded = base64.b64decode(pages[0])
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


class _ObservedOllamaRequest(BaseHTTPRequestHandler):
    """Local Ollama-shaped endpoint that captures the posted chat body."""

    events: ClassVar[Queue[dict[str, object]]]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put({"body": json.loads(body.decode("utf-8"))})
        payload = {
            "model": "gpt-oss",
            "message": {"content": " vision read "},
            "prompt_eval_count": 11,
            "eval_count": 4,
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


def test_local_adapter_forwards_rasterised_images_to_loopback() -> None:
    """The LocalAdapter sends the rasterised base64 images on the Ollama images field."""
    images = rasterise_pdf_pages_to_base64_png(_scan_only_pdf())
    events: Queue[dict[str, object]] = Queue()
    _ObservedOllamaRequest.events = events
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ObservedOllamaRequest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/chat"

    request = ProviderRequest(
        request_id="req",
        model="gpt-oss",
        prompt="Read the attached invoice and report the total.",
        system=None,
        max_tokens=64,
        temperature=0.0,
        timeout_s=3,
        images=images,
    )
    try:
        with override_settings(aeat_llm_ollama_chat_url=endpoint):
            completion = asyncio.run(LocalAdapter(timeout_s=3).complete(request))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    observed = events.get_nowait()
    body = observed["body"]
    assert isinstance(body, dict)
    messages = body["messages"]  # ty: ignore[invalid-argument-type]  # narrowed by isinstance above
    assert isinstance(messages, list)
    user_message = messages[-1]
    assert isinstance(user_message, dict)
    assert user_message["role"] == "user"  # ty: ignore[invalid-argument-type]  # narrowed by isinstance above
    assert user_message["images"] == list(images)  # ty: ignore[invalid-argument-type]  # narrowed by isinstance above
    assert completion.text == "vision read"
    assert completion.input_tokens == 11
    assert completion.output_tokens == 4
