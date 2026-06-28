"""CLI surface tests for ``aeat app ledger ratios``.

Pins the 5-verb ratios subgroup (list / set / unset / eligible /
validate) against the real ratios backend, plus exercises the help-text
surface so each verb's documentation reaches the operator. Companion
to the destructive-action safeguard tests; the ratios `unset` verb is
non-destructive of accounting state (clears one per-category override
that the operator can recompute) so it has no `--yes` requirement.

The bucket-maintenance verbs are not yet mounted, so
this file covers only the ratios half of contract; the bucket-maintenance
half lands when contract is closed.
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


@pytest.mark.parametrize("verb", ["list", "set", "unset", "eligible", "validate"])
def test_ledger_ratios_verb_help_renders(cli_runner: CliRunner, verb: str) -> None:
    """Every `aeat app ledger ratios <verb> --help` renders cleanly,
    confirming each verb is mounted and its help-text translation key
    resolves to a non-empty default."""

    result = cli_runner.invoke(app, ["app", "ledger", "ratios", verb, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output or "Uso:" in result.output, result.output


def test_ledger_ratios_list_returns_envelope_on_empty_bucket(cli_runner: CliRunner) -> None:
    """`aeat app ledger ratios list` on an empty bucket emits a typed
    envelope (no exception, no missing-override error). The verb is
    read-only and informative — operators must always be able to query
    the override surface even when no overrides are persisted."""

    result = cli_runner.invoke(app, ["app", "ledger", "ratios", "list"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_eligible_returns_envelope_on_empty_bucket(cli_runner: CliRunner) -> None:
    """`aeat app ledger ratios eligible` lists the categories whose
    overrides the engine accepts; this surface is purely registry-driven
    and works against an empty bucket."""

    result = cli_runner.invoke(app, ["app", "ledger", "ratios", "eligible"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_validate_on_empty_bucket_succeeds(cli_runner: CliRunner) -> None:
    """`aeat app ledger ratios validate` runs the engine validation on
    the persisted override set (empty here). No errors surface when no
    overrides exist; the verb proves the validation path is reachable."""

    result = cli_runner.invoke(app, ["app", "ledger", "ratios", "validate"])
    assert result.exit_code == 0, result.output


def test_ledger_ratios_unset_refuses_when_no_override_exists(cli_runner: CliRunner) -> None:
    """`aeat app ledger ratios unset <category>` against a bucket with
    no persisted override for that category surfaces the
    ``no_override_error`` translation rather than silently succeeding,
    so the operator notices the override was never persisted."""

    result = cli_runner.invoke(app, ["app", "ledger", "ratios", "unset", "material_oficina"])
    assert result.exit_code != 0, result.output
