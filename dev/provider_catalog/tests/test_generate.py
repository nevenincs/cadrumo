"""The lane-catalog generator against a synthetic cadrumo-agent tree.

The fixture mirrors only the declarations the generator reads, so these tests
run where no agent checkout exists and prove the drift gate catches a change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.provider_settings.catalog import ProviderAuthKind, ProviderTransport, parse_provider_catalog

from ..generate import AgentDefinitionError, agent_lanes, main, render_catalog, target_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCES = {
    "pyproject.toml": '[project]\nname = "cadrumo-agent"\nversion = "9.9.9"\n',
    "src/cadrumo_agent/provider_definitions.py": """
class Provider(StrEnum):
    CLAUDE = "claude"
    ANTIGRAVITY = "antigravity"
    ZAI = "zai"

SUPPORTED_PROVIDERS: Final = (
    ProviderDefinition(Provider.CLAUDE.value, (ProviderTransport.API, ProviderTransport.CLI)),
    ProviderDefinition(Provider.ANTIGRAVITY.value, (ProviderTransport.CLI,), uses_api_key=False),
    ProviderDefinition(Provider.ZAI.value, (ProviderTransport.CLI,)),
)
""",
    "src/cadrumo_agent/graph/enums.py": """
class ExecutionLane(StrEnum):
    CLAUDE_API = "anthropic"
    CLAUDE_CLI = provider_definitions.Provider.CLAUDE.value
    ANTIGRAVITY = provider_definitions.Provider.ANTIGRAVITY.value
    ZAI = provider_definitions.Provider.ZAI.value

    @property
    def provider(self):
        if self is ExecutionLane.CLAUDE_API:
            return provider_definitions.Provider.CLAUDE
        return provider_definitions.Provider(self.value)

    @property
    def transport(self):
        if self in {ExecutionLane.CLAUDE_API}:
            return provider_definitions.ProviderTransport.API
        return provider_definitions.ProviderTransport.CLI
""",
    "src/cadrumo_agent/providers/registry.py": """
_CORE_PROVIDERS: Final[tuple[ProviderDescriptor, ...]] = (
    _core(ExecutionLane.CLAUDE_API, "Claude", Transport.ANTHROPIC_HTTP),
    _core(ExecutionLane.ANTIGRAVITY, "Antigravity", Transport.ANTIGRAVITY_PRINT, autonomous_only=True),
    _core(ExecutionLane.CLAUDE_CLI, "Claude", Transport.CLAUDE_ACP),
)
""",
    "src/cadrumo_agent/providers/gateways.py": """
ANTHROPIC_GATEWAYS: Final[tuple[AnthropicGateway, ...]] = _one_row_per_provider(
    (
        AnthropicGateway(
            provider=ExecutionLane.ZAI,
            display_name="Z.ai",
            base_url_default="https://api.z.ai/api/anthropic",
            base_url_setting="zai_base_url",
            token_setting="zai_api_key",
        ),
    )
)
""",
    "src/cadrumo_agent/providers/cli_resolution.py": """
SYSTEM_CLI_LANES: Mapping[ExecutionLane, str] = MappingProxyType(
    {
        ExecutionLane.CLAUDE_CLI: "claude",
        ExecutionLane.ANTIGRAVITY: "agy",
    }
)
""",
    "src/cadrumo_agent/control/env_registry.py": '_TABLE = {"claude_code_oauth_token": None}\n',
}


def _agent_tree(root: Path, overrides: dict[str, str] | None = None) -> Path:
    for relative, text in {**_SOURCES, **(overrides or {})}.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_generated_lanes_follow_the_agent_definitions(tmp_path: Path) -> None:
    lanes, version, digest = agent_lanes(_agent_tree(tmp_path))
    catalog = parse_provider_catalog(render_catalog(lanes, version, digest))
    by_id = {entry.id: entry for entry in catalog.providers}

    assert catalog.source.agent_version == "9.9.9"
    assert catalog.source.agent_source_digest == digest
    assert set(by_id) == {"claude_api", "claude_cli", "antigravity_cli", "zai_cli"}
    assert (by_id["claude_api"].provider, by_id["claude_api"].transport) == ("claude", ProviderTransport.API)
    assert by_id["claude_api"].credential_field == "claude_api_key"
    assert by_id["claude_api"].development_setting == "cadrumo_llm_claude_api_key"
    assert by_id["claude_cli"].auth_kind is ProviderAuthKind.OAUTH_OR_PROVIDER_SIGN_IN
    assert by_id["claude_cli"].credential_field == "claude_code_oauth_token"
    assert by_id["antigravity_cli"].auth_kind is ProviderAuthKind.PROVIDER_SIGN_IN_ONLY
    assert by_id["antigravity_cli"].cli_program == "agy"
    assert by_id["zai_cli"].auth_kind is ProviderAuthKind.API_KEY_WITH_BASE_URL
    assert by_id["zai_cli"].cli_program == "claude"
    assert by_id["zai_cli"].default_base_url == "https://api.z.ai/api/anthropic"


def test_source_digest_changes_with_any_read_definition(tmp_path: Path) -> None:
    _, _, before = agent_lanes(_agent_tree(tmp_path / "a"))
    registry = _SOURCES["src/cadrumo_agent/providers/registry.py"].replace('"Antigravity"', '"Antigravity CLI"')
    lanes, _, after = agent_lanes(_agent_tree(tmp_path / "b", {"src/cadrumo_agent/providers/registry.py": registry}))

    assert before != after
    assert {lane.id: lane.display_name for lane in lanes}["antigravity_cli"] == "Antigravity CLI"


def test_a_lane_without_a_declared_transport_refuses(tmp_path: Path) -> None:
    definitions = _SOURCES["src/cadrumo_agent/provider_definitions.py"].replace(
        "(ProviderTransport.API, ProviderTransport.CLI)", "(ProviderTransport.CLI,)"
    )

    with pytest.raises(AgentDefinitionError):
        agent_lanes(_agent_tree(tmp_path, {"src/cadrumo_agent/provider_definitions.py": definitions}))


def test_unrecognised_declarations_refuse(tmp_path: Path) -> None:
    broken = {"src/cadrumo_agent/providers/cli_resolution.py": "SYSTEM_CLI_LANES = {}\n"}

    with pytest.raises(AgentDefinitionError):
        agent_lanes(_agent_tree(tmp_path, broken))


def test_check_mode_reports_drift_and_refuses_without_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = _agent_tree(tmp_path / "agent")
    committed = target_path().read_bytes()
    monkeypatch.delenv("CADRUMO_AGENT_CHECKOUT", raising=False)

    refused = main(["--check"])
    drift = main(["--check", "--agent-root", str(agent)])

    assert refused == 2
    assert drift == 1
    assert "DRIFT" in capsys.readouterr().err
    assert target_path().read_bytes() == committed
