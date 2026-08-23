"""Noise-resistant contracts for CLI latency calibration and budgets."""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest
import typer

from cadrumo.tests.cli_performance import (
    CliPerformanceObservation,
    CliPerformanceProfile,
    LatencyBudget,
    LatencyDistribution,
    PerformanceCalibrationPolicy,
    evaluate_latency_budget,
    profile_cli_path,
)

from .._app_execution_policies import METADATA
from .._command_policy import command_execution_policy
from .._command_suggestions import CadrumoTyperGroup, LiveCommandNode, walk_live_command_tree

pytestmark = pytest.mark.hex_entrypoint


@pytest.mark.unit
def test_calibration_rejects_single_sample_and_missing_warmup() -> None:
    with pytest.raises(ValueError, match="three measured samples"):
        PerformanceCalibrationPolicy(sample_count=1)
    with pytest.raises(ValueError, match="one warmup"):
        PerformanceCalibrationPolicy(warmup_runs=0)
    with pytest.raises(ValueError, match="three samples"):
        LatencyDistribution.from_samples((0.01,))


@pytest.mark.unit
def test_one_fast_sample_cannot_rescue_a_slow_distribution() -> None:
    distribution = LatencyDistribution.from_samples((0.01, 2.0, 2.1, 2.2, 2.3))

    result = evaluate_latency_budget(distribution, LatencyBudget(maximum_median_seconds=1.0))

    assert distribution.median_seconds == 2.1
    assert result.passed is False
    assert result.violations == ("absolute-median",)
    assert result.outlier_samples_seconds == (2.0, 2.1, 2.2, 2.3)


@pytest.mark.unit
def test_absolute_and_control_ratio_limits_are_independent_and_composable() -> None:
    observed = LatencyDistribution.from_samples((0.38, 0.4, 0.42))
    control = LatencyDistribution.from_samples((0.09, 0.1, 0.11))

    ratio_failure = evaluate_latency_budget(
        observed,
        LatencyBudget(maximum_median_seconds=0.5, maximum_control_ratio=3.0),
        control=control,
    )
    absolute_failure = evaluate_latency_budget(observed, LatencyBudget(maximum_median_seconds=0.3))

    assert ratio_failure.control_ratio == 4.0
    assert ratio_failure.violations == ("control-ratio",)
    assert absolute_failure.control_ratio is None
    assert absolute_failure.violations == ("absolute-median",)


@pytest.mark.unit
def test_ratio_budget_requires_a_positive_control_distribution() -> None:
    observed = LatencyDistribution.from_samples((0.1, 0.1, 0.1))

    with pytest.raises(ValueError, match="control distribution"):
        evaluate_latency_budget(observed, LatencyBudget(maximum_control_ratio=2.0))
    with pytest.raises(ValueError, match="control median"):
        evaluate_latency_budget(
            observed,
            LatencyBudget(maximum_control_ratio=2.0),
            control=LatencyDistribution.from_samples((0.0, 0.0, 0.0)),
        )


@pytest.mark.unit
@pytest.mark.parametrize("samples", [(1.0, float("nan"), 2.0), (1.0, -0.1, 2.0)])
def test_distribution_rejects_invalid_measurements(samples: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        LatencyDistribution.from_samples(samples)


def _observations(profile: CliPerformanceProfile) -> tuple[CliPerformanceObservation, ...]:
    return profile.resolution, profile.invocation


def _require_no_new_imports(
    control: CliPerformanceObservation,
    candidate: CliPerformanceObservation,
    *,
    family: str,
) -> None:
    added = tuple(sorted(set(candidate.import_families[family]) - set(control.import_families[family])))
    assert not added, f"unexpected {family} imports: {', '.join(added)}"


def _filesystem_changes(observation: CliPerformanceObservation) -> frozenset[str]:
    return frozenset(
        (*observation.filesystem_created, *observation.filesystem_modified, *observation.filesystem_deleted)
    )


def _require_no_new_filesystem_changes(
    control: CliPerformanceObservation,
    candidate: CliPerformanceObservation,
) -> None:
    added = tuple(sorted(_filesystem_changes(candidate) - _filesystem_changes(control)))
    assert not added, f"unexpected filesystem changes: {', '.join(added)}"


def _write_fresh_process_injector(directory: Path, body: str) -> Path:
    """Install a real interpreter hook that fires inside the observed phase.

    ``sitecustomize`` itself loads before the profiler snapshots ``sys.modules``.
    Its trace function waits for the profiler's real resolution/invocation
    boundary, so the planted work occurs after observation begins.  This keeps
    the mutation outside tracked source and exercises the same import and OS
    paths as an accidental eager registration would.
    """
    directory.mkdir()
    (directory / "sitecustomize.py").write_text(
        dedent(
            f"""
            import sys

            def _plant(frame, event, arg):
                if (
                    event == "call"
                    and frame.f_globals.get("__name__") == "__main__"
                    and frame.f_code.co_name in {{"_resolve_cli_path", "_invoke_cli"}}
                ):
                    sys.settrace(None)
                    {body}
                return _plant

            sys.settrace(_plant)
            """
        ),
        encoding="utf-8",
    )
    return directory


def _injector_env(directory: Path) -> dict[str, str]:
    inherited = os.environ.get("PYTHONPATH")
    value = str(directory) if not inherited else os.pathsep.join((str(directory), inherited))
    return {"PYTHONPATH": value}


@pytest.mark.integration
def test_fresh_process_gate_bites_on_unrelated_registry_loading(tmp_path: Path) -> None:
    """Both resolution and safe help expose a planted eager registry import."""
    storage = tmp_path / "storage"
    control = profile_cli_path((), invocation_args=("--help",), storage_root=storage)
    injector = _write_fresh_process_injector(
        tmp_path / "registry-injector",
        'import importlib; importlib.import_module("cadrumo.application.registry")',
    )
    planted = profile_cli_path(
        (),
        invocation_args=("--help",),
        storage_root=storage,
        extra_env=_injector_env(injector),
    )

    for control_phase, planted_phase in zip(_observations(control), _observations(planted), strict=True):
        assert control_phase.exit_code == planted_phase.exit_code == 0
        added = set(planted_phase.import_families["registry"]) - set(control_phase.import_families["registry"])
        assert {
            "cadrumo.application.registry",
            "cadrumo.domain.calculations.registry",
        } <= added
        with pytest.raises(AssertionError, match=r"cadrumo\.application\.registry") as failure:
            _require_no_new_imports(control_phase, planted_phase, family="registry")
        assert "unexpected registry imports" in str(failure.value)
    assert tuple(storage.iterdir()) == ()


@pytest.mark.integration
def test_fresh_process_gate_bites_on_filesystem_materialization(tmp_path: Path) -> None:
    """Both resolution and safe help expose a planted storage-root write."""
    storage = tmp_path / "storage"
    control = profile_cli_path((), invocation_args=("--help",), storage_root=storage)
    injector = _write_fresh_process_injector(
        tmp_path / "filesystem-injector",
        (
            'from pathlib import Path; import os; '
            'marker = Path(os.environ["CADRUMO_LOCAL_STORAGE_ROOT"]) / "planted-materialization"; '
            'marker.mkdir(); (marker / "unexpected.txt").write_text("planted", encoding="utf-8")'
        ),
    )
    planted = profile_cli_path(
        (),
        invocation_args=("--help",),
        storage_root=storage,
        extra_env=_injector_env(injector),
    )

    for control_phase, planted_phase in zip(_observations(control), _observations(planted), strict=True):
        assert control_phase.exit_code == planted_phase.exit_code == 0
        added = _filesystem_changes(planted_phase) - _filesystem_changes(control_phase)
        assert added == frozenset(
            {
                "planted-materialization",
                "planted-materialization/unexpected.txt",
            }
        )
        assert planted_phase.filesystem_operations["open.write"] > control_phase.filesystem_operations["open.write"]
        assert planted_phase.filesystem_operations["os.mkdir"] > control_phase.filesystem_operations["os.mkdir"]
        with pytest.raises(AssertionError, match=r"planted-materialization/unexpected\.txt") as failure:
            _require_no_new_filesystem_changes(control_phase, planted_phase)
        assert "unexpected filesystem changes" in str(failure.value)
    assert tuple(storage.iterdir()) == ()


def _require_complete_policy(nodes: tuple[LiveCommandNode, ...]) -> None:
    missing = tuple(" ".join(node.path) for node in nodes if node.execution_policy is None)
    assert not missing, f"unclassified CLI nodes: {', '.join(missing)}"


def _classified_callback() -> None:
    return None


command_execution_policy(METADATA)(_classified_callback)


def _planted_unclassified_tree(shape: str) -> typer.Typer:
    root = typer.Typer(name=f"planted-{shape}", cls=CadrumoTyperGroup)
    if shape != "root":
        root.callback()(_classified_callback)
    else:

        @root.callback()
        def unclassified_root() -> None:
            return None

    if shape == "group":
        generated = typer.Typer(name="generated", cls=CadrumoTyperGroup)

        @generated.callback()
        def unclassified_generated_group() -> None:
            return None

        generated.command("classified-leaf")(_classified_callback)
        root.add_typer(generated, name="generated")
    elif shape == "leaf":

        @root.command("unclassified-leaf")
        def unclassified_leaf() -> None:
            return None

    return root


@pytest.mark.unit
@pytest.mark.parametrize(
    ("shape", "offending_path"),
    [
        ("root", "planted-root"),
        ("group", "planted-group generated"),
        ("leaf", "planted-leaf unclassified-leaf"),
    ],
)
def test_census_gate_bites_on_every_unclassified_node_shape(shape: str, offending_path: str) -> None:
    """Future roots, helper-generated groups, and leaves all fail closed."""
    nodes = walk_live_command_tree(_planted_unclassified_tree(shape))

    with pytest.raises(AssertionError, match=offending_path) as failure:
        _require_complete_policy(nodes)
    assert "unclassified CLI nodes" in str(failure.value)
