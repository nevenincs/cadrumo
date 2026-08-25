"""Fresh-process proofs that the CLI latency gate bites on real work."""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest

from ....tests.cli_performance import (
    CliPerformanceObservation,
    CliPerformanceProfile,
    profile_cli_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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


def test_fresh_process_gate_bites_on_filesystem_materialization(tmp_path: Path) -> None:
    """Both resolution and safe help expose a planted storage-root write."""
    storage = tmp_path / "storage"
    control = profile_cli_path((), invocation_args=("--help",), storage_root=storage)
    injector = _write_fresh_process_injector(
        tmp_path / "filesystem-injector",
        (
            "from pathlib import Path; import os; "
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
