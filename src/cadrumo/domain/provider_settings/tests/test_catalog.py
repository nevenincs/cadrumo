"""The bundled lane catalog and its strict loader."""

from __future__ import annotations

import re

import pytest

from ....core.errors.hierarchy import CoreValidationError
from ..catalog import (
    ProviderAuthKind,
    ProviderTransport,
    load_provider_catalog,
    parse_provider_catalog,
    validate_https_base_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_GATEWAYS = ("zai", "zhipu", "deepseek", "moonshot", "minimax", "qwen")

_HEADER = """schema_version = 1

[source]
agent_version = "0.1.0"
agent_source_digest = "0000000000000000000000000000000000000000000000000000000000000000"
"""

_API_LANE = """
[[providers]]
id = "claude_api"
provider = "claude"
transport = "api"
display_name = "Claude"
auth_kind = "api_key"
consumers = ["assistant"]
credential_field = "claude_api_key"
"""


def test_bundled_catalog_has_one_entry_per_agent_lane() -> None:
    catalog = load_provider_catalog()

    lanes = {entry.id: (entry.provider, entry.transport, entry.auth_kind) for entry in catalog.providers}
    assert lanes["claude_api"] == ("claude", ProviderTransport.API, ProviderAuthKind.API_KEY)
    assert lanes["claude_cli"] == ("claude", ProviderTransport.CLI, ProviderAuthKind.OAUTH_OR_PROVIDER_SIGN_IN)
    assert lanes["codex_api"] == ("codex", ProviderTransport.API, ProviderAuthKind.API_KEY)
    assert lanes["codex_cli"] == ("codex", ProviderTransport.CLI, ProviderAuthKind.PROVIDER_SIGN_IN_ONLY)
    assert lanes["antigravity_cli"] == ("antigravity", ProviderTransport.CLI, ProviderAuthKind.PROVIDER_SIGN_IN_ONLY)
    assert lanes["kimi_cli"] == ("kimi", ProviderTransport.CLI, ProviderAuthKind.API_KEY)
    for gateway in _GATEWAYS:
        assert lanes[f"{gateway}_cli"] == (gateway, ProviderTransport.CLI, ProviderAuthKind.API_KEY_WITH_BASE_URL)
    assert set(lanes) == {
        "claude_api",
        "claude_cli",
        "codex_api",
        "codex_cli",
        "antigravity_cli",
        "kimi_cli",
        *(f"{gateway}_cli" for gateway in _GATEWAYS),
    }


def test_lanes_of_one_identity_share_its_name_and_never_a_credential_field() -> None:
    catalog = load_provider_catalog()
    by_id = {entry.id: entry for entry in catalog.providers}

    assert by_id["claude_api"].display_name == by_id["claude_cli"].display_name == "Claude"
    assert by_id["codex_api"].display_name == by_id["codex_cli"].display_name == "Codex"
    assert by_id["claude_api"].credential_field == "claude_api_key"
    assert by_id["claude_cli"].credential_field == "claude_code_oauth_token"
    assert by_id["codex_api"].credential_field == "codex_api_key"
    assert by_id["codex_cli"].credential_field is None
    assert by_id["qwen_cli"].default_base_url is None
    assert by_id["zai_cli"].default_base_url == "https://api.z.ai/api/anthropic"
    assert all(by_id[f"{gateway}_cli"].cli_program == "claude" for gateway in _GATEWAYS)
    assert by_id["claude_api"].cli_program is None


def test_only_api_key_lanes_have_an_agent_credential_id_and_it_is_the_agents_provider_name() -> None:
    catalog = load_provider_catalog()
    by_id = {entry.id: entry for entry in catalog.providers}

    assert by_id["claude_api"].agent_credential_id == "claude"
    assert by_id["codex_api"].agent_credential_id == "codex"
    assert by_id["kimi_cli"].agent_credential_id == "kimi"
    assert all(by_id[f"{gateway}_cli"].agent_credential_id == gateway for gateway in _GATEWAYS)
    # An OAuth token or the provider's own sign-in never travels in the hosting frame.
    assert by_id["claude_cli"].agent_credential_id is None
    assert by_id["codex_cli"].agent_credential_id is None
    assert by_id["antigravity_cli"].agent_credential_id is None
    ids = [entry.agent_credential_id for entry in catalog.providers if entry.agent_credential_id is not None]
    assert len(ids) == len(set(ids))


def test_catalog_lookup_refuses_unknown_and_malformed_ids() -> None:
    catalog = load_provider_catalog()

    assert catalog.entry("claude_api") is not None
    assert catalog.entry("anthropic") is None
    assert catalog.entry("not-a-lane") is None
    assert catalog.entry("../claude_api") is None


def test_lane_ids_fit_the_desktop_host_grammar() -> None:
    grammar = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

    for entry in load_provider_catalog().providers:
        assert grammar.fullmatch(entry.id), entry.id
        assert entry.id == f"{entry.provider}_{entry.transport.value}"


@pytest.mark.parametrize(
    "url",
    [
        "http://gateway.example.invalid",
        "https://",
        "https://user:pw@gateway.example.invalid",
        "https://gateway.example.invalid/?q=1",
        "https://gateway.example.invalid/a*b",
        "https://gateway.example.invalid/a[b",
        "https://gateway.example.invalid/%41",
        "https://gateway.example.invalid/$HOME",
        "https://gatewäy.example.invalid",
        "https://gateway.example.invalid/" + chr(7),
        "-https://gateway.example.invalid",
        "https://gateway.example.invalid/" + "a" * 2048,
    ],
)
def test_base_url_rejections_match_the_desktop_host(url: str) -> None:
    with pytest.raises(ValueError):
        validate_https_base_url(url)


def test_acceptable_base_url_passes() -> None:
    assert validate_https_base_url("https://api.z.ai/api/anthropic") == "https://api.z.ai/api/anthropic"


def test_valid_minimal_catalog_parses() -> None:
    catalog = parse_provider_catalog(_HEADER + _API_LANE)

    assert catalog.provider_ids == ("claude_api",)


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_HEADER.replace("schema_version = 1", "schema_version = 2") + _API_LANE, id="schema-version"),
        pytest.param(_HEADER + _API_LANE + _API_LANE, id="duplicate-lane"),
        pytest.param(_API_LANE.join(("schema_version = 1\n", "")), id="missing-source"),
        pytest.param(
            _HEADER + _API_LANE.replace('consumers = ["assistant"]', 'consumers = ["extraction"]'),
            id="extraction-consumer",
        ),
        pytest.param(_HEADER + _API_LANE + 'cli_program = "claude"\n', id="api-lane-with-program"),
        pytest.param(
            _HEADER + _API_LANE.replace('transport = "api"', 'transport = "cli"'),
            id="cli-lane-without-program",
        ),
        pytest.param(
            _HEADER + _API_LANE + 'default_base_url = "https://gateway.example.invalid"\n',
            id="default-url-on-plain-key",
        ),
        pytest.param(
            _HEADER + _API_LANE.replace('credential_field = "claude_api_key"\n', ""),
            id="key-lane-without-field",
        ),
        pytest.param(_HEADER + _API_LANE + 'development_setting = "cadrumo_llm_model"\n', id="setting-not-secret"),
        pytest.param(
            _HEADER
            + _API_LANE
            + _API_LANE.replace('id = "claude_api"', 'id = "claude_cli"')
            .replace('transport = "api"', 'transport = "cli"')
            .replace('"Claude"', '"Other"')
            .replace("claude_api_key", "claude_code_oauth_token")
            + 'cli_program = "claude"\n',
            id="identity-names-disagree",
        ),
        pytest.param(_HEADER + _API_LANE + 'unexpected = "x"\n', id="unknown-field"),
        pytest.param("schema_version = [", id="not-toml"),
    ],
)
def test_malformed_catalog_is_refused(document: str) -> None:
    with pytest.raises(CoreValidationError):
        parse_provider_catalog(document)
