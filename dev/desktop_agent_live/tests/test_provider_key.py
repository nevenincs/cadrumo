"""The lane reads a provider's key under the vendor name the repository's environment template declares."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..provider_key import candidate_key_variables, declared_key_variables, provider_key_variable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPOSITORY = Path(__file__).resolve().parents[3]


def test_the_template_declares_the_vendor_names_and_not_the_product_names() -> None:
    declared = declared_key_variables(_REPOSITORY / "env" / ".env.example")
    assert "CADRUMO_LLM_ANTHROPIC_API_KEY" in declared
    assert "CADRUMO_LLM_CLAUDE_API_KEY" not in declared


def test_the_claude_api_lane_reads_the_anthropic_key_the_template_declares() -> None:
    declared = declared_key_variables(_REPOSITORY / "env" / ".env.example")
    assert provider_key_variable("claude", "https://api.anthropic.com", declared) == "CADRUMO_LLM_ANTHROPIC_API_KEY"


@pytest.mark.parametrize(
    ("provider", "base_url", "expected"),
    [
        ("claude", "https://api.anthropic.com", ["CADRUMO_LLM_ANTHROPIC_API_KEY", "CADRUMO_LLM_CLAUDE_API_KEY"]),
        ("codex", "https://api.openai.com/v1", ["CADRUMO_LLM_OPENAI_API_KEY", "CADRUMO_LLM_CODEX_API_KEY"]),
        ("gemini", None, ["CADRUMO_LLM_GEMINI_API_KEY"]),
        ("zai", "https://localhost", ["CADRUMO_LLM_ZAI_API_KEY"]),
        ("moon-shot", "https://api.moonshot.ai", ["CADRUMO_LLM_MOONSHOT_API_KEY", "CADRUMO_LLM_MOON_SHOT_API_KEY"]),
    ],
)
def test_the_endpoint_vendor_is_tried_before_the_provider_name(
    provider: str, base_url: str | None, expected: list[str]
) -> None:
    assert candidate_key_variables(provider, base_url) == expected


def test_a_name_the_template_does_not_declare_is_never_used(tmp_path: Path) -> None:
    template = tmp_path / ".env.example"
    template.write_text("# CADRUMO_LLM_ANTHROPIC_API_KEY= commented\nCADRUMO_LLM_OPENAI_API_KEY=\n", encoding="utf-8")
    declared = declared_key_variables(template)
    assert declared == {"CADRUMO_LLM_OPENAI_API_KEY"}
    assert provider_key_variable("claude", "https://api.anthropic.com", declared) is None
