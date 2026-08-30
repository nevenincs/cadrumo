"""Opt-in live integration test for the Anthropic provider adapter.

Performs a tiny real round trip against the Anthropic API. Tagged
``aeat_live`` so it is excluded from the default unit test selection; after
live opt-in, missing provider credentials are a failing prerequisite.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ...core.config import Settings
from ...tests.live_gate import requires_live_enabled
from ..client import LLMClient
from ..models import LLMRequest

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def test_live_anthropic_round_trip(tmp_path: Path) -> None:
    """Run a tiny Anthropic round trip when live testing is explicitly enabled.

    There is no ``.env`` file support: ``CADRUMO_LLM_ANTHROPIC_API_KEY`` must be
    a real process environment variable (e.g. via ``uv run --env-file env/.env``)
    for this opt-in live test to find credentials.
    """

    requires_live_enabled()
    settings = Settings(
        cadrumo_llm_cache_dir=tmp_path / "probe-cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
    )
    if settings.cadrumo_llm_anthropic_api_key is None:
        pytest.fail("CADRUMO_LLM_ANTHROPIC_API_KEY is not configured after live opt-in.")
    client = LLMClient(settings=settings)
    response = asyncio.run(
        client.complete(
            LLMRequest(
                prompt="Reply with exactly the word AEAT.",
                max_tokens=16,
                temperature=0.0,
            ),
        ),
    )
    assert response.provider.value == "ANTHROPIC"
    assert "AEAT" in response.text
