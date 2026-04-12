"""Unit tests for the prompt registry."""

import pytest

from aeat.llm import PromptDefinition, PromptRegistry


@pytest.mark.unit
def test_prompt_registry_returns_latest_version_by_default() -> None:
    """Registry lookups should return the highest version when unspecified."""

    registry = PromptRegistry.seeded()
    registry.register(
        PromptDefinition(
            id="translation_v1",
            version=2,
            template="new template {text}",
            expected_output_schema=None,
            description="newer version",
        )
    )
    assert registry.get("translation_v1").version == 2
    assert registry.get("translation_v1", version=1).version == 1


@pytest.mark.unit
def test_prompt_registry_seed_contains_required_prompts() -> None:
    """Seeded registry should include the prompts expected by downstream work."""

    registry = PromptRegistry.seeded()
    assert set(registry.prompt_ids()) == {
        "translation_v1",
        "casilla_extract_v1",
        "manual_rule_extract_v1",
    }
