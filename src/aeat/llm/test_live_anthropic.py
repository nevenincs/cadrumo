"""Opt-in live test for the Anthropic adapter."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from aeat.config import Settings
from aeat.llm import LLMClient, LLMRequest


class _LiveSettings(Settings):
    model_config = SettingsConfigDict(env_file=Settings.model_config.get("env_file"), env_file_encoding="utf-8")


@pytest.mark.live
def test_live_anthropic_round_trip(tmp_path: Path) -> None:
    """Run a tiny Anthropic round trip when live testing is explicitly enabled."""

    if os.getenv("AEAT_LIVE_TESTS") != "1":
        pytest.skip("Set AEAT_LIVE_TESTS=1 to enable live LLM tests.")
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
            )
        )
    )
    assert response.provider.value == "ANTHROPIC"
    assert "AEAT" in response.text
