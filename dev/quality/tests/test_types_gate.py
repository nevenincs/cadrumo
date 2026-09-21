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
import threading
from dataclasses import replace

import pytest

from ..types import (
    _IRREDUCIBLE_EXTERNAL_GAPS,
    _PLATFORMS,
    Diagnostic,
    TargetPlatform,
    _describe_stream,
    _ExternalGap,
    _is_irreducible_external_gap,
    collect_all,
    collect_basedpyright,
    collect_pyrefly,
    collect_ty,
    fold_platforms,
    main,
    platform_pin_failures,
    read_pyproject,
    require_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["checker"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_an_empty_stream_is_refused_rather_than_read_as_clean() -> None:
    """The defect: a checker that never ran answered exactly like a clean tree."""
    with pytest.raises(RuntimeError, match=r"produced no report.*exit code -9"):
        require_report("", _completed(stderr="ty: command not found", returncode=-9), "ty")


def test_the_refusal_carries_the_stderr_rather_than_pointing_at_it() -> None:
    """A message that says "see the captured stderr above" is worth what is above it.

    Measured, not hypothetical: a CI run failed with ``ty[darwin] produced no
    report; see the captured stderr above`` and the whole step held nothing
    between the setup group and the traceback. The text it referred the reader
    to did not exist, and the diagnosis needed a second run to correlate
    against. The evidence has to travel inside the exception.
    """
    with pytest.raises(RuntimeError) as raised:
        require_report("", _completed(stderr="ty: unknown platform darwin", returncode=2), "ty[darwin]")

    message = str(raised.value)
    assert "ty: unknown platform darwin" in message
    assert "exit code 2" in message
    assert "above" not in message, "the message must carry its evidence, not point out of itself"


def test_an_absent_stream_is_named_as_empty_rather_than_omitted() -> None:
    """Silence and a lost capture are different failures and must read differently.

    This is the case that actually happened: the checker exited having written
    nothing to either stream. A message that simply omits an empty stream lets
    a reader assume the harness dropped it, which sends the diagnosis at the
    harness instead of at the checker.
    """
    with pytest.raises(RuntimeError) as raised:
        require_report("", _completed(returncode=1), "ty[darwin]")

    message = str(raised.value)
    assert "stdout empty" in message
    assert "stderr empty" in message


def test_a_long_stream_is_excerpted_with_its_full_length_stated() -> None:
    """A checker dying mid-dump must not bury the rest of the message."""
    described = _describe_stream("x" * 5000, "stderr")

    assert described.startswith("stderr (5000 chars, first 2000): ")
    assert len(described) < 5000


def test_a_stream_python_never_captured_is_distinguished_from_an_empty_one() -> None:
    """``TimeoutExpired`` can carry ``None`` streams, which is a third state."""
    assert _describe_stream(None, "stdout") == "stdout not captured"
    assert _describe_stream("", "stdout") == "stdout empty"
    assert _describe_stream(b"bytes arrive from a timed-out child", "stderr").endswith("child")


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
    # A set, because the nine runs overlap; the union is sorted before it is
    # reported, so completion order cannot reach the verdict.
    assert sorted(seen) == sorted(
        (checker, platform.key) for platform in _PLATFORMS for checker in ("ty", "pyrefly", "basedpyright")
    )


def test_checker_families_do_not_overlap_platform_sweeps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep one process per checker family resident at a time.

    The old nine-future schedule allowed a fast family worker to pick up a
    second platform while another worker still held that family's first
    platform. The test releases the other two first-platform calls while the
    ``ty`` call remains blocked; that schedule necessarily overlaps ``ty``
    under the old implementation, but not under the family-serial sweep.
    """
    started = {name: threading.Event() for name in ("ty", "pyrefly", "basedpyright")}
    release = {name: threading.Event() for name in ("ty", "pyrefly", "basedpyright")}
    active = {name: 0 for name in started}
    maximum = {name: 0 for name in started}
    overlap = threading.Event()
    lock = threading.Lock()

    def fake_collector(name: str):
        def collect(platform: TargetPlatform) -> list[Diagnostic]:
            with lock:
                active[name] += 1
                maximum[name] = max(maximum[name], active[name])
                if active[name] > 1:
                    overlap.set()
            try:
                if platform.key == "linux":
                    started[name].set()
                    assert release[name].wait(timeout=5), f"{name} did not receive its release"
                return []
            finally:
                with lock:
                    active[name] -= 1

        return collect

    monkeypatch.setattr("dev.quality.types.collect_ty", fake_collector("ty"))
    monkeypatch.setattr("dev.quality.types.collect_pyrefly", fake_collector("pyrefly"))
    monkeypatch.setattr("dev.quality.types.collect_basedpyright", fake_collector("basedpyright"))

    worker = threading.Thread(target=collect_all)
    worker.start()
    overlap_seen = False
    try:
        assert all(event.wait(timeout=5) for event in started.values())
        release["pyrefly"].set()
        release["basedpyright"].set()
        # Under the old global queue, one of those freed workers picked up
        # ty's next platform while ty/linux was still resident. The new
        # family task cannot do that. Keep this wait bounded before releasing
        # ty so a broken schedule fails as an assertion rather than hanging.
        overlap_seen = overlap.wait(timeout=1)
    finally:
        for event in release.values():
            event.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert not overlap_seen
    assert maximum == {name: 1 for name in started}


def test_the_live_configuration_pins_every_checker_to_one_swept_platform() -> None:
    """The pin is what keeps a bare `ty check` from answering about the host."""
    assert platform_pin_failures(read_pyproject()) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("not-a-platform", "is not a platform this project sweeps"),
        ("Linux", "is not a platform this project sweeps"),
        (None, "would inherit the host platform"),
    ],
)
def test_a_mistyped_or_missing_pin_is_refused(value: str | None, expected: str) -> None:
    """The teeth. ty itself accepts a nonsense platform, so this is the only refusal.

    `python-platform = "not-a-platform"` does not raise from ty: it analyses as
    though the target were simply not Windows and reports a plausible, green
    answer for a platform nobody chose. A silent degradation of the pin is the
    exact failure the pin exists to remove, so it fails here instead.
    `"Linux"` is the near-miss that matters most - it is basedpyright's correct
    spelling and ty's wrong one.
    """
    environment = {} if value is None else {"python-platform": value}
    document = {
        "tool": {
            "ty": {"environment": environment},
            "pyrefly": {"python_platform": "linux"},
            "mypy": {"platform": "linux"},
            "basedpyright": {"pythonPlatform": "Linux"},
        }
    }

    failures = platform_pin_failures(document)

    assert len(failures) == 1
    assert "[tool.ty.environment] python-platform" in failures[0]
    assert expected in failures[0]


def test_checkers_pinned_to_different_platforms_are_refused() -> None:
    """Four pins that disagree are four verdicts, and none of them is the tree's."""
    document = {
        "tool": {
            "ty": {"environment": {"python-platform": "linux"}},
            "pyrefly": {"python_platform": "win32"},
            "mypy": {"platform": "linux"},
            "basedpyright": {"pythonPlatform": "Linux"},
        }
    }

    failures = platform_pin_failures(document)

    assert failures == [
        "the checkers declare different target platforms: "
        "[tool.basedpyright] pythonPlatform -> linux, [tool.mypy] platform -> linux, "
        "[tool.pyrefly] python_platform -> win32, [tool.ty.environment] python-platform -> linux"
    ]


def test_the_gate_refuses_to_measure_when_the_pin_cannot_be_trusted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown target platform is not a tree to report on; no checker runs."""

    def unreachable(platform: TargetPlatform) -> list[Diagnostic]:  # pragma: no cover - must not run
        raise AssertionError("a checker ran although the target platform was unusable")

    monkeypatch.setattr("dev.quality.types.read_pyproject", dict)
    for name in ("collect_ty", "collect_pyrefly", "collect_basedpyright"):
        monkeypatch.setattr(f"dev.quality.types.{name}", unreachable)
    monkeypatch.setattr(sys, "argv", ["dev.quality.types", "--count"])

    assert main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "would inherit the host platform" in captured.err


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
