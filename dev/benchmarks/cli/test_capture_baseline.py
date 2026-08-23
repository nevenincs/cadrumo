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


def test_gate_bites_when_ranked_outlier_order_is_tampered() -> None:
    """A complete set in the wrong ranking order is still stale evidence."""
    payload = _committed_baseline()
    ranked = payload["ranked_outliers"]
    assert isinstance(ranked, dict)
    resolution = ranked["resolution_by_control_ratio"]
    assert isinstance(resolution, list)
    resolution.reverse()

    with pytest.raises(RuntimeError, match="ranked outlier order"):
        check_baseline(payload)


def test_gate_bites_when_a_raw_sample_or_derived_median_is_tampered() -> None:
    """Stored distributions must be exact derivations of raw observations."""
    raw_payload = _committed_baseline()
    commands = raw_payload["commands"]
    assert isinstance(commands, dict)
    first = commands[next(iter(commands))]
    assert isinstance(first, dict)
    samples = first["samples"]
    assert isinstance(samples, list)
    sample = samples[0]
    assert isinstance(sample, dict)
    resolution = sample["resolution"]
    assert isinstance(resolution, dict)
    resolution["wall_seconds"] = 999999.0

    with pytest.raises(RuntimeError, match="distribution disagrees"):
        check_baseline(raw_payload)

    derived_payload = _committed_baseline()
    derived_commands = derived_payload["commands"]
    assert isinstance(derived_commands, dict)
    derived = derived_commands[next(iter(derived_commands))]
    assert isinstance(derived, dict)
    distributions = derived["distribution"]
    assert isinstance(distributions, dict)
    derived_resolution = distributions["resolution"]
    assert isinstance(derived_resolution, dict)
    derived_resolution["median_seconds"] = 999999.0

    with pytest.raises(RuntimeError, match="distribution disagrees"):
        check_baseline(derived_payload)


def test_gate_bites_when_control_distribution_or_method_count_is_tampered() -> None:
    """Calibration summaries and declared sample counts derive from observations."""
    control_payload = _committed_baseline()
    control = control_payload["control"]
    assert isinstance(control, dict)
    distribution = control["distribution"]
    assert isinstance(distribution, dict)
    resolution = distribution["resolution"]
    assert isinstance(resolution, dict)
    resolution["median_seconds"] = 999999.0

    with pytest.raises(RuntimeError, match="control distribution"):
        check_baseline(control_payload)

    method_payload = _committed_baseline()
    method = method_payload["method"]
    assert isinstance(method, dict)
    method["samples_per_node"] = 4

    with pytest.raises(RuntimeError, match="insufficient CLI baseline samples"):
        check_baseline(method_payload)


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
