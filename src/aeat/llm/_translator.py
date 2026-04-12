"""Translation helpers built on top of the public LLM client."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable, Sequence

from aeat.config import Settings
from aeat.llm._client import LLMClient
from aeat.llm._errors import LLMRateLimitError
from aeat.llm._i18n_compat import normalize_language_code
from aeat.llm._models import LLMRequest, PromptRegistry, Translation
from aeat.llm._prompts import render_prompt


class Translator:
    """High-level translation API backed by `LLMClient`.

    Args:
        client: Optional shared LLM client instance.
        prompt_registry: Optional prompt registry override.
    """

    def __init__(self, client: LLMClient | None = None, prompt_registry: PromptRegistry | None = None) -> None:
        self.client = client or LLMClient(caller="aeat.llm.translator", prompt_id="translation_v1")
        self.prompt_registry = prompt_registry or self.client.prompt_registry

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        context: str | None = None,
    ) -> Translation:
        """Translate text between two languages.

        Args:
            text: Source text to translate.
            source_lang: Source ISO 639-1 language code.
            target_lang: Target ISO 639-1 language code.
            context: Optional translation context.

        Returns:
            Structured translation result.
        """

        normalized_source = normalize_language_code(source_lang)
        normalized_target = normalize_language_code(target_lang)
        prompt = self.prompt_registry.get("translation_v1")
        rendered_prompt = render_prompt(
            prompt,
            {
                "source_lang": normalized_source,
                "target_lang": normalized_target,
                "context": context or "(none)",
                "text": text,
            },
        )
        response = await self.client.complete(
            LLMRequest(
                prompt=rendered_prompt,
                system=(
                    "You are a legal and tax translation assistant. Translate faithfully, preserve numbers and "
                    "field identifiers, and avoid adding commentary."
                ),
                temperature=0.0,
                language=normalized_target,
                cache_key=f"{prompt.id}:{prompt.version}:{normalized_source}:{normalized_target}",
            )
        )
        return Translation(
            text=response.text,
            source_lang=normalized_source,
            target_lang=normalized_target,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            created_at=response.created_at,
        )


class BulkTranslator:
    """Translate many texts concurrently with retry handling.

    Args:
        translator: Optional translator override.
        concurrency: Maximum concurrent in-flight translations.
        max_retries: Optional retry override for rate-limit failures.
    """

    def __init__(
        self,
        translator: Translator | None = None,
        *,
        concurrency: int = 5,
        max_retries: int | None = None,
    ) -> None:
        self.translator = translator or Translator()
        settings = self.translator.client.settings if self.translator.client else Settings()
        self.concurrency = concurrency
        self.max_retries = max_retries or settings.aeat_llm_max_retries

    async def translate_many(
        self,
        texts: Sequence[str],
        source_lang: str,
        target_lang: str,
        *,
        context: str | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> tuple[Translation, ...]:
        """Translate many texts while honoring provider rate limits.

        Args:
            texts: Source texts to translate.
            source_lang: Source ISO 639-1 language code.
            target_lang: Target ISO 639-1 language code.
            context: Optional translation context.
            progress: Optional progress callback receiving completed and total
                counts.

        Returns:
            Completed translations in input order.
        """

        semaphore = asyncio.Semaphore(self.concurrency)
        total = len(texts)
        completed = 0
        results: list[Translation | None] = [None] * total

        async def worker(index: int, item: str) -> None:
            nonlocal completed
            async with semaphore:
                results[index] = await self._translate_with_retry(item, source_lang, target_lang, context=context)
                completed += 1
                if progress is not None:
                    progress(completed, total)

        await asyncio.gather(*(worker(index, item) for index, item in enumerate(texts)))
        return tuple(item for item in results if item is not None)

    async def _translate_with_retry(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        context: str | None = None,
    ) -> Translation:
        """Retry on provider rate limits with jittered exponential backoff.

        Args:
            text: Source text to translate.
            source_lang: Source ISO 639-1 language code.
            target_lang: Target ISO 639-1 language code.
            context: Optional translation context.

        Returns:
            Completed translation result.
        """

        attempt = 0
        while True:
            try:
                return await self.translator.translate(text, source_lang, target_lang, context=context)
            except LLMRateLimitError as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                retry_after = exc.retry_after_seconds or min(2**attempt, 8)
                await asyncio.sleep(retry_after + (secrets.randbelow(26) / 100))
