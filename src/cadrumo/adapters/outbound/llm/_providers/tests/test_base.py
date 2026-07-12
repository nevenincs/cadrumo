"""Behaviour tests for the shared LLM provider HTTP-status dispatch."""

from __future__ import annotations

import logging

import httpx
import pytest

from ..._errors import LLMProviderError, LLMRateLimitError
from ..base import check_http_error

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LOGGER = logging.getLogger(__name__)


def _response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code=status, headers=headers or {})


def test_check_http_error_passes_through_success() -> None:
    """A 2xx response raises nothing."""
    check_http_error(_response(200), provider_name="OpenAI", model="m", logger=_LOGGER)


def test_check_http_error_429_raises_rate_limit_with_retry_hint() -> None:
    """HTTP 429 raises a rate-limit error carrying the parsed Retry-After hint."""
    with pytest.raises(LLMRateLimitError) as exc:
        check_http_error(_response(429, {"retry-after": "5"}), provider_name="OpenAI", model="m", logger=_LOGGER)
    assert exc.value.retry_after_seconds == 5.0


def test_check_http_error_5xx_raises_provider_error() -> None:
    """A 5xx status raises a provider error naming the provider and status."""
    with pytest.raises(LLMProviderError, match=r"Gemini API failure \(503\)"):
        check_http_error(_response(503), provider_name="Gemini", model="m", logger=_LOGGER)


def test_check_http_error_4xx_raises_provider_error() -> None:
    """A non-429 4xx status raises a provider error."""
    with pytest.raises(LLMProviderError, match=r"OpenAI API failure \(404\)"):
        check_http_error(_response(404), provider_name="OpenAI", model="m", logger=_LOGGER)
