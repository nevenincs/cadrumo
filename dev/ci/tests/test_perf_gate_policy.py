"""Structural gate for the performance-benchmark placement policy.

Perf acceptance gates assert PROCESS CPU-TIME (load-immune on the shared
two-machine fleet) and print wall-clock as advisory only; they run exactly
once — explicitly enrolled in the dispatch-only ci-full lane — and never in a
per-push lane, where co-resident jobs make wall numbers meaningless and extra
minutes burn the ten-minute wall.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPO_ROOT: Final = Path(__file__).resolve().parents[3]
_WORKFLOWS: Final = _REPO_ROOT / ".github" / "workflows"
_BENCHMARK_TEST: Final = _REPO_ROOT / "dev" / "packaging" / "tests" / "test_serving_path_benchmark.py"


def test_benchmark_module_is_perf_marked_and_out_of_default_selectors() -> None:
    """The benchmark carries perf + integration + serial (plus its hex label).

    The taxonomy hook demands exactly one execution marker, so ``perf`` rides
    alongside ``integration``; ``serial`` is what keeps the file out of every
    ``integration and not serial`` selector (the per-push dev gates and the
    bulk integration pass), and the broad serial passes carry ``not perf``.
    """
    source = _BENCHMARK_TEST.read_text(encoding="utf-8")
    assert "pytest.mark.perf" in source
    assert "pytest.mark.integration" in source
    assert "pytest.mark.serial" in source
    assert "pytest.mark.unit" not in source


def test_broad_serial_passes_exclude_the_perf_gate() -> None:
    """Every repo-wide 'integration and serial' pass refuses perf tests.

    The file-scoped installed-oracles pass (pinned to
    ``test_installed_oracles.py``) cannot collect the benchmark and stays
    as-is; the two broad serial passes must carry ``not perf``.
    """
    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")
    # Asserted by intent rather than by an exact expression. The literal form
    # broke when an unrelated change added "and not os_keychain" to these lanes,
    # which excluded MORE than the policy demands and so satisfied it -- the
    # test failed on a compliant justfile. Any broad serial pass must exclude
    # perf; further exclusions are somebody else's policy and not this gate's.
    broad = [
        line.strip()
        for line in justfile.splitlines()
        if '-m "integration and serial' in line and "test_installed_oracles.py" not in line
    ]
    assert broad, "no broad serial pass found; this gate would be measuring nothing"
    for line in broad:
        assert "not perf" in line, f"broad serial pass does not exclude the benchmark: {line}"


def test_perf_marker_is_registered() -> None:
    """strict-markers demands registration; the marker documents its policy."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"perf: [^"]+"', pyproject)


def test_per_push_lanes_never_collect_the_perf_gate() -> None:
    """No per-push workflow invokes the perf marker or the benchmark file."""
    for workflow in ("ci.yml", "packaging-quick.yml", "packaging-smoke.yml"):
        surface = (_WORKFLOWS / workflow).read_text(encoding="utf-8")
        assert "-m perf" not in surface, workflow
        assert "test_serving_path_benchmark" not in surface, workflow


def test_ci_full_enrolls_the_perf_gate_explicitly() -> None:
    """The dispatch-only full lane runs the perf gate serially with -s.

    ``-s`` surfaces the advisory wall-clock lines in the job log; ``-n0``
    keeps the warm in-process runtime unshared.
    """
    surface = (_WORKFLOWS / "ci-full.yml").read_text(encoding="utf-8")
    match = re.search(r"pytest[^\n]*-m perf[^\n]*", surface)
    assert match, "ci-full.yml must enroll the perf gate"
    invocation = match.group(0)
    assert "-n0" in invocation
    assert "-s" in invocation
    assert "dev/packaging/tests/test_serving_path_benchmark.py" in invocation
