"""On-host vision read: in-memory PDF rasterisation plus the LocalAdapter images path.

Proves a scan-only PDF is rasterised to base64 PNG pages fully in process memory
and that :class:`cadrumo.llm.providers.local.LocalAdapter`
forwards those images on the Ollama ``images`` message field to a loopback
endpoint -- so a local vision model can read the document with no byte leaving
the host (``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

import asyncio
import base64
import io
from collections.abc import Mapping
from http import HTTPStatus
from queue import Queue
from typing import ClassVar, override

import pytest
from PIL import Image

from ...core.config import override_settings
from ...core.image_media_type import ImageMediaType
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..models import MultimodalImageInput
from ..providers.base import ProviderRequest
from ..providers.local import LocalAdapter, rasterise_pdf_pages_to_base64_png

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


class _ObservedOllamaRequest(SilentLoopbackHandler):
    """Local Ollama-shaped endpoint that captures the posted chat body."""

    events: ClassVar[Queue[dict[str, object]]]

    @override
    def do_POST(self) -> None:
        self.events.put({"body": read_json_body(self)})
        write_json_response(
            self,
            ollama_chat_reply(" vision read ", prompt_eval_count=11),
            status=HTTPStatus.OK,
        )


def test_local_adapter_forwards_rasterised_images_to_loopback() -> None:
    """The LocalAdapter sends the rasterised base64 images on the Ollama images field."""
    images = tuple(
        MultimodalImageInput.from_base64(page, ImageMediaType.PNG)
        for page in rasterise_pdf_pages_to_base64_png(_scan_only_pdf())
    )
    events: Queue[dict[str, object]] = Queue()
    _ObservedOllamaRequest.events = events
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
    with (
        serving_loopback(_ObservedOllamaRequest, path="/api/chat") as endpoint,
        override_settings(cadrumo_llm_ollama_chat_url=endpoint),
    ):
        completion = asyncio.run(LocalAdapter(timeout_s=3).complete(request))

    observed = events.get_nowait()
    body = observed["body"]
    assert isinstance(body, Mapping)
    messages = body.get("messages")
    assert isinstance(messages, list)
    user_message = messages[-1]
    assert isinstance(user_message, Mapping)
    assert user_message.get("role") == "user"
    assert user_message.get("images") == [image.base64_data for image in images]
    assert completion.text == "vision read"
    assert completion.input_tokens == 11
    assert completion.output_tokens == 4
