"""The live-agent proof names the agent's own provider and lane, not Cadrumo's former provider name."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..agent_live import _claude_api_lane, _run_selection

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _lane(provider_id: str, transport: str, model: str) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "transport": transport,
        "health": {"selectable": True, "reasons": []},
        "catalog": {"models": [{"entry_id": f"{transport}-1", "model": model}]},
    }


def test_the_claude_api_lane_is_chosen_although_its_command_line_lane_shares_the_provider_name() -> None:
    catalog = {"providers": [_lane("claude", "cli", "cli-model"), _lane("claude", "api", "api-model")]}

    lane = _claude_api_lane(catalog)

    assert lane is not None
    assert lane["transport"] == "api"
    assert lane["catalog"]["models"][0]["model"] == "api-model"


@pytest.mark.parametrize(
    "providers",
    [
        pytest.param([_lane("claude", "cli", "cli-model")], id="only-the-command-line-lane"),
        pytest.param([_lane("anthropic", "api", "api-model")], id="the-former-cadrumo-name"),
        pytest.param([_lane("codex", "api", "api-model")], id="another-provider"),
        pytest.param([], id="empty"),
    ],
)
def test_no_claude_api_lane_is_found_when_the_agent_does_not_offer_it(providers: list[dict[str, object]]) -> None:
    assert _claude_api_lane({"providers": providers}) is None


def test_a_run_names_the_agents_canonical_provider_and_its_transport(tmp_path: Path) -> None:
    selection = _run_selection(tmp_path, "model-x")

    assert selection == {
        "provider": "claude",
        "transport": "api",
        "model": "model-x",
        "workspace_root": str(tmp_path),
    }
