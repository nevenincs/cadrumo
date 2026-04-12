"""LLM client, prompt registry, cache, and translation helpers.

The public API is exported from this package root so callers never need to
import internal provider or storage modules directly.

Example:
    ```python
    import asyncio

    from aeat.llm import LLMClient, LLMRequest

    async def main() -> None:
        client = LLMClient()
        response = await client.complete(
            LLMRequest(prompt="Summarize Modelo 130 in one sentence.")
        )
        print(response.text)

    asyncio.run(main())
    ```
"""

from aeat.llm._cache import LLMCache
from aeat.llm._client import LLMClient
from aeat.llm._errors import (
    LLMCacheError,
    LLMConfigError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
)
from aeat.llm._models import (
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
from aeat.llm._providers import ProviderRequest, _FakeAdapter
from aeat.llm._translator import BulkTranslator, Translator
from aeat.llm._usage import UsageRecorder

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
    "ProviderRequest",
    "Translation",
    "Translator",
    "UsageRecord",
    "UsageRecorder",
    "UsageSummary",
    "_FakeAdapter",
]
