"""Local provider adapter for Ollama-compatible runtimes.

Speaks the Ollama ``/api/chat`` endpoint (resolved per call from
``Settings.cadrumo_llm_ollama_chat_url``) and adapts its response into the
:class:`~llm.providers.base.ProviderCompletion` shape.
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

from ...core import LLM_EXTRA, require_optional_extra
from ...core.config import load_settings
from ..errors import LLMPdfRasterisationError
from ..models import LLMProvider
from .base import (
    ProviderAdapter,
    ProviderCompletion,
    ProviderRequest,
    check_http_error,
    parse_provider_response,
    post_provider_request,
)

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

    Raises:
        MissingOptionalExtraError: If the ``llm`` extra is not installed.
        LLMPdfRasterisationError: If the PDF cannot be rendered.
    """
    # The feature-boundary guard sits ahead of the lazy import, per the
    # established convention. What it refuses is an operator who reached the
    # rasteriser without opting into the inference closure at all; the refusal
    # names the install command instead of letting the render proceed into a
    # boundary the rest of the extra is absent from. It does NOT stand in for a
    # missing Pillow -- Pillow is an unconditional base dependency, so its
    # absence is a broken installation rather than a declined extra, and the
    # bare ``except Exception`` below correctly owns the render failures that
    # remain.
    require_optional_extra(LLM_EXTRA)
    import pypdfium2 as pdfium  # lazy: keep the adapter import light, mirror the declaración fast-path

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise LLMPdfRasterisationError(
            context={"rasterisation_stage": "document_open", "rasterisation_error_type": type(exc).__name__},
        ) from exc
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
        raise LLMPdfRasterisationError(
            context={"rasterisation_stage": "page_render", "rasterisation_error_type": type(exc).__name__},
        ) from exc
    finally:
        document.close()


class _LocalMessage(BaseModel):
    """Single message returned in an Ollama chat response."""

    # NOT the canonical STRICT_FROZEN_CONFIG: this parses a THIRD-PARTY response
    # envelope, and the canonical forbids extra fields. The runtime sends keys we
    # do not declare -- `message.role` among them -- so forbidding extras rejects
    # a valid response. Tolerating unknown keys is the contract at a boundary we
    # do not own; strictness here belongs on the fields we DO declare.
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


class LocalAdapter(ProviderAdapter):
    """Provider adapter that invokes a local Ollama-compatible HTTP endpoint."""

    provider = LLMProvider.LOCAL
    supports_images = True

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
            user_message["images"] = [image.base64_data for image in request.images]
        messages.append(user_message)
        settings = load_settings()
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await post_provider_request(
                client,
                settings.cadrumo_llm_ollama_chat_url,
                provider_name=LLMProvider.LOCAL.value,
                model=request.model,
                logger=_LOG,
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
                        "num_ctx": settings.cadrumo_llm_ollama_num_ctx,
                    },
                },
            )
        check_http_error(response, provider_name=LLMProvider.LOCAL.value, model=request.model, logger=_LOG)
        parsed = parse_provider_response(response, provider_name=LLMProvider.LOCAL.value, response_model=_LocalResponse)
        return ProviderCompletion(
            text=parsed.message.content.strip(),
            model=parsed.model,
            input_tokens=parsed.prompt_eval_count,
            output_tokens=parsed.eval_count,
            provider_request_id=None,
        )
