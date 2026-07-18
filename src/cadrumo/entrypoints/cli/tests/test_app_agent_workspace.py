"""Behaviour gate for ``aeat app agent --output DIR`` (workspace materialiser).

Asserts the group-callback command materialises the shipped operator harness into
the chosen directory and emits a typed ``agent`` envelope, without requiring an
active profile or secret store (it is profile-independent).
"""

from __future__ import annotations

import json
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


def test_materialise_emits_agent_envelope_and_writes_files(tmp_path: Path) -> None:
    out = tmp_path / "workspace"
    result = invoke_cached_cli(["--format", "json", "app", "agent", "--output", str(out)])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "agent"
    assert envelope["status"] == "success"
    payload = envelope["result"]
    assert payload["layout"] == "workspace"
    assert payload["rules_written"] >= 7
    assert payload["personas_written"] >= 3
    assert payload["skills_written"] >= 1
    assert (out / ".claude" / "rules" / "cadrumo-operator-operating-rules.md").is_file()
    assert (out / ".claude" / "skills" / "preparar-modelo-130" / "SKILL.md").is_file()


def test_materialise_requires_output_option() -> None:
    result = invoke_cached_cli(["--format", "json", "app", "agent"])
    # The required --output option is missing: the CLI refuses with usage guidance.
    assert result.exit_code != 0
