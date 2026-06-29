"""Local provider adapter for Ollama-compatible runtimes.

Speaks the Ollama ``/api/chat`` endpoint (resolved per call from
``Settings.aeat_llm_ollama_chat_url``) and adapts its response into the
:class:`aeat.adapters.outbound.llm._providers.base.ProviderCompletion` shape.
The adapter assumes the runtime is reachable on localhost; remote Ollama
deployments are out of scope.

For multimodal evidence, :func:`rasterise_pdf_pages_to_base64_png` renders an
in-memory PDF to base64 PNG pages fully on-host so a local vision model can read
a scan-only invoice; the adapter forwards those base64 images on the Ollama
``images`` message field. No file is written and nothing leaves the host
(``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Protocol, cast, override

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .....core.config import load_settings
from .._errors import LLMPdfRasterisationError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter, check_http_error

_LOG = logging.getLogger(__name__)


class _PillowImageLike(Protocol):
    def save(self, fp: BytesIO, format: str | None = None) -> None: ...


class _PdfiumBitmapLike(Protocol):
    def to_pil(self) -> _PillowImageLike: ...

    def close(self) -> None: ...


class _PdfiumPageLike(Protocol):
    def render(self, *, scale: float) -> _PdfiumBitmapLike: ...

    def close(self) -> None: ...


def rasterise_pdf_pages_to_base64_png(pdf_bytes: bytes, *, scale: float = 2.0) -> tuple[str, ...]:
    """Rasterise each page of an in-memory PDF to a base64-encoded PNG, on-host.

    Renders every page in process memory via pypdfium2 and Pillow so a local
    vision model can read a scan-only or image-only PDF that has no extractable
    text layer. Nothing is written to disk and nothing leaves the host
    (``sensitive-financial-data-secure-storage-only``).

    Args:
        pdf_bytes: In-memory PDF bytes (read transiently from secure storage).
        scale: pypdfium2 render scale; a larger value yields a larger raster.

    Returns:
        One base64-encoded PNG string per page, in page order.
    """
    import pypdfium2 as pdfium  # lazy: keep the adapter import light, mirror the declaración fast-path

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise LLMPdfRasterisationError(f"could not rasterise PDF pages: {exc}") from exc
    try:
        pages: list[str] = []
        for page in document:
            # CAST-RATIONALE-PDFIUM-PAGE: pypdfium2 yields untyped page objects; the adapter only needs render/close.
            pdf_page = cast("_PdfiumPageLike", page)
            try:
                bitmap = pdf_page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    pages.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
                finally:
                    bitmap.close()
            finally:
                pdf_page.close()
        return tuple(pages)
    except Exception as exc:
        raise LLMPdfRasterisationError(f"could not rasterise PDF pages: {exc}") from exc
    finally:
        document.close()


class _LocalMessage(BaseModel):
    """Single message returned in an Ollama chat response."""

    model_config = ConfigDict(strict=True, frozen=True)

    content: str


class _LocalResponse(BaseModel):
    """Top-level Ollama chat response envelope.

    Attributes:
        model: Model identifier reported by the runtime.
        message: Generated message payload.
        prompt_eval_count: Tokens evaluated for the prompt.
        eval_count: Tokens evaluated for the generated output.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    model: str
    message: _LocalMessage
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


class LocalAdapter(_ProviderAdapter):
    """Provider adapter that invokes a local Ollama-compatible HTTP endpoint."""

    provider = LLMProvider.LOCAL

    def __init__(self, timeout_s: int) -> None:
        """Initialize the adapter.

        Args:
            timeout_s: Per-request HTTP timeout in seconds.
        """
        self._timeout_s = timeout_s

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Execute a chat completion request against the local endpoint.

        Args:
            request: Normalized provider request.

        Returns:
            :class:`ProviderCompletion` containing the trimmed assistant message
            and reported token counts.

        Raises:
            LLMProviderError: When the runtime returns a non-2xx HTTP error status.
        """
        messages: list[dict[str, object]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        user_message: dict[str, object] = {"role": "user", "content": request.prompt}
        if request.images:
            # Ollama carries multimodal inputs as base64 strings on the message
            # ``images`` field; only present them when a vision read supplied them.
            user_message["images"] = list(request.images)
        messages.append(user_message)
        settings = load_settings()
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                settings.aeat_llm_ollama_chat_url,
                json={
                    "model": request.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens,
                        # A vision request packs the allow-list prompt plus the encoded
                        # invoice image past Ollama's 4096 default context; size the
                        # window from settings so the request is not truncated/rejected.
                        "num_ctx": settings.aeat_llm_ollama_num_ctx,
                    },
                },
            )
        check_http_error(response, provider_name="Local Ollama", model=request.model, logger=_LOG)
        parsed = _LocalResponse.model_validate_json(response.text)
        return ProviderCompletion(
            text=parsed.message.content.strip(),
            model=parsed.model,
            input_tokens=parsed.prompt_eval_count,
            output_tokens=parsed.eval_count,
            provider_request_id=None,
        )
