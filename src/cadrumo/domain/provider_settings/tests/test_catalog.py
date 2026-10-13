"""The bundled provider catalog and its strict loader."""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import CoreValidationError
from ..catalog import ProviderAuthKind, ProviderConsumer, load_provider_catalog, parse_provider_catalog

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXPECTED_PROVIDERS = {
    "anthropic": (ProviderAuthKind.API_KEY, {"extraction", "assistant"}, None),
    "openai": (ProviderAuthKind.API_KEY, {"extraction", "assistant"}, None),
    "gemini": (ProviderAuthKind.API_KEY, {"extraction"}, None),
    "kimi": (ProviderAuthKind.API_KEY, {"assistant"}, None),
    "zai": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, "https://api.z.ai/api/anthropic"),
    "zhipu": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, "https://open.bigmodel.cn/api/anthropic"),
    "deepseek": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, "https://api.deepseek.com/anthropic"),
    "moonshot": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, "https://api.moonshot.ai/anthropic"),
    "minimax": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, "https://api.minimax.io/anthropic"),
    "qwen": (ProviderAuthKind.API_KEY_WITH_BASE_URL, {"assistant"}, None),
    "claude": (ProviderAuthKind.OAUTH_OR_PROVIDER_SIGN_IN, {"assistant"}, None),
    "codex": (ProviderAuthKind.PROVIDER_SIGN_IN_ONLY, {"assistant"}, None),
    "antigravity": (ProviderAuthKind.PROVIDER_SIGN_IN_ONLY, {"assistant"}, None),
}

_VALID_ENTRY = """
[[providers]]
id = "anthropic"
display_name = "Anthropic"
auth_kind = "api_key"
consumers = ["extraction"]
"""


def test_bundled_catalog_declares_every_supported_provider() -> None:
    catalog = load_provider_catalog()

    declared = {
        entry.id: (entry.auth_kind, {consumer.value for consumer in entry.consumers}, entry.default_base_url)
        for entry in catalog.providers
    }
    assert declared == _EXPECTED_PROVIDERS
    assert all(entry.display_name for entry in catalog.providers)
    development = {
        entry.id: entry.development_setting
        for entry in catalog.providers
        if entry.development_setting is not None and entry.development_setting
    }
    key_providers = {"anthropic", "openai", "gemini", "kimi", "zai", "zhipu", "deepseek", "moonshot", "minimax", "qwen"}
    assert development == {provider: f"cadrumo_llm_{provider}_api_key" for provider in key_providers}
    agent_ids = {entry.id: entry.agent_credential_id for entry in catalog.providers if entry.agent_credential_id}
    assert agent_ids == {
        "anthropic": "claude",
        "openai": "codex",
        **{provider: provider for provider in ("kimi", "zai", "zhipu", "deepseek", "moonshot", "minimax", "qwen")},
    }


def test_catalog_lookup_refuses_unknown_and_malformed_ids() -> None:
    catalog = load_provider_catalog()

    assert catalog.entry("anthropic") is not None
    assert catalog.entry("not-a-provider") is None
    assert catalog.entry("../anthropic") is None
    gemini = catalog.entry("gemini")
    assert gemini is not None
    assert gemini.serves(ProviderConsumer.EXTRACTION)
    assert not gemini.serves(ProviderConsumer.ASSISTANT)


def test_valid_minimal_catalog_parses() -> None:
    catalog = parse_provider_catalog("schema_version = 1\n" + _VALID_ENTRY)

    assert catalog.provider_ids == ("anthropic",)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param("schema_version = 2\n" + _VALID_ENTRY, id="unknown-schema-version"),
        pytest.param("schema_version = 1\n" + _VALID_ENTRY + _VALID_ENTRY, id="duplicate-id"),
        pytest.param(
            "schema_version = 1\n"
            + _VALID_ENTRY.replace(
                'consumers = ["extraction"]',
                'consumers = ["extraction"]\ndefault_base_url = "https://example.invalid/anthropic"',
            ),
            id="default-url-on-plain-key",
        ),
        pytest.param(
            "schema_version = 1\n"
            + _VALID_ENTRY.replace('"api_key"', '"api_key_with_base_url"').replace(
                'consumers = ["extraction"]', 'consumers = ["assistant"]\ndefault_base_url = "http://example.invalid"'
            ),
            id="plain-http-default",
        ),
        pytest.param(
            "schema_version = 1\n" + _VALID_ENTRY.replace('"api_key"', '"provider_sign_in_only"'),
            id="extraction-without-direct-key",
        ),
        pytest.param(
            "schema_version = 1\n" + _VALID_ENTRY + 'development_setting = "cadrumo_llm_model"\n',
            id="development-setting-not-secret",
        ),
        pytest.param("schema_version = 1\n" + _VALID_ENTRY + 'unexpected = "x"\n', id="unknown-field"),
        pytest.param(
            "schema_version = 1
" + _VALID_ENTRY + 'agent_credential_id = "claude"
', id="agent-id-without-assistant"
        ),
        pytest.param("schema_version = [", id="not-toml"),
    ],
)
def test_malformed_catalog_is_refused(document: str) -> None:
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(document)
