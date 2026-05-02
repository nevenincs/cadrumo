"""Unit tests for translation helpers built atop the LLM client.

Exercises :class:`aeat.adapters.outbound.llm.Translator` against the
deterministic provider adapter to verify it builds a valid translation
request and returns a populated
:class:`aeat.adapters.outbound.llm.Translation` model.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from ....core.config import LLMProviderSetting, Settings
from . import LLMCache, LLMClient, Translator, UsageRecorder
from ._providers import _DeterministicAdapter

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


class _IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")


def test_translator_uses_seeded_prompt_and_returns_translation(tmp_path: Path) -> None:
    """Translator should build a translation request and return a Translation model."""

    settings = _IsolatedSettings(
        aeat_llm_provider=LLMProviderSetting.ANTHROPIC,
        aeat_llm_model="claude-sonnet-4-6",
        aeat_llm_cache_dir=tmp_path / "cache",
        aeat_llm_usage_dir=tmp_path / "usage",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=tmp_path / "cache"),
        usage_recorder=UsageRecorder(root_dir=tmp_path / "usage"),
        _adapter=_DeterministicAdapter(response_text="hola"),
    )
    translator = Translator(client=client)
    translation = asyncio.run(translator.translate("hello", "en", "es", context="AEAT form label"))
    assert translation.source_lang == "en"
    assert translation.target_lang == "es"
    assert translation.text.startswith("hola:")
