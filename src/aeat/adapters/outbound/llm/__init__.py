"""LLM client, prompt registry, cache, and translation helpers.

The public API is exported from this package root so callers never need to
import internal provider or storage modules directly. Public surface
includes :class:`LLMClient` for completions, :class:`LLMCache` for the
on-disk content-addressed cache, :class:`PromptRegistry` for versioned
prompt templates, :class:`Translator` / :class:`BulkTranslator` for the
translation workflow, and the :class:`LLMError` exception hierarchy.

Examples:
    Issue a completion via the high-level client::

        import asyncio
        from aeat.adapters.outbound.llm import LLMClient, LLMRequest

        async def main() -> None:
            client = LLMClient()
            response = await client.complete(
                LLMRequest(prompt="Summarize Modelo 130 in one sentence.")
            )
            print(response.text)

        asyncio.run(main())
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
    PromptDefinition,
    PromptRegistry,
    Translation,
    UsageRecord,
    UsageSummary,
)
from ._translator import BulkTranslator, Translator
from ._usage import UsageRecorder

__all__ = [
    "BulkTranslator",
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
    "PromptDefinition",
    "PromptRegistry",
    "Translation",
    "Translator",
    "UsageRecord",
    "UsageRecorder",
    "UsageSummary",
]
