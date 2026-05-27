"""Inventory tests for the `aeat config profile` operator surface.

Pins the ten plain-English operator-target verbs the
2026-05-16 ADR mandates as reachable on the
`aeat config profile` subgroup. Future regressions that
accidentally rename or unmount a verb surface here, not in a
shipped operator session.

The legacy `view` / `use` / `remove` names and field-at-a-time
`get` / `set` / `unset` diagnostics verbs MUST NOT resolve on the
operator surface. Those diagnostics live under
`python -m aeat.diagnostics profile`.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli._config import profile_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


_OPERATOR_VERBS = (
    "switch",
    "logout",
    "show",
    "edit",
    "rename",
    "delete",
    "export",
    "import",
    "duplicate",
    "list",
)

_RETIRED_VERBS = (
    "view",
    "use",
    "remove",
    "get",
    "set",
    "unset",
)


@pytest.mark.parametrize("verb", _OPERATOR_VERBS)
def test_operator_verb_is_mounted(verb: str, runner: CliRunner) -> None:
    """Each operator-target verb resolves under `aeat config profile`."""

    result = runner.invoke(profile_app, [verb, "--help"])

    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("verb", _RETIRED_VERBS)
def test_retired_verb_is_not_mounted(verb: str, runner: CliRunner) -> None:
    """Renamed verbs must not be reachable under their previous names."""

    result = runner.invoke(profile_app, [verb, "--help"])

    assert result.exit_code != 0
    assert "No such command" in result.output or "Usage" in result.output
