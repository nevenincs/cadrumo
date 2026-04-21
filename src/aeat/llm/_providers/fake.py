"""Deterministic real fake adapter for unit tests."""

from __future__ import annotations

from .._errors import LLMProviderError, LLMRateLimitError
from .._models import LLMProvider
from .base import ProviderCompletion, ProviderRequest, _ProviderAdapter


class _FakeAdapter(_ProviderAdapter):
    """Deterministic adapter used by unit tests without mocks or patches."""

    provider = LLMProvider.ANTHROPIC

    def __init__(
        self,
        *,
        response_text: str = "fake-completion",
        model: str = "claude-sonnet-4-6",
        input_tokens: int = 12,
        output_tokens: int = 4,
        error_mode: str | None = None,
    ) -> None:
        self.response_text = response_text
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.error_mode = error_mode
        self.calls = 0

    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Return a deterministic completion or raise a configured error."""

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
            provider_request_id="fake-request-id",
        )
