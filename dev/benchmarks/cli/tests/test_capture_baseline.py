"""Contracts for the complete live CLI baseline generator."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from ..capture_baseline import (
    DEFAULT_OUTPUT,
    _copy_source_snapshot,
    _load_raw_evidence,
    _publish_raw_and_summary,
    _reject_unexpected_checkpoint_commands,
    _write_json_atomic,
    check_baseline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _committed_baseline() -> dict[str, object]:
    payload: object = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return cast("dict[str, object]", payload)


def test_committed_baseline_is_an_exact_live_census_with_safe_samples() -> None:
    """The checked-in evidence exactly covers the current live tree."""
    check_baseline(_committed_baseline())


def _republish_mutated_raw(
    tmp_path: Path, mutate: Callable[[dict[str, object]], None]
) -> tuple[dict[str, object], Path]:
    summary = _committed_baseline()
    raw = _load_raw_evidence(summary, baseline_path=DEFAULT_OUTPUT)
    commands = raw["commands"]
    assert isinstance(commands, dict)
    frozen: object = json.loads(DEFAULT_OUTPUT.with_name("baseline.census.json").read_text(encoding="utf-8"))
    assert isinstance(frozen, dict)
    raw["frozen_census"] = frozen["commands"]
    mutate(commands)
    output = tmp_path / "baseline.json"
    republished = _publish_raw_and_summary(output, raw)
    _write_json_atomic(output, republished)
    return cast("dict[str, object]", republished), output


def test_exact_set_gate_bites_on_coherently_republished_missing_node(tmp_path: Path) -> None:
    """Independent frozen authority rejects a self-consistent shortened pair."""

    def remove_first(commands: dict[str, object]) -> None:
        commands.pop(next(iter(commands)))

    payload, output = _republish_mutated_raw(tmp_path, remove_first)
    with pytest.raises(RuntimeError, match="exact-set mismatch"):
        check_baseline(payload, baseline_path=output)


def test_exact_set_gate_bites_on_coherently_republished_invented_node(tmp_path: Path) -> None:
    """Independent frozen authority rejects a self-consistent invented node."""

    def add_invented(commands: dict[str, object]) -> None:
        commands["aeat invented"] = next(iter(commands.values()))

    payload, output = _republish_mutated_raw(tmp_path, add_invented)
    with pytest.raises(RuntimeError, match="exact-set mismatch"):
        check_baseline(payload, baseline_path=output)


def test_resume_rejects_checkpoint_commands_outside_frozen_census() -> None:
    """A poisoned resume cannot carry an invented observation to publication."""
    with pytest.raises(RuntimeError, match="unexpected commands"):
        _reject_unexpected_checkpoint_commands({"aeat": {}, "aeat invented": {}}, ["aeat"])


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


def test_live_census_freshness_has_no_fixed_count_assumption() -> None:
    """Freshness compares dynamic paths and source identity, never a frozen tally."""
    payload = _committed_baseline()
    with pytest.raises(RuntimeError, match="source snapshot is stale"):
        check_baseline(payload, require_current_source=True)


def test_gate_bites_when_lossless_raw_evidence_is_corrupted(tmp_path: Path) -> None:
    """The compact summary cannot authenticate damaged lossless observations."""
    summary_path = tmp_path / "baseline.json"
    raw_path = tmp_path / "baseline.raw.json.gz"
    shutil.copyfile(DEFAULT_OUTPUT, summary_path)
    shutil.copyfile(DEFAULT_OUTPUT.with_name("baseline.raw.json.gz"), raw_path)
    shutil.copyfile(DEFAULT_OUTPUT.with_name("baseline.census.json"), tmp_path / "baseline.census.json")
    raw = bytearray(raw_path.read_bytes())
    raw[len(raw) // 2] ^= 1
    raw_path.write_bytes(raw)

    with pytest.raises(RuntimeError, match="compressed digest"):
        check_baseline(_committed_baseline(), baseline_path=summary_path)


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
