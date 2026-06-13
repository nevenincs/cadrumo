"""LLM client, prompt registry, and cache.

The public API is exported from this package root so callers never need to
import internal provider or storage modules directly. Public surface
includes :class:`LLMClient` for completions, :class:`LLMCache` for the
on-disk content-addressed cache, :class:`PromptRegistry` for versioned
prompt templates, and the :class:`LLMError` exception hierarchy.

Examples:
    Issue a completion via the high-level client:

    >>> import asyncio
    >>> from aeat.adapters.outbound.llm import LLMClient, LLMRequest
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
    "LLMProvider",
    "LLMProviderError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "MultimodalImageInput",
    "PromptDefinition",
    "PromptRegistry",
    "Translation",
    "UsageRecord",
    "UsageRecorder",
    "UsageSummary",
]
