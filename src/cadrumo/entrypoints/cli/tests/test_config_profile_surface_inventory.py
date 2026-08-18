"""Inventory tests for the `aeat config profile` operator surface.

Pins the plain-English operator-target verbs the profile surface
contract mandates as reachable on the `aeat config profile` subgroup.
Future regressions that accidentally rename or unmount a verb surface
here, not in a shipped operator session.
"""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


_OPERATOR_VERBS = (
    "show",
    "edit",
    "delete",
    "list",
)


@pytest.mark.parametrize("verb", _OPERATOR_VERBS)
def test_operator_verb_is_mounted(verb: str) -> None:
    """Each operator-target verb resolves under `aeat config profile`."""

    result = invoke_cached_cli(["config", "profile", verb, "--help"])

    assert result.exit_code == 0, result.output
