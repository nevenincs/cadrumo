"""Translation helpers layered on top of the public LLM client.

Provides a high-level :class:`Translator` for single-text translation and a
:class:`BulkTranslator` for concurrent batches with built-in rate-limit
backoff. Both delegate prompt rendering and provider invocation to
:class:`aeat.adapters.outbound.llm.LLMClient` and the
``translation_v1`` prompt in :class:`aeat.adapters.outbound.llm.PromptRegistry`.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable, Sequence

from ....core.config import Settings
from ....core.i18n import normalize_language_code
from ....core.logging import get_logger
from ._client import LLMClient
from ._errors import LLMRateLimitError
from ._models import LLMRequest, PromptRegistry, Translation
from ._prompts import render_prompt

_log = get_logger(__name__)


class Translator:
    """High-level translation API backed by :class:`LLMClient`.

    Attributes:
        client: Underlying LLM client used to issue completion requests.
        prompt_registry: Prompt registry consulted for the
            ``translation_v1`` template.
    """

    def __init__(self, client: LLMClient | None = None, prompt_registry: PromptRegistry | None = None) -> None:
        """Initialize the translator.

        Args:
            client: Shared LLM client instance; a new caller-tagged client is
                created when omitted.
            prompt_registry: Prompt registry override; defaults to the registry
                exposed by the chosen :attr:`client`.
        """
        self.client = client or LLMClient(caller="aeat.adapters.outbound.llm.translator", prompt_id="translation_v1")
        self.prompt_registry = prompt_registry or self.client.prompt_registry

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        *,
        context: str | None = None,
    ) -> Translation:
        """Translate ``text`` from ``source_lang`` into ``target_lang``.

        The system prompt instructs the model to preserve numbers and field
        identifiers verbatim, which matters for legal and tax content.

        Args:
            text: Source text to translate.
            source_lang: Source ISO 639-1 language code.
            target_lang: Target ISO 639-1 language code.
            context: Optional translation context surfaced to the model.

        Returns:
            Structured :class:`Translation` carrying the translated text,
            normalized language codes, and provider accounting metadata.
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
    """Translate many texts concurrently with rate-limit-aware retry.

    Concurrency is bounded by an :class:`asyncio.Semaphore`; rate-limit
    failures from :class:`LLMRateLimitError` are retried with jittered
    exponential backoff, capped at :attr:`max_retries`.

    Attributes:
        translator: Underlying single-text translator.
        concurrency: Maximum number of in-flight translations.
        max_retries: Maximum retry attempts for rate-limit failures.
    """

    def __init__(
        self,
        translator: Translator | None = None,
        *,
        concurrency: int = 5,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the bulk translator.

        Args:
            translator: Translator override; a new :class:`Translator` is
                created when omitted.
            concurrency: Maximum concurrent in-flight translations.
            max_retries: Override for rate-limit retry attempts; falls back to
                :attr:`aeat.core.config.Settings.aeat_llm_max_retries`.
        """
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
            context: Optional translation context shared by every text.
            progress: Optional progress callback invoked as
                ``progress(completed, total)`` after each item finishes.

        Returns:
            Completed translations in the same order as ``texts``.
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
        """Translate one text, retrying rate-limit failures with backoff.

        On :exc:`LLMRateLimitError` the call is retried up to
        :attr:`max_retries` times, sleeping for ``retry_after_seconds``
        (or a capped exponential fallback) plus a small random jitter
        sourced from :func:`secrets.randbelow`.

        Args:
            text: Source text to translate.
            source_lang: Source ISO 639-1 language code.
            target_lang: Target ISO 639-1 language code.
            context: Optional translation context.

        Returns:
            Completed :class:`Translation`.

        Raises:
            :exc:`aeat.adapters.outbound.llm.LLMRateLimitError`: Re-raised
                after :attr:`max_retries` is exhausted.
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
                _log.warning(
                    "translator: rate limit hit attempt=%d/%d retry_after=%.2fs",
                    attempt,
                    self.max_retries,
                    retry_after,
                )
                await asyncio.sleep(retry_after + (secrets.randbelow(26) / 100))
