"""CLI surface tests for ``aeat app overview`` + retired-noun negatives.

Closes two W81 Steps in one file:

- W81.P393.S2247: Add CLI surface tests for every overview verb per
  the adjudicated grammar (status / calendar / agenda / backlog /
  explain). Each verb is exercised against an isolated profile so the
  mount + help path + empty-bucket envelope all reach the operator.

- W81.P393.S2248: Add negative tests asserting `aeat deadlines` and
  related retired noun-groups are unknown commands. The W71 verb tree
  retired the standalone `deadlines` noun-group in favour of mounting
  deadline-shaped surfaces under `aeat app overview`. Operators
  reaching for `aeat deadlines ...` must see Click's "No such command"
  refusal, not a silent fallthrough.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
        yield


# ---------------------------------------------------------------------------
# S2247 — overview verb surface tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", ["status", "calendar", "agenda", "backlog", "explain"])
def test_overview_verb_help_renders(cli_runner: CliRunner, verb: str) -> None:
    """Every `aeat app overview <verb> --help` renders cleanly; each
    verb is mounted and its help-text translation key resolves to a
    non-empty default."""

    result = cli_runner.invoke(app, ["app", "overview", verb, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output or "Uso:" in result.output, result.output


def test_overview_status_returns_envelope_on_empty_bucket(cli_runner: CliRunner) -> None:
    """`aeat app overview status` against an isolated profile with no
    work units emits a typed envelope (no exception, no missing-data
    error). The verb is read-only and works without a populated bucket."""

    result = cli_runner.invoke(app, ["app", "overview", "status"])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# S2248 — retired-noun-group negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "retired_verb",
    [
        ["deadlines"],
        ["deadlines", "list"],
        ["deadlines", "status"],
        ["deadlines", "show"],
        ["app", "deadlines"],
        ["app", "deadlines", "list"],
    ],
)
def test_retired_deadlines_noun_group_is_unknown(
    cli_runner: CliRunner,
    retired_verb: list[str],
) -> None:
    """Reaching for `aeat deadlines ...` (or `aeat app deadlines ...`)
    must surface Click's "No such command" refusal. The W71 verb tree
    retired the standalone deadlines noun-group; its surfaces live
    under `aeat app overview` (calendar, agenda, backlog)."""

    result = cli_runner.invoke(app, retired_verb)
    assert result.exit_code != 0, (
        f"retired verb path {retired_verb!r} should be unknown but exited 0: {result.output!r}"
    )
    haystack = result.output.lower()
    assert "no such command" in haystack or "no such" in haystack, (
        f"retired verb path {retired_verb!r} did not surface unknown-command refusal: {result.output!r}"
    )
