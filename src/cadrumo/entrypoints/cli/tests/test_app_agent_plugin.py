"""End-to-end gate for ``aeat app agent --output DIR --layout plugin``.

Asserts the CLI materialises the shipped operator harness as a schema-valid Claude
plugin tree and emits the layout-discriminated ``agent`` envelope, without
requiring an active profile or secret store (the command is profile-independent).
Where the ``claude`` CLI is on PATH, the emitted tree is additionally asserted to
pass ``claude plugin validate --strict``; the structural assertions always run so
the test never silently degrades to a validator-only skip.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_sessionless_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path) -> Iterator[None]:
    with isolated_sessionless_storage_root(tmp_path=tmp_path):
        yield


def test_plugin_layout_emits_envelope_and_schema_valid_tree(tmp_path: Path) -> None:
    out = tmp_path / "plugin"
    result = invoke_cached_cli(["--format", "json", "app", "agent", "--output", str(out), "--layout", "plugin"])
    assert result.exit_code == 0, result.output

    envelope = json.loads(result.output)
    assert envelope["command"] == "agent"
    assert envelope["status"] == "success"
    payload = envelope["result"]
    assert payload["layout"] == "plugin"
    assert payload["plugin_name"] == "cadrumo"
    assert payload["version"]
    assert payload["skills_written"] >= 1
    assert payload["agents_written"] >= 1
    assert payload["persona_default"] == ""

    assert (out / ".claude-plugin" / "plugin.json").is_file()
    assert (out / "skills" / "preparar-modelo-130" / "SKILL.md").is_file()
    assert (out / "agents" / "coordinator.md").is_file()
    assert (out / ".mcp.json").is_file()
    mcp = json.loads((out / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "uvx"
    assert server["args"] == ["--from", f"cadrumo[agent]=={payload['version']}", "cadrumo-mcp"]
    assert server["env"]["CADRUMO_MCP_REQUIRED_VERSION"] == payload["version"]
    assert not (out / "artifacts").exists()

    claude = shutil.which("claude")
    if claude is not None:
        completed = subprocess.run(  # noqa: S603 - claude resolved from PATH, fixed args
            [claude, "plugin", "validate", "--strict", str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )


def test_default_layout_is_the_workspace_mirror(tmp_path: Path) -> None:
    out = tmp_path / "default"
    result = invoke_cached_cli(["--format", "json", "app", "agent", "--output", str(out)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # No --layout means the Claude-native workspace mirror, not the plugin.
    assert payload["layout"] == "workspace"
    assert (out / ".claude" / "rules" / "cadrumo-operator-operating-rules.md").is_file()
    assert not (out / ".claude-plugin").exists()


def test_invalid_layout_is_refused_with_choices(tmp_path: Path) -> None:
    out = tmp_path / "bad"
    result = invoke_cached_cli(["app", "agent", "--output", str(out), "--layout", "mcpb"])
    # A closed enum option refuses an unknown value and names the accepted set.
    assert result.exit_code != 0
    assert "workspace" in result.output and "plugin" in result.output
