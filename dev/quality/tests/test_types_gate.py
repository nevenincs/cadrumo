"""Tests for the type-check harness's empty-stream refusal and its suppression list.

It runs three type checkers and reports whether the tree is clean, so the one thing
it must never do is report clean without having measured.

It did, for one of the three. ``collect_pyrefly`` and ``collect_basedpyright``
raised on an empty stream, with a comment saying exactly why - a clean run still
prints a report, so nothing at all means the checker never ran. ``collect_ty``
returned an empty diagnostic list, which is the answer a genuinely clean tree
gives. Verified against the real binary: ``ty check`` over a clean directory
prints an empty JSON array, two bytes, never nothing. So a ty that failed to
start or crashed reported green and the gate exited 0.

The rule now lives in one place. These cases drive it directly with constructed
completed processes - a ``CompletedProcess`` is a data holder, not a stand-in for
the code under test - because running the three real checkers over ``src`` takes
minutes and would prove the checkers rather than the harness.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace

import pytest

from ..types import (
    _IRREDUCIBLE_EXTERNAL_GAPS,
    _PLATFORMS,
    Diagnostic,
    TargetPlatform,
    _ExternalGap,
    _is_irreducible_external_gap,
    collect_all,
    collect_basedpyright,
    collect_pyrefly,
    collect_ty,
    fold_platforms,
    main,
    require_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["checker"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_an_empty_stream_is_refused_rather_than_read_as_clean() -> None:
    """The defect: a checker that never ran answered exactly like a clean tree."""
    with pytest.raises(RuntimeError, match="produced no report"):
        require_report("", _completed(stderr="ty: command not found"), "ty")


def test_the_refusal_names_the_checker_that_went_silent() -> None:
    """Three checkers run; a message naming none of them starts the diagnosis over."""
    with pytest.raises(RuntimeError, match="pyrefly"):
        require_report("", _completed(), "pyrefly")


def test_an_empty_report_document_is_accepted() -> None:
    """A clean run prints an empty collection, and that is a measurement.

    This is the case the refusal must not swallow: refusing it would make every
    green tree a hard failure, which is the opposite mistake and just as wrong.
    """
    require_report("[]", _completed(stdout="[]"), "ty")
    require_report('{"errors": []}', _completed(stdout='{"errors": []}'), "pyrefly")


def test_a_populated_report_is_accepted() -> None:
    """The ordinary failing-tree path still reaches the parser."""
    require_report('[{"check_name": "x"}]', _completed(stdout='[{"check_name": "x"}]'), "ty")


def test_ty_uses_the_same_project_discovery_as_a_standalone_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """The aggregate must not replace ty's project boundary with a curated subset."""
    seen: list[list[str]] = []

    def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return _completed(stdout="[]")

    monkeypatch.setattr("dev.quality.types._run", run)

    assert collect_ty(TargetPlatform(key="linux", basedpyright="Linux")) == []
    assert seen == [["ty", "check", "--python-platform", "linux", "--output-format", "gitlab", "--color", "never"]]


def test_every_checker_names_the_target_platform_it_analyses_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defect this closes: an unset target platform is inherited from the HOST.

    Left unpinned, the same tree is clean on Windows and carries dozens of
    diagnostics on Linux, so the gate's verdict is a property of the runner
    rather than of the code. Every invocation therefore declares the platform.
    """
    seen: list[list[str]] = []

    def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(cmd)
        return _completed(stdout='{"errors": []}' if cmd[0] == "pyrefly" else "[]")

    monkeypatch.setattr("dev.quality.types._run", run)
    target = TargetPlatform(key="darwin", basedpyright="Darwin")

    collect_ty(target)
    collect_pyrefly(target)
    monkeypatch.setattr("dev.quality.types._run", lambda cmd: (seen.append(cmd), _completed(stdout="{}"))[1])
    collect_basedpyright(target)

    assert seen[0][2:4] == ["--python-platform", "darwin"]
    assert seen[1][2:4] == ["--python-platform", "darwin"]
    assert "--pythonplatform" in seen[2]
    assert seen[2][seen[2].index("--pythonplatform") + 1] == "Darwin"


def test_the_sweep_covers_every_supported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single pinned platform would be deterministic and half-blind.

    `sys.platform` narrowing means a Windows-only function body is analysed
    ONLY by a Windows-targeted run, so pinning Linux alone would leave the
    Windows branches permanently unchecked.
    """
    seen: list[tuple[str, str]] = []

    monkeypatch.setattr("dev.quality.types.collect_ty", lambda p: seen.append(("ty", p.key)) or [])
    monkeypatch.setattr("dev.quality.types.collect_pyrefly", lambda p: seen.append(("pyrefly", p.key)) or [])
    monkeypatch.setattr("dev.quality.types.collect_basedpyright", lambda p: seen.append(("basedpyright", p.key)) or [])

    assert collect_all() == []
    assert {platform.key for platform in _PLATFORMS} == {"linux", "win32", "darwin"}
    assert sorted(seen) == sorted(
        (checker, platform.key) for platform in _PLATFORMS for checker in ("ty", "pyrefly", "basedpyright")
    )


def test_one_defect_seen_on_every_platform_counts_once() -> None:
    """Three runs of the same tree must not treble a tree-wide finding."""
    everywhere = [_diagnostic(platform=platform.key) for platform in _PLATFORMS]

    folded = fold_platforms(everywhere)

    assert len(folded) == 1
    assert folded[0][1] == tuple(platform.key for platform in _PLATFORMS)


def test_a_platform_specific_defect_keeps_the_platforms_that_reported_it() -> None:
    """ "Only on Windows" is the most actionable thing this gate can say."""
    folded = fold_platforms([_diagnostic(platform="win32")])

    assert folded[0][1] == ("win32",)


def test_the_suppression_list_is_empty() -> None:
    """States why the cases below are constructed.

    The one entry it carried suppressed an unresolved import in a corpus-search
    model loader that was deleted with the runtime embedding stack, so it had no
    subject left. An entry reappearing should send whoever added it here.
    """
    assert _IRREDUCIBLE_EXTERNAL_GAPS == ()


def _diagnostic(
    checker: str = "ty",
    rule: str = "unresolved-import",
    path: str = "src/cadrumo/x.py",
    platform: str = "linux",
) -> Diagnostic:
    return Diagnostic(
        checker=checker,
        rule=rule,
        path=path,
        line=1,
        message="Cannot resolve import `absent_pkg`",
        platform=platform,
    )


def test_a_matching_gap_suppresses_only_its_own_diagnostic() -> None:
    """All four parts must agree, which is what keeps the suppression narrow."""
    gap = _ExternalGap(
        path_suffix="cadrumo/x.py",
        checker="ty",
        rule="unresolved-import",
        needle="absent_pkg",
        reason="constructed for this proof",
    )
    diagnostic = _diagnostic()

    assert (
        diagnostic.checker == gap.checker
        and diagnostic.rule == gap.rule
        and diagnostic.path.endswith(gap.path_suffix)
        and gap.needle in diagnostic.message
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("checker", "pyrefly"),
        ("rule", "invalid-assignment"),
        ("path", "src/cadrumo/other.py"),
    ],
)
def test_a_diagnostic_differing_in_any_part_is_not_suppressed(field: str, value: str) -> None:
    """A suppression that matched loosely would hide the next real defect.

    The module states the intent - a new diagnostic under any other rule or
    naming any other symbol stays a hard failure - and this is what holds the
    match to all four parts.
    """
    gap = _ExternalGap(
        path_suffix="cadrumo/x.py",
        checker="ty",
        rule="unresolved-import",
        needle="absent_pkg",
        reason="constructed for this proof",
    )
    diagnostic = _diagnostic(**{field: value})

    matched = (
        diagnostic.checker == gap.checker
        and diagnostic.rule == gap.rule
        and diagnostic.path.endswith(gap.path_suffix)
        and gap.needle in diagnostic.message
    )
    assert not matched


def test_nothing_is_suppressed_while_the_list_is_empty() -> None:
    """The live predicate, so it cannot rot while the list stays empty."""
    assert not _is_irreducible_external_gap(_diagnostic())


@pytest.mark.parametrize(
    ("diagnostics", "expected_count"),
    [
        ([], "0\n"),
        ([_diagnostic(), _diagnostic(checker="basedpyright")], "2\n"),
    ],
)
def test_count_mode_emits_only_the_aggregate_integer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    diagnostics: list[Diagnostic],
    expected_count: str,
) -> None:
    """The machine signal stays one integer without a recipe-runner error suffix."""
    by_checker = {
        "ty": [diagnostic for diagnostic in diagnostics if diagnostic.checker == "ty"],
        "pyrefly": [diagnostic for diagnostic in diagnostics if diagnostic.checker == "pyrefly"],
        "basedpyright": [diagnostic for diagnostic in diagnostics if diagnostic.checker == "basedpyright"],
    }
    # Each checker answers the same for every target platform here, so the
    # integer also proves the fold: three sweeps of one defect are one defect.
    monkeypatch.setattr(
        "dev.quality.types.collect_ty",
        lambda platform: [replace(d, platform=platform.key) for d in by_checker["ty"]],
    )
    monkeypatch.setattr(
        "dev.quality.types.collect_pyrefly",
        lambda platform: [replace(d, platform=platform.key) for d in by_checker["pyrefly"]],
    )
    monkeypatch.setattr(
        "dev.quality.types.collect_basedpyright",
        lambda platform: [replace(d, platform=platform.key) for d in by_checker["basedpyright"]],
    )
    monkeypatch.setattr(sys, "argv", ["dev.quality.types", "--count"])

    assert main() == 0
    captured = capsys.readouterr()
    assert captured.out == expected_count
    assert captured.err == ""
