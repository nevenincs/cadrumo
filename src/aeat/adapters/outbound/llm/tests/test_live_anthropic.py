"""Opt-in live integration test for the Anthropic provider adapter.

Performs a tiny real round trip against the Anthropic API when
``AEAT_LLM_ANTHROPIC_API_KEY`` is configured; the test self-skips
otherwise. Tagged ``aeat_live`` so it is excluded from the default unit
test selection.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from .....core.config import Settings
from .. import LLMClient, LLMRequest

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


class _LiveSettings(Settings):
    model_config = SettingsConfigDict(env_file=Settings.model_config.get("env_file"), env_file_encoding="utf-8")


def test_live_anthropic_round_trip(tmp_path: Path) -> None:
    """Run a tiny Anthropic round trip when live testing is explicitly enabled."""

    settings = _LiveSettings(
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
    )
    if settings.aeat_llm_anthropic_api_key is None:
        pytest.skip("AEAT_LLM_ANTHROPIC_API_KEY is not configured.")
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
