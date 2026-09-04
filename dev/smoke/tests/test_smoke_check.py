"""Tests for the distribution smoke check's refusals.

`dev.quality.module_test_reach` listed `dev/smoke/smoke_check.py` as unreached.
It is the last gate a published wheel passes through: CI runs it against the
installed artifact to establish the package imports, reports its version, and
exposes both console scripts.

Its metadata check called ``importlib.metadata.version`` unguarded. An absent
distribution raises ``PackageNotFoundError``, and this runs in an isolated
environment whose only content is the artifact under test - so a companion
corpus that failed to install, which is the likeliest packaging failure there
is and precisely what the check exists to catch, surfaced as an unhandled
traceback instead of the one FAIL line every other refusal here produces.

Only the refusal paths and the command construction are exercised. The checks
that drive the console scripts belong to a built wheel in an isolated
environment, and running them from inside this repository would prove something
about this checkout rather than about a distribution.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from ..smoke_check import (
    CLI_SCRIPT,
    COMPANIONS,
    MCP_SCRIPT,
    _fail,
    _ok,
    _run,
    installed_version,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_refusal_exits_non_zero_and_names_the_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every failure in this file routes here, so its shape is the whole contract."""
    with pytest.raises(SystemExit) as exit_info:
        _fail("the corpora disagree")

    assert exit_info.value.code == 1
    assert "FAIL: the corpora disagree" in capsys.readouterr().err


def test_a_pass_is_reported_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """CI reads these lines to see which checks actually ran."""
    _ok("something held")

    assert "ok: something held" in capsys.readouterr().out


def test_an_absent_distribution_refuses_instead_of_raising(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The defect: the likeliest packaging failure bypassed the refusal path.

    ``PackageNotFoundError`` reaching the top of the process replaces one
    diagnostic line with a traceback, in the one run where a reader has only
    the CI log to work from.
    """
    with pytest.raises(SystemExit) as exit_info:
        installed_version("cadrumo-data-that-was-never-published")

    assert exit_info.value.code == 1
    assert "is not installed" in capsys.readouterr().err


def test_an_installed_distribution_returns_its_version() -> None:
    """The success path, so the guard cannot be satisfied by refusing everything."""
    assert installed_version("cadrumo")


def test_both_companion_corpora_are_named() -> None:
    """The version agreement is checked across these, so the set is the contract.

    A companion dropped from this tuple would stop being compared and a
    mismatched corpus would ship silently.
    """
    assert COMPANIONS == ("cadrumo-data-manuals", "cadrumo-data-official")


def test_a_script_on_path_is_invoked_directly(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The console script is the surface under test, so it must be preferred.

    Proven by a launcher that exits with a code nothing else would produce:
    if the module fallback had run instead, the status would be an import
    failure rather than this one.
    """
    if os.name == "nt":
        launcher = tmp_path / (CLI_SCRIPT + ".cmd")
        launcher.write_text("@echo off" + chr(10) + "exit /b 7" + chr(10), encoding="utf-8")
    else:
        launcher = tmp_path / CLI_SCRIPT
        launcher.write_text("#!/bin/sh" + chr(10) + "exit 7" + chr(10), encoding="utf-8")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    result = _run(CLI_SCRIPT, ["--version"])

    assert result.returncode == 7, result.stderr


def test_a_missing_script_falls_back_to_the_module_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """A console script absent from PATH must still produce a diagnosable result.

    The fallback runs the module form, and what matters is that the check
    returns a completed process to be judged rather than raising - the caller
    reports the exit status and stderr, which is what tells CI whether the
    entry point shipped.
    """
    monkeypatch.setenv("PATH", "")

    result = _run(MCP_SCRIPT, ["--help"])

    assert result.returncode != 0
    assert result.stderr
