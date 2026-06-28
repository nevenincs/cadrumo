"""Deterministic in-memory provider adapter used by unit tests.

Implements the :class:`aeat.adapters.outbound.llm._providers.base._ProviderAdapter`
contract without performing any network I/O so :mod:`aeat.adapters.outbound.llm`
unit tests can exercise the public client end-to-end without patches or
network test doubles.
"""

from __future__ import annotations

from typing import override

from .._errors import LLMProviderError, LLMRateLimitError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter


class _DeterministicAdapter(_ProviderAdapter):
    """In-memory adapter that returns reproducible completions or canned errors.

    The adapter echoes the prompt back inside :attr:`response_text` so tests
    can assert that the request actually reached the adapter, and exposes
    :attr:`calls` for invocation counting.

    Attributes:
        response_text: Prefix concatenated with the prompt to form the completion.
        model: Reported model identifier.
        input_tokens: Synthetic prompt token count.
        output_tokens: Synthetic output token count.
        error_mode: When set to ``"provider"`` or ``"rate-limit"``, the next
            :meth:`complete` call raises the matching error; otherwise ``None``.
        calls: Running total of :meth:`complete` invocations.
    """

    provider = LLMProvider.ANTHROPIC

    def __init__(
        self,
        *,
        response_text: str = "deterministic-completion",
        model: str = "claude-sonnet-4-6",
        input_tokens: int = 12,
        output_tokens: int = 4,
        error_mode: str | None = None,
    ) -> None:
        """Initialise the deterministic adapter with canned response parameters.

        Args:
            response_text: Prefix prepended to the prompt to form the response text.
            model: Reported model identifier echoed in completions.
            input_tokens: Synthetic prompt token count reported in completions.
            output_tokens: Synthetic output token count reported in completions.
            error_mode: When ``"provider"`` or ``"rate-limit"``, the next call raises
                the corresponding error; ``None`` returns a normal completion.
        """
        self.response_text = response_text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error_mode = error_mode
        self.calls = 0

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Return a deterministic completion or raise the configured error.

        Args:
            request: Normalized provider request; the prompt is echoed back
                in the response text.

        Returns:
            A :class:`ProviderCompletion` whose text is
            ``"{response_text}:{request.prompt}"``.

        Raises:
            LLMProviderError: When :attr:`error_mode` is ``"provider"``.
            LLMRateLimitError: When :attr:`error_mode` is ``"rate-limit"``.
        """
        self.calls += 1
        if self.error_mode == "provider":
            raise LLMProviderError("synthetic provider failure")
        if self.error_mode == "rate-limit":
            raise LLMRateLimitError("synthetic rate limit", retry_after_seconds=0.01)
        return ProviderCompletion(
            text=f"{self.response_text}:{request.prompt}",
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            provider_request_id="deterministic-request-id",
        )
