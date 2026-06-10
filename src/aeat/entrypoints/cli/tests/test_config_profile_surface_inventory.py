"""Inventory tests for the `aeat config profile` operator surface.

Pins the plain-English operator-target verbs the profile surface
contract mandates as reachable on the `aeat config profile` subgroup.
Future regressions that accidentally rename or unmount a verb surface
here, not in a shipped operator session.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._config import profile_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


_OPERATOR_VERBS = (
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


@pytest.mark.parametrize("verb", _OPERATOR_VERBS)
def test_operator_verb_is_mounted(verb: str, runner: CliRunner) -> None:
    """Each operator-target verb resolves under `aeat config profile`."""

    result = runner.invoke(profile_app, [verb, "--help"])

    assert result.exit_code == 0, result.output
