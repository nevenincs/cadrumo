"""Contracts for the complete live CLI baseline generator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from dev.benchmarks.cli.capture_baseline import DEFAULT_OUTPUT, _copy_source_snapshot, check_baseline

from cadrumo.entrypoints.cli import app
from cadrumo.entrypoints.cli._command_suggestions import walk_live_command_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _committed_baseline() -> dict[str, object]:
    payload: object = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return cast("dict[str, object]", payload)


def test_committed_baseline_is_an_exact_live_census_with_safe_samples() -> None:
    """The checked-in evidence exactly covers the current live tree."""
    check_baseline(_committed_baseline())


def test_exact_set_gate_bites_when_a_live_path_is_absent() -> None:
    """Removing one dynamically selected path makes the gate red."""
    payload = _committed_baseline()
    commands = payload["commands"]
    assert isinstance(commands, dict)
    commands.pop(next(iter(commands)))

    with pytest.raises(RuntimeError, match="stale CLI baseline"):
        check_baseline(payload)


def test_gate_bites_when_help_mode_is_claimed_as_handler_execution() -> None:
    """The artifact cannot overclaim that safe help ran a handler."""
    payload = _committed_baseline()
    commands = payload["commands"]
    assert isinstance(commands, dict)
    entry = commands[next(iter(commands))]
    assert isinstance(entry, dict)
    entry["invocation_mode"] = "handler-execution"

    with pytest.raises(RuntimeError, match="unsafe or dishonest"):
        check_baseline(payload)


def test_live_census_has_no_fixed_count_assumption() -> None:
    """Enrollment equality derives from paths rather than a frozen tally."""
    paths = {node.path for node in walk_live_command_tree(app)}
    payload = _committed_baseline()
    commands = payload["commands"]
    assert isinstance(commands, dict)

    assert {tuple(path.split(" ")) for path in commands} == paths


def test_frozen_import_root_ignores_later_live_source_mutation(tmp_path: Path) -> None:
    """A later shared-tree edit cannot alter subsequent snapshot imports."""
    live_package = tmp_path / "live" / "cadrumo"
    live_package.mkdir(parents=True)
    live_module = live_package / "__init__.py"
    live_module.write_text("IDENTITY = 'before'\n", encoding="utf-8")
    snapshot_package = tmp_path / "snapshot" / "cadrumo"
    _copy_source_snapshot(live_package, snapshot_package)

    live_module.write_text("IDENTITY = 'after'\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(snapshot_package.parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-P", "-c", "import cadrumo; print(cadrumo.IDENTITY)"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "before"
