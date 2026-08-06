"""Public facade for outbound model-provider completion adapters.

The package root defines the ``__all__`` contract for public imports. Use these
top-level re-exports for :class:`LLMClient`, :class:`LLMRequest`,
:class:`LLMResponse`, :class:`LLMProvider`, cache records
(:class:`LLMCache`, :class:`CacheKey`, :class:`CacheStats`,
:class:`CachedEntry`), prompt types (:class:`PromptRegistry` and
:class:`PromptDefinition`), usage records (:class:`UsageRecorder`,
:class:`UsageRecord`, and :class:`UsageSummary`), model records
(:class:`Translation` and :class:`MultimodalImageInput`), rasterisation, and
exported error types.

The async-first :meth:`LLMClient.complete` flow reads :class:`LLMCache` before a
provider call, writes content-addressed encrypted cache entries on misses,
records usage on hits and misses, and returns :class:`LLMResponse`.
Cache types include :class:`CacheKey`, :class:`CacheStats`, and
:class:`CachedEntry`; persisted cache data is encrypted secure-object storage,
not plaintext files.

Prompt handling uses :class:`PromptRegistry` and :class:`PromptDefinition` for
versioned prompt definitions/templates. :class:`UsageRecorder` persists
redacted :class:`UsageRecord` values to encrypted secure-object storage and
produces :class:`UsageSummary` reports. :class:`LLMRunTelemetryRecorder`
persists local-only :class:`LLMRunRecord` run-timing/outcome metadata (never
prompt or response text) and produces :class:`LLMRunTelemetrySummary` reports,
backing the ``aeat app diagnostics run-health`` operator surface. Strict model
types include :class:`Translation` and transient :class:`MultimodalImageInput`,
whose base64 bytes are not persisted; only content SHA participates in cache
keys.

Use :func:`rasterise_pdf_pages_to_base64_png` for in-memory, on-host PDF-to-PNG
rasterisation for local vision inputs. Exported exceptions include
:exc:`LLMError`, :exc:`LLMCacheError`, :exc:`LLMConfigError`,
:exc:`LLMPdfRasterisationError`, :exc:`LLMProviderError`, and
:exc:`LLMRateLimitError`. Importing this outbound adapter must remain silent.

Examples:
    Issue a completion via the high-level client:

    >>> import asyncio
    >>> from cadrumo.adapters.outbound.llm import LLMClient, LLMRequest
    >>> async def main() -> None:
    ...     client = LLMClient()
    ...     response = await client.complete(
    ...         LLMRequest(prompt="Summarize the requested modelo in one sentence.")
    ...     )
    ...     # response.text contains the completion; print in real usage
    >>> # asyncio.run(main())  # requires a live LLM provider; omitted from doctest
"""

from ._cache import LLMCache
from ._client import LLMClient
from ._errors import (
    LLMCacheError,
    LLMConfigError,
    LLMError,
    LLMPdfRasterisationError,
    LLMProviderError,
    LLMRateLimitError,
)
from ._models import (
    CachedEntry,
    CacheKey,
    CacheStats,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MultimodalImageInput,
    PromptDefinition,
    PromptRegistry,
    Translation,
    UsageRecord,
    UsageSummary,
)
from ._providers import rasterise_pdf_pages_to_base64_png
from ._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder, LLMRunTelemetrySummary
from ._usage import UsageRecorder

__all__ = [
    "CacheKey",
    "CacheStats",
    "CachedEntry",
    "LLMCache",
    "LLMCacheError",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMPdfRasterisationError",
    "LLMProvider",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "LLMRunRecord",
    "LLMRunTelemetryRecorder",
    "LLMRunTelemetrySummary",
    "MultimodalImageInput",
    "PromptDefinition",
    "PromptRegistry",
    "Translation",
    "UsageRecord",
    "UsageRecorder",
    "UsageSummary",
    "rasterise_pdf_pages_to_base64_png",
]
