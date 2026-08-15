"""Structural gate for the Claude acquisition workflow's lane contract.

Two doctrine-grounded invariants: the CI lane is DETERMINISTIC (the live-model
Claude session is an operator-local capture per the post-release-distribution
plan and standing operator ruling — never a CI leg, and there is no CI API key by
standing ruling), and the client pin is REAL (the npm-global shim is resolved
by absolute path with a hard version-drift refusal, because PATH resolution
picked the operator's auto-updating native client over the pin on the
self-hosted runner).
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "packaging-claude.yml"


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> list[dict[str, Any]]:
    return _workflow()["jobs"]["cadrumo-claude-acquisition"]["steps"]


def test_ci_lane_never_runs_a_live_model_session() -> None:
    """The live Claude session stays operator-local; CI runs the protocol oracle only."""
    steps = _steps()
    surface = "\n".join(str(step.get("run", "")) for step in steps)
    assert "--run-claude-session" not in surface
    assert "dev.packaging.smoke_plugin_install" in surface
    assert "dev.packaging.smoke_mcpb" in surface
    # No credential is provisioned to any step: nothing in this lane may talk
    # to the live model.
    for step in steps:
        env = step.get("env") or {}
        assert "ANTHROPIC_API_KEY" not in env, step.get("name")
        assert "ANTHROPIC_AUTH_TOKEN" not in env, step.get("name")


def test_client_pin_is_absolute_path_resolved_and_drift_refusing() -> None:
    """The pinned npm shim is invoked by absolute path and version-asserted."""
    install = next(step for step in _steps() if step.get("name") == "Install pinned Claude Code client")
    run = str(install["run"])
    # One declared pin, installed and asserted from the same variable.
    assert '$pin = "2.1.211"' in run
    assert '"@anthropic-ai/claude-code@$pin"' in run
    # Absolute-path resolution through the npm global prefix — never PATH
    # lookup, which resolved the operator's native auto-updating client.
    assert "npm prefix --global" in run
    assert 'Join-Path $npmPrefix "claude.cmd"' in run
    assert "Get-Command claude" not in run
    # Loud refusals: missing shim and version drift both throw.
    assert "pinned Claude Code shim not found" in run
    assert "version drift" in run
    assert "CADRUMO_CLAUDE_EXECUTABLE=$claude" in run
