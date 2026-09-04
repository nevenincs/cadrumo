"""Tests for the cohort oracle-emit leg's refusals and its argument contract.

`dev.quality.module_test_reach` listed `dev/packaging/oracle_emit_cohort.py` as
unreached and writing to the tree. Most of the module is an orchestration of two
real ``uv`` invocations against digest-pinned wheels, and that part is what the
packaging-smoke workflow itself exercises on every OS leg; reproducing it here
would need a real release cohort and prove nothing the live legs do not.

What has no coverage anywhere is the boundary the operator actually touches: the
executable resolution and the parsed argument contract. Those decide whether a
mistyped flag produces an instructive refusal or a stack trace, and whether a leg
that omits an option silently runs with a different timeout or interpreter than
its siblings - which would diverge the cohort id the module exists to keep
singular.

``AcquisitionError`` subclasses ``SystemExit`` precisely so a refusal exits
non-zero with its rendered message. A ``FileNotFoundError`` escaping instead is
not a smaller version of that; it is the failure mode the type was introduced to
remove.
"""

from __future__ import annotations

import pathlib

import pytest

from .._acquire_common import AcquisitionError
from ..oracle_emit_cohort import _parser, _resolve_uv

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _executable(directory: pathlib.Path, name: str = "uv") -> pathlib.Path:
    target = directory / name
    target.write_text("", encoding="utf-8")
    return target


def test_an_explicit_override_is_resolved_to_an_absolute_path(tmp_path: pathlib.Path) -> None:
    """The path is handed to a subprocess with a different cwd, so it must be absolute."""
    override = _executable(tmp_path)

    assert _resolve_uv(override) == override.resolve()


def test_a_relative_override_is_made_absolute(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both uv invocations run with ``cwd=work``, where a relative path means something else."""
    override = _executable(tmp_path)
    monkeypatch.chdir(tmp_path)

    resolved = _resolve_uv(pathlib.Path("uv"))

    assert resolved.is_absolute()
    assert resolved == override.resolve()


def test_an_override_that_does_not_exist_refuses_instructively(tmp_path: pathlib.Path) -> None:
    """A mistyped flag must render the refusal, not a pathlib traceback.

    ``AcquisitionError`` subclasses ``SystemExit`` so the leg exits non-zero with
    its message. Strict resolution raises ``OSError`` instead, which escaped the
    module entirely and reached the operator as a stack for a mistyped flag
    rather than as the flag they mistyped.
    """
    missing = tmp_path / "not-installed" / "uv"

    with pytest.raises(AcquisitionError) as refusal:
        _resolve_uv(missing)

    assert "--uv" in str(refusal.value)


def test_an_absent_uv_on_path_names_the_flag_that_fixes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refusal that does not say what to do next spends the operator's next hour."""
    monkeypatch.setenv("PATH", "")

    with pytest.raises(AcquisitionError) as refusal:
        _resolve_uv(None)

    assert "--uv" in str(refusal.value)


def test_the_leg_defining_options_are_all_required() -> None:
    """Defaulting any of these would let one OS leg prove a different thing.

    The cohort directory, the row id and the work directory are what bind the
    emitted row to one cohort on one operating system; a default would make an
    omission silent rather than fatal.
    """
    with pytest.raises(SystemExit):
        _parser().parse_args(["--row-id", "python-linux-x86-64", "--work-dir", "work"])


def test_the_optional_defaults_are_the_same_on_every_leg() -> None:
    """Every OS leg must agree, or the rows bind cohorts built differently.

    The module exists so all Python rows carry one cohort id; an interpreter or
    timeout that varies per leg reintroduces the per-OS divergence by another
    route.
    """
    parsed = _parser().parse_args(
        ["--release-cohort-dir", "cohort", "--row-id", "python-linux-x86-64", "--work-dir", "work"],
    )

    assert parsed.python == "3.13"
    assert parsed.timeout_seconds == 300.0
    assert parsed.uv is None
    assert parsed.distribution_evidence_dir is None


def test_the_path_options_are_parsed_as_paths_rather_than_strings() -> None:
    """They are joined and resolved downstream, where a string would not behave."""
    parsed = _parser().parse_args(
        [
            "--release-cohort-dir",
            "cohort",
            "--row-id",
            "python-linux-x86-64",
            "--work-dir",
            "work",
            "--distribution-evidence-dir",
            "evidence",
        ],
    )

    assert isinstance(parsed.release_cohort_dir, pathlib.Path)
    assert isinstance(parsed.work_dir, pathlib.Path)
    assert isinstance(parsed.distribution_evidence_dir, pathlib.Path)


def test_the_timeout_is_numeric_so_a_typo_refuses_rather_than_running_forever() -> None:
    """A string timeout would reach the subprocess call and fail late, mid-install."""
    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "--release-cohort-dir",
                "cohort",
                "--row-id",
                "python-linux-x86-64",
                "--work-dir",
                "work",
                "--timeout-seconds",
                "five-minutes",
            ],
        )
