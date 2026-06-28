"""Shape tests for the ``aeat app modelo m036`` declarative-recording verbs.

Drives the CLI surface introduced by M036 commit 3 of 3: the
``m036_app`` Typer subgroup with ``alta`` / ``modificacion`` / ``baja``
verbs. Asserts each verb advertises the three operator-supplied flags
(``--declared-on``, ``--sede-justificante``, ``--note``), refuses
invocation without an active profile (the existing ``_require_active_profile``
guard), and rejects invalid date input cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.mark.parametrize("verb", ["alta", "modificacion", "baja"])
def test_m036_verb_advertises_flag_set(verb: str) -> None:
    """Each verb's --help surfaces --declared-on / --sede-justificante / --note."""
    result = _invoke(["app", "modelo", "m036", verb, "--help"])
    assert result.exit_code == 0, result.output
    assert "--declared-on" in result.output
    assert "--sede-justificante" in result.output
    assert "--note" in result.output


def test_m036_group_lists_three_verbs() -> None:
    """``aeat app modelo m036 --help`` lists the three declarative verbs."""
    result = _invoke(["app", "modelo", "m036", "--help"])
    assert result.exit_code == 0, result.output
    assert "alta" in result.output
    assert "modificacion" in result.output
    assert "baja" in result.output


@pytest.mark.parametrize("verb", ["alta", "modificacion", "baja"])
def test_m036_rejects_invalid_declared_on(verb: str) -> None:
    """An unparseable --declared-on fails cleanly with a non-zero exit."""
    result = _invoke(
        ["app", "modelo", "m036", verb, "--declared-on", "not-a-date"],
    )
    assert result.exit_code != 0


@pytest.mark.parametrize("verb", ["alta", "modificacion", "baja"])
def test_m036_refuses_without_active_profile(verb: str) -> None:
    """No active profile -> the cold-start guard refuses with a translated message."""
    result = _invoke(
        ["app", "modelo", "m036", verb, "--declared-on", "2026-06-04"],
    )
    assert result.exit_code != 0
    # The translated guard message is locale-dependent; the assertion
    # checks the verb did not silently proceed (non-zero exit) and the
    # output reaches the operator surface. Active-profile presence is
    # required for any actual record write; tests of the service body
    # itself live in ``application/modelo/test_m036_lifecycle_service.py``.
    assert result.output != ""
