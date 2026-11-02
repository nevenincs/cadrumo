"""The duplication gates that run a real jscpd scan over the tree.

These spawn the vendored scanner through npx and read what it actually reports,
so they are ``integration``: they need node on PATH and they walk the whole
source tree. The instrument-honesty gates live here because a scan that reports
zero clones while clones exist is the failure they exist to catch, and only a
real scan can prove it.

The parsing and actionability checks are in ``test_duplication``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from .. import report
from ..duplication import (
    DuplicationOutcome,
    DuplicationResult,
    ceiling_verdict,
    run_duplication_scan,
)
from ..report import Status, audit_duplication

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _require_npx() -> None:
    """Assert the real npx binary is present for an integration test.

    The sanctioned convention for external-binary integration tests in this
    repo is to assert the tool is present, not to self-skip when it is absent
    (see ``dev/release/tests/test_justfile_release_guidance.py`` and
    ``dev/packaging/tests/test_smoke_split_install_sequence.py``). The project
    forbids ``skipif`` as a shortcut.
    """
    assert shutil.which("npx") is not None, "npx is required to run the real jscpd duplication scan"


def test_real_clean_subtree_scan_observes_zero() -> None:
    """A real zero-clone jscpd run over a real clone-free tree is observed_zero.

    The security runner is a real, clone-free source file. The complete audit
    subtree also contains shared scanner idioms, so it cannot witness zero.
    This still requires a real subprocess to inspect nonempty source.
    """
    _require_npx()
    result = run_duplication_scan(REPO_ROOT, source_roots=(Path("dev/audit/security.py"),))

    assert result.outcome is DuplicationOutcome.OBSERVED_ZERO, result.headline()
    assert result.is_green is True
    assert result.clone_count == 0
    assert result.files_analyzed > 0, "a green verdict must prove files were analysed"


def test_a_missing_root_beside_a_real_one_is_unavailable_not_a_smaller_scope() -> None:
    """One lost package must not let the surviving roots pose as the whole scope.

    The real root alone observes zero (see above), so the unavailable verdict
    here is attributable to the missing root alone. A scan whose every root is
    missing fails through the same non-zero exit, so this one proof covers it.
    """
    _require_npx()
    result = run_duplication_scan(
        REPO_ROOT, source_roots=(Path("dev/audit/security.py"), Path("src/cadrumo/no-such-directory"))
    )

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False


def test_real_timeout_is_unavailable_not_green() -> None:
    """A real jscpd run cut off by the timeout must report unavailable."""
    _require_npx()
    result = run_duplication_scan(REPO_ROOT, timeout=0.001)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "timeout" in result.reason


def test_real_nonzero_exit_is_unavailable_not_green() -> None:
    """A real subprocess that exits non-zero must report unavailable.

    The failure CONDITION is forced through the injected ``which`` seam, not by
    patching global state: the resolver returns a real Python interpreter, so
    ``run_duplication_scan`` really launches ``<python> --yes jscpd@4.2.0 ...``,
    which the interpreter rejects and exits non-zero. A genuinely failing
    process is what is under test -- the parser is untouched.

    The failed process's own diagnostic must also survive into the reason.
    ``run_duplication_scan`` builds the unavailable reason from the failed
    process's stderr, falling back to stdout and then to a fixed
    ``no diagnostic output`` sentinel. Asserting only that the reason says
    ``exited`` cannot tell those apart: drop the stderr capture entirely and the
    reason still reads ``jscpd exited 2: no diagnostic output``, so the amber
    verdict stays correct while the evidence explaining it silently vanishes.

    The tail is a real interpreter's own error text, which varies by version
    and locale, so that assertion is structural -- a non-empty tail that is not
    the fallback sentinel -- never the literal message.
    """
    result = run_duplication_scan(REPO_ROOT, which=lambda _name: sys.executable)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "exited" in result.reason

    _, _, tail = result.reason.partition(": ")

    assert tail, f"the reason carried no diagnostic tail at all: {result.reason!r}"
    assert tail != "no diagnostic output", (
        f"the failed process wrote a diagnostic but it did not reach the reason: {result.reason!r}"
    )


def test_health_report_duplication_dimension_reflects_the_live_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """The D2 dimension must map the live scan's own outcome, never a fixed verdict.

    Deliberately NOT an assertion that the product tree is clone-free. That
    assertion is a campaign milestone: it was true when these gates were
    written and is false today, so restoring it would gate the dashboard on a
    frozen corpus count rather than on the mapping under test.

    What is invariant is the mapping. GREEN is reachable only through
    ``observed_zero``; clones are AMBER carrying the measured count as advisory
    debt; and neither verdict may be reached without the scan proving it
    inspected files. Whichever of the two the tree currently earns, the
    dimension must agree with the scan run beside it.
    """
    _require_npx()
    result = run_duplication_scan(REPO_ROOT)
    # The dimension delegates the measurement to this same runner; hand it the
    # scan just taken rather than launching a second identical whole-tree jscpd
    # run, and record that the delegation really asked for this tree.
    delegated: list[Path] = []

    def scanned(repo_root: Path) -> DuplicationResult:
        delegated.append(repo_root)
        return result

    monkeypatch.setattr(report, "run_duplication_scan", scanned)
    dimension = audit_duplication(REPO_ROOT)

    assert delegated == [REPO_ROOT]

    assert result.outcome is not DuplicationOutcome.UNAVAILABLE, result.reason
    assert result.files_analyzed > 0, "neither verdict is honest without proof of inspection"

    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        assert dimension.status is Status.GREEN
        assert "no clones found" in dimension.headline
    else:
        assert dimension.status is Status.AMBER
        assert str(result.clone_count) in dimension.headline
        assert "no clones found" not in dimension.headline


def _plant_test_tree(root: Path, *, copies: int) -> Path:
    tests = root / "pkg" / "tests"
    tests.mkdir(parents=True)
    body = "".join(
        f"    value_{i} = compute_{i}(argument) + offset_{i}\n    check(value_{i}, {i})\n" for i in range(20)
    )
    for index in range(copies):
        tests.joinpath(f"test_copy_{index}.py").write_text(f"def test_case(argument):\n{body}", encoding="utf-8")
    return root / "pkg"


def test_the_test_surface_scan_fails_a_planted_duplicate_over_the_ceiling(tmp_path: Path) -> None:
    """Copy-pasted test bodies exceed the ceiling and the verdict names it."""
    _require_npx()
    package = _plant_test_tree(tmp_path, copies=2)

    result = run_duplication_scan(tmp_path, source_roots=(package.relative_to(tmp_path),), tests=True)

    verdict = ceiling_verdict(result)
    assert result.outcome is DuplicationOutcome.CLONES, result.headline()
    assert verdict is not None
    assert "exceeds" in verdict


def test_the_test_surface_scan_passes_clean_tests_and_ignores_production_clones(tmp_path: Path) -> None:
    """A single test copy passes, and cloned production modules are outside the test scope."""
    _require_npx()
    package = _plant_test_tree(tmp_path, copies=1)
    source = package.joinpath("tests", "test_copy_0.py").read_text(encoding="utf-8")
    for name in ("one.py", "two.py"):
        package.joinpath(name).write_text(source, encoding="utf-8")

    result = run_duplication_scan(tmp_path, source_roots=(package.relative_to(tmp_path),), tests=True)

    assert result.outcome is DuplicationOutcome.OBSERVED_ZERO, result.headline()
    assert result.files_analyzed == 1
    assert ceiling_verdict(result) is None


def test_an_unmeasured_test_surface_breaks_the_ceiling() -> None:
    """An unavailable scan cannot prove the percentage, so it fails the ceiling check."""
    assert ceiling_verdict(DuplicationResult.unavailable("npx was not found on PATH")) is not None
