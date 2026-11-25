"""A provider adapter that answers each attempt from a script, for the client's retry and pacing logic.

The client's retry loop and its run-wide rate-limit window decide only from the
typed failure an adapter raises and the delay it carries. The agent adapter
raises no transient failure, so these cases isolate that scheduling logic: the
script plays the failures, and the attempts it records are what the loop sent.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import override

from .....core.config_support import LLMProvider
from ..providers.base import ProviderAdapter, ProviderCompletion, ProviderRequest

COMPLETION_TEXT = "scripted completion"


class ScriptedAdapter(ProviderAdapter):
    """Raise or answer per attempt; the last entry repeats once the script is exhausted.

    Attributes:
        attempts: Every request the adapter received, in arrival order.
        arrived_at: The monotonic instant of each attempt, in the same order.
    """

    provider = LLMProvider.AGENT

    def __init__(self, script: Sequence[Exception | None]) -> None:
        """Bind the script: an exception to raise, or ``None`` to complete."""
        self._script = tuple(script)
        self.attempts: list[ProviderRequest] = []
        self.arrived_at: list[float] = []

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Record the attempt and play the script's entry for it."""
        index = len(self.attempts)
        self.attempts.append(request)
        self.arrived_at.append(time.monotonic())
        outcome = self._script[min(index, len(self._script) - 1)]
        if outcome is not None:
            raise outcome
        return ProviderCompletion(text=COMPLETION_TEXT, model=request.model, input_tokens=1, output_tokens=1)


def provider_request(prompt: str = "hello") -> ProviderRequest:
    """Return one normalized request, sent unchanged on every attempt."""
    return ProviderRequest(
        request_id="r" * 64,
        model="example/api/example-model-1",
        prompt=prompt,
        max_tokens=64,
        timeout_s=30,
    )
