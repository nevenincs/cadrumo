"""Unit tests for the ``aeat workflow`` CLI sub-app.

The tests exercise the typer surface via :class:`typer.testing.CliRunner`.
Real :class:`aeat.application.workflow.WorkflowEngine` instances are wired through
the ``set_test_hooks`` module seam — no mocks, no patches. The shared
test stand-ins live in ``_test_doubles.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import app as root_app
from ._helpers import clear_test_hooks, set_test_hooks
from ._test_doubles import make_engine, make_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _unwrap_result(output: str):
    return json.loads(output)["result"]


@pytest.fixture(autouse=True)
def _isolated_runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect AEAT_WORKFLOW_RUNS_DIR to an isolated tmp dir per test."""
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("AEAT_WORKFLOW_RUNS_DIR", str(runs_dir))
    yield runs_dir


@pytest.fixture(autouse=True)
def _wire_hooks() -> Iterator[None]:
    """Wire real test doubles into the CLI helper seam."""
    set_test_hooks(engine_factory=make_engine, profile_factory=make_profile)
    yield None
    clear_test_hooks()


class TestWorkflowCli:
    def test_next_json_round_trips(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        assert result.exit_code == 0, result.output
        payload = _unwrap_result(result.output)
        assert payload["final_stage"] == "DONE"
        run_id = payload["run_id"]
        # workflow runs CipherEnvelope-on-disk; the
        # canonical filename is ``<run_id>.envelope.json`` (not
        # ``<run_id>.json``). The bare-``.json`` assertion was a
        # that started silently passing on
        # tmp-dir filesystem oddities and only began failing under
        # CI's deterministic POSIX runners.
        persisted = _isolated_runs_dir / f"{run_id}.envelope.json"
        assert persisted.exists()

    def test_run_for_period(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            root_app,
            [
                "workflow",
                "run",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--json",
                "--no-sync",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_show_round_trips(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        first = runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        assert first.exit_code == 0
        run_id = _unwrap_result(first.output)["run_id"]
        second = runner.invoke(root_app, ["workflow", "show", run_id, "--json"])
        assert second.exit_code == 0, second.output
        assert _unwrap_result(second.output)["run_id"] == run_id

    def test_list_enumerates(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        listing = runner.invoke(root_app, ["workflow", "list", "--json"])
        assert listing.exit_code == 0, listing.output
        payload = _unwrap_result(listing.output)
        assert len(payload) >= 1
