"""Real-behavior offline coverage for the install-time constraint-effect gate.

No mocks: a throwaway stub interpreter script emits a controlled
``importlib.metadata``-shaped distribution JSON and is passed to
:func:`assert_installed_matches_constraints` as the installed interpreter, so the
subprocess enumeration path runs exactly as it does against a real venv python.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from dev.packaging.constraint_effect import (
    ConstraintDriftError,
    assert_installed_matches_constraints,
    normalise_distribution_name,
    parse_constraint_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# A constraint closure shaped like a real ``uv export``: mandatory (marker-free)
# rows, a comment, a blank line, and platform-gated rows carrying markers.
_CONSTRAINT_LINES: tuple[str, ...] = (
    "# Runtime dependency closure pinned from the tested uv.lock.",
    "",
    "anyio==4.11.0",
    "click==8.3.0",
    "pydantic==2.12.4",
    "colorama==0.4.6 ; sys_platform == 'win32'",
    "jeepney==0.9.0 ; sys_platform == 'linux'",
)


def _stub_interpreter(tmp_path: Path, distributions: Mapping[str, str]) -> Path:
    """Write a stub python script that emits the given installed distribution set.

    The script mirrors the JSON shape the real enumeration one-liner prints, so
    :func:`enumerate_installed_distributions` parses it through the identical
    subprocess path. It is executed by the current interpreter via a shebang-free
    ``python <script>`` call, so the stub itself needs no execute bit.
    """
    payload = json.dumps(dict(distributions))
    script = tmp_path / "stub_metadata_interpreter.py"
    script.write_text(f"print({payload!r})\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IRUSR)
    return script


def _run_against_stub(tmp_path: Path, distributions: Mapping[str, str]) -> None:
    """Drive the real assertion against a stub interpreter emitting ``distributions``."""
    script = _stub_interpreter(tmp_path, distributions)
    # A tiny launcher interpreter: a shell/py shim would couple to the platform,
    # so instead wrap the real interpreter to run the stub script and ignore the
    # ``-c`` enumeration snippet the helper passes. Realised as an executable
    # script the helper calls as ``python_exe``.
    launcher = tmp_path / ("stub_python" + (".cmd" if os.name == "nt" else ""))
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
    assert_installed_matches_constraints(launcher, _CONSTRAINT_LINES)


def test_passing_case_matches_every_mandatory_pin(tmp_path: Path) -> None:
    """An installed set at the exact pins, missing only a foreign-platform row, passes."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        # colorama present at its pin (this is the win32 gated row); jeepney is
        # a linux-only gated row and is legitimately absent here.
        "colorama": "0.4.6",
        # An unconstrained extra distribution is ignored, not flagged.
        "cadrumo": "0.2.1",
    }
    _run_against_stub(tmp_path, installed)


def test_drifted_version_is_named_with_expected_and_actual(tmp_path: Path) -> None:
    """A single drifted mandatory distribution is enumerated as expected vs actual."""
    installed = {
        "anyio": "4.11.0",
        "click": "8.2.0",  # drifted: pinned to 8.3.0
        "pydantic": "2.12.4",
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_stub(tmp_path, installed)
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
        # pydantic (mandatory) omitted entirely.
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_stub(tmp_path, installed)
    message = str(excinfo.value)
    assert "pydantic" in message
    assert "actual <missing>" in message


def test_gated_row_absence_is_tolerated_but_drift_when_present_is_refused(tmp_path: Path) -> None:
    """A marker-gated distribution is conditional: absent tolerated, present-drift refused."""
    drifted_gated = {
        "anyio": "4.11.0",
        "click": "8.3.0",
        "pydantic": "2.12.4",
        "colorama": "0.4.5",  # gated (win32) but installed at the wrong pin
    }
    with pytest.raises(ConstraintDriftError) as excinfo:
        _run_against_stub(tmp_path, drifted_gated)
    assert "colorama" in str(excinfo.value)


def test_parse_rejects_a_non_pinned_row() -> None:
    """A loose (non ``==``) requirement can never pass silently through the gate."""
    with pytest.raises(ConstraintDriftError):
        parse_constraint_lines(("anyio>=4.0",))


def test_name_normalisation_follows_pep_503() -> None:
    """Runs of ``-_.`` collapse to a single ``-`` under lowercase normalisation."""
    assert normalise_distribution_name("Typing_Extensions") == "typing-extensions"
    assert normalise_distribution_name("zope..interface") == "zope-interface"
    assert normalise_distribution_name("Ruamel__Yaml") == "ruamel-yaml"
