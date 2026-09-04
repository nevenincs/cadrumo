"""Tests for the registry maintenance CLI's exit-code contract.

`dev.quality.module_test_reach` listed `dev/registry/parity/maintenance_cli.py`
as unreached. Three of its four verbs are gates by intent, and only one of them
could fail.

``audit-oracles`` raises ``typer.Exit(1)`` on failures and is the verb CI runs.
Its two siblings in the same file printed their failure signal as JSON and
returned 0: ``workbooks-verify`` ignored ``failed_count``, and ``parity-replay``
ignored a ``status`` of ``mismatch`` - so a replay whose entire purpose is to
detect that the product diverged from an archived tape reported that divergence
and exited successfully. Anything reading the status code could not tell a
divergence from an agreement.

What is NOT covered here, stated rather than implied: a genuine mismatching
replay. Building one needs a valid archived tape, which needs a parity scenario
and an official workbook, and replaying it runs the scenario against the live
registry. That corpus is the subject of the parity suite next door, not of the
CLI's exit-code wiring. These cases pin the wiring - that the failure branch
exists, that the success branch stays 0, and that a missing input refuses
rather than passing.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from typer.testing import CliRunner

from ..maintenance_cli import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _invoke(*arguments: str) -> object:
    return CliRunner().invoke(app, list(arguments))


def test_every_maintenance_verb_is_registered() -> None:
    """The commands are reached by name from a workflow file, so the names are contract."""
    result = _invoke("--help")

    assert result.exit_code == 0, result.output
    for verb in ("audit-oracles", "workbooks-verify", "parity-run", "parity-replay"):
        assert verb in result.output


def test_a_verified_empty_workbook_root_still_exits_zero(tmp_path: pathlib.Path) -> None:
    """The success branch must survive the new refusal.

    A gate that refused unconditionally would be no better than one that never
    refused; this is the half that says the exit code tracks the report.
    """
    result = _invoke("workbooks-verify", "--root", str(tmp_path))

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["failed_count"] == 0


def test_the_workbook_verdict_and_the_exit_code_agree(tmp_path: pathlib.Path) -> None:
    """The property, stated over whatever the run actually found.

    Written against the report rather than a fixed expectation so it holds for
    any root: a run reporting failures must not exit 0, and a clean run must
    not exit non-zero.
    """
    result = _invoke("workbooks-verify", "--root", str(tmp_path))
    failed = json.loads(result.output)["failed_count"]

    assert (result.exit_code != 0) == bool(failed)


def test_replaying_a_missing_tape_refuses(tmp_path: pathlib.Path) -> None:
    """An absent tape proves nothing about parity, so it cannot exit 0."""
    result = _invoke("parity-replay", "--tape", str(tmp_path / "absent.json"))

    assert result.exit_code != 0


def test_replaying_an_unparsable_tape_refuses(tmp_path: pathlib.Path) -> None:
    """A tape that is not a tape is not a match either."""
    tape = tmp_path / "broken.json"
    tape.write_text("{not json", encoding="utf-8")

    result = _invoke("parity-replay", "--tape", str(tape))

    assert result.exit_code != 0


def test_auditing_an_empty_registry_root_does_not_report_success(
    tmp_path: pathlib.Path,
) -> None:
    """The verb CI runs, over a root containing no registry at all.

    This is the pattern the two siblings now follow, so it is pinned here as
    the reference: a gate handed nothing must not answer the way a clean audit
    does.
    """
    result = _invoke("audit-oracles", "--registry-root", str(tmp_path))

    assert result.exit_code != 0


def test_a_parity_run_without_its_required_options_refuses() -> None:
    """The scenario and store root have no defensible default."""
    result = _invoke("parity-run")

    assert result.exit_code != 0
