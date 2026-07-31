"""Real-behavior offline coverage for the install-time constraint-effect gate.

No mocks: a throwaway synthetic-metadata interpreter script emits a controlled
``importlib.metadata``-shaped distribution JSON and is passed to
:func:`assert_installed_matches_constraints` as the installed interpreter, so the
subprocess enumeration path runs exactly as it does against a real venv python.

Environment markers are exercised deterministically on any platform by phrasing
them relative to the running ``sys.platform``: a ``THIS``-platform marker is
always active here and an ``OTHER``-platform marker never is.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from dev.packaging.constraint_effect import (
    ConstraintDriftError,
    assert_installed_matches_constraints,
    parse_constraint_lines,
)
from dev.packaging._distribution_names import normalise_distribution_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# Phrased against the running platform so the marker evaluation is deterministic
# on Windows, Linux, and macOS alike.
_THIS_PLATFORM = sys.platform
_OTHER_PLATFORM = "linux" if sys.platform != "linux" else "darwin"

# A constraint closure shaped like a real ``uv export``: mandatory (marker-free)
# rows, a comment, a blank line, an active platform-gated row (marker true here),
# and a foreign-platform row (marker false here).
_CONSTRAINT_LINES: tuple[str, ...] = (
    "# Runtime dependency closure pinned from the tested uv.lock.",
    "",
    "anyio==4.11.0",
    "click==8.3.0",
    "pydantic==2.12.4",
    f"activehere==1.0.0 ; sys_platform == '{_THIS_PLATFORM}'",
    f"foreignonly==9.9.9 ; sys_platform == '{_OTHER_PLATFORM}'",
)

# One name pinned under two mutually exclusive markers. Only the running
# platform's version is active; the old union behaviour would have accepted
# either version.
_DUAL_MARKER_LINES: tuple[str, ...] = (
    "anyio==4.11.0",
    f"dualpin==1.0.0 ; sys_platform == '{_THIS_PLATFORM}'",
    f"dualpin==2.0.0 ; sys_platform == '{_OTHER_PLATFORM}'",
)


def _synthetic_metadata_interpreter(tmp_path: Path, distributions: Mapping[str, str]) -> Path:
    """Write a synthetic python script that emits the given installed distribution set.

    The script mirrors the JSON shape the real enumeration one-liner prints, so
    :func:`enumerate_installed_distributions` parses it through the identical
    subprocess path. It is executed by the current interpreter via a shebang-free
    ``python <script>`` call, so the synthetic script itself needs no execute bit.
    """
    payload = json.dumps(dict(distributions))
    script = tmp_path / "synthetic_metadata_interpreter.py"
    script.write_text(f"print({payload!r})\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IRUSR)
    return script


def _run_against_synthetic_interpreter(
    tmp_path: Path,
    distributions: Mapping[str, str],
    *,
    constraint_lines: Sequence[str] = _CONSTRAINT_LINES,
) -> None:
    """Drive the real assertion against a synthetic interpreter emitting ``distributions``."""
    script = _synthetic_metadata_interpreter(tmp_path, distributions)
    # A tiny launcher interpreter: a shell/py shim would couple to the platform,
    # so instead wrap the real interpreter to run the stub script and ignore the
    # ``-c`` enumeration snippet the helper passes. Realised as an executable
    # script the helper calls as ``python_exe``.
    launcher = tmp_path / ("synthetic_python" + (".cmd" if os.name == "nt" else ""))
    if os.name == "nt":
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}"\r\n',
            encoding="utf-8",
        )
    else:
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n',
            encoding="utf-8",
        )
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)
    assert_installed_matches_constraints(launcher, constraint_lines)


def test_passing_case_matches_every_active_pin(tmp_path: Path) -> None:
    """An installed set at the exact active pins, without any foreign row, passes."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        # The active (this-platform) gated row must be present at its pin.
        "activehere": "1.0.0",
        # An unconstrained extra distribution is ignored, not flagged.
        "cadrumo": "0.2.1",
    }
    _run_against_synthetic_interpreter(tmp_path, installed)


def test_foreign_platform_row_is_ignored_even_when_installed(tmp_path: Path) -> None:
    """A row whose marker is false here constrains nothing, present or not."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        "activehere": "1.0.0",
        # foreignonly's marker is false here; installed at an off-pin version, it
        # must NOT be flagged, because this platform's closure does not pin it.
        "foreignonly": "0.0.1",
    }
    _run_against_synthetic_interpreter(tmp_path, installed)


def test_drifted_version_is_named_with_expected_and_actual(tmp_path: Path) -> None:
    """A single drifted mandatory distribution is enumerated as expected vs actual."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.2.0",  # drifted: pinned to 8.3.0
        "pydantic": "2.12.4",
        "activehere": "1.0.0",
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_synthetic_interpreter(tmp_path, installed)
    message = str(excinfo.value)
    assert "click" in message
    assert "expected 8.3.0" in message
    assert "actual 8.2.0" in message
    # The un-drifted distributions must not be named in the refusal.
    assert "anyio" not in message
    assert "pydantic" not in message


def test_missing_mandatory_distribution_is_reported(tmp_path: Path) -> None:
    """A mandatory pin absent from the installed set is refused as <missing>."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "activehere": "1.0.0",
        # pydantic (mandatory) omitted entirely.
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_synthetic_interpreter(tmp_path, installed)
    message = str(excinfo.value)
    assert "pydantic" in message
    assert "actual <missing>" in message


def test_active_gated_distribution_missing_on_its_own_platform_is_refused(tmp_path: Path) -> None:
    """A gated row active here is mandatory: its absence fails (not tolerated)."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        # activehere's marker holds on this platform, so it must be installed;
        # under the retired if-installed heuristic its absence was tolerated.
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_synthetic_interpreter(tmp_path, installed)
    message = str(excinfo.value)
    assert "activehere" in message
    assert "actual <missing>" in message


def test_active_gated_distribution_present_at_wrong_pin_is_refused(tmp_path: Path) -> None:
    """An active gated distribution installed at the wrong version is refused."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        "activehere": "1.0.1",  # active gated row, wrong pin
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_synthetic_interpreter(tmp_path, installed)
    assert "activehere" in str(excinfo.value)


def test_mutually_exclusive_marker_accepts_only_the_active_version(tmp_path: Path) -> None:
    """Only the version whose marker holds is accepted; the old union would pass.

    ``dualpin`` is pinned to 1.0.0 (this platform) and 2.0.0 (another). The
    installed 2.0.0 is the OTHER platform's pin; the marker-union behaviour would
    have accepted it, but marker evaluation accepts only 1.0.0 here.
    """
    installed = {
        "anyio": "4.11.0",
        "dualpin": "2.0.0",  # the foreign-platform pin
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_synthetic_interpreter(tmp_path, installed, constraint_lines=_DUAL_MARKER_LINES)
    message = str(excinfo.value)
    assert "dualpin" in message
    assert "expected 1.0.0" in message
    assert "actual 2.0.0" in message


def test_mutually_exclusive_marker_accepts_the_active_version(tmp_path: Path) -> None:
    """The version whose marker holds on this platform passes."""
    installed = {
        "anyio": "4.11.0",
        "dualpin": "1.0.0",  # this platform's pin
    }
    _run_against_synthetic_interpreter(tmp_path, installed, constraint_lines=_DUAL_MARKER_LINES)


def test_parse_rejects_a_non_pinned_row() -> None:
    """A loose (non ``==``) requirement can never pass silently through the gate."""
    with pytest.raises(ConstraintDriftError):
        parse_constraint_lines(("anyio>=4.0",))


def test_parse_evaluates_markers_against_the_running_platform() -> None:
    """The parsed map keeps only rows whose marker holds here."""
    pins = parse_constraint_lines(_CONSTRAINT_LINES)
    assert "activehere" in pins
    assert "foreignonly" not in pins
    assert pins["activehere"].versions == frozenset({"1.0.0"})


def test_name_normalisation_follows_pep_503() -> None:
    """Runs of ``-_.`` collapse to a single ``-`` under lowercase normalisation."""
    assert normalise_distribution_name("Typing_Extensions") == "typing-extensions"
    assert normalise_distribution_name("zope..interface") == "zope-interface"
    assert normalise_distribution_name("Ruamel__Yaml") == "ruamel-yaml"
    assert normalise_distribution_name("  Uv...Build__Backend  ") == "uv-build-backend"
