"""Tests for the self-hosted runner capability probe.

`dev.quality.module_test_reach` listed `dev/containers/runner_capabilities.py`
as unreached. It exists because half the fleet - the macOS and Windows hosts -
has no image pinning its tools, so a capability gap surfaces mid-lane as a
command-not-found inside a step that never names the missing tool.

Presence was being taken for capability. The version probe returned a detail
string for every outcome, including a binary that resolved but whose
``--version`` failed, and the caller marked the finding ``ok`` regardless. A gh
that could not run at all was reported under an ok marker and the probe exited
0 - which on a fleet where a job lands on whichever runner is free is exactly
the coin-flip failure this module exists to remove.

The probe is driven against real executables on disk: a launcher that reports a
version, one that exits non-zero, and a name that is absent. Nothing here calls
the live fleet checks, whose answers depend on the machine running the suite.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from ..runner_capabilities import _BREW_PATHS, Finding, _machine, version_probe

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _launcher(directory: pathlib.Path, name: str, *, exit_code: int, output: str) -> pathlib.Path:
    """Write an executable that prints ``output`` and exits ``exit_code``."""
    if os.name == "nt":
        path = directory / (name + ".cmd")
        body = ("@echo off", "echo " + output, "exit /b " + str(exit_code))
    else:
        path = directory / name
        body = ("#!/bin/sh", "echo " + output, "exit " + str(exit_code))
    path.write_text(chr(10).join(body) + chr(10), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o755)
    return path


def test_an_executable_that_reports_a_version_is_usable(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary carried-capability case."""
    _launcher(tmp_path, "probe-tool", exit_code=0, output="probe-tool 1.2.3")
    monkeypatch.setenv("PATH", str(tmp_path))

    usable, detail = version_probe("probe-tool")

    assert usable
    assert "1.2.3" in detail


def test_an_executable_that_cannot_run_is_not_usable(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect: this resolved on PATH and was reported as a carried capability.

    A broken install, a wrong-architecture binary or a missing runtime library
    all land here, and all of them fail the lane later at a step that names no
    tool.
    """
    _launcher(tmp_path, "probe-tool", exit_code=1, output="loader error")
    monkeypatch.setenv("PATH", str(tmp_path))

    usable, detail = version_probe("probe-tool")

    assert not usable
    assert "--version failed" in detail


def test_an_absent_executable_is_not_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case that already worked, kept so the fix is not a blanket refusal."""
    monkeypatch.setenv("PATH", "")

    usable, detail = version_probe("a-tool-that-is-not-installed-anywhere")

    assert not usable
    assert "not on PATH" in detail


def test_the_detail_names_where_the_broken_binary_was_found(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An operator with two installs on PATH needs to know which one answered."""
    launcher = _launcher(tmp_path, "probe-tool", exit_code=2, output="nope")
    monkeypatch.setenv("PATH", str(tmp_path))

    _, detail = version_probe("probe-tool")

    assert str(launcher.parent) in detail or launcher.stem in detail


def test_a_finding_carries_its_verdict_and_its_reason() -> None:
    """The report prints one line per finding; both halves are read."""
    finding = Finding("gh", ok=False, detail="not on PATH")

    assert finding.name == "gh"
    assert not finding.ok
    assert finding.detail


def test_the_architecture_token_is_normalised_away_from_the_windows_spelling() -> None:
    """The brew path table is keyed on this token, so a wrong one skips the check.

    Windows reports ``AMD64`` where the matrix legs say ``x86_64``. Leaving it
    unnormalised would miss every key in the table and return NO brew finding
    rather than a failing one - a capability gap reported as nothing at all.
    """
    architecture = _machine()

    assert architecture != "AMD64"
    assert architecture


def test_the_brew_table_is_keyed_on_normalised_tokens() -> None:
    """A key the normaliser can never produce is a leg that is never checked."""
    for system, machine in _BREW_PATHS:
        assert system in {"Darwin", "Linux"}
        assert machine in {"x86_64", "arm64", "aarch64"}
