"""CI gate: ``conformance audit --check`` exit code is tested via real subprocess.

This gate invokes ``python -m dev.registry.conformance audit --check`` as a
separate process so the CI lane sees a non-zero exit when the committed
baseline has regressed — rather than relying on a developer to run the verb
by hand and notice.

Two proofs are required, because a gate never observed failing is not a gate.
A green run alone cannot distinguish a check that is working from one that has
stopped checking — a broken invocation, a swallowed exit code, or a baseline
comparison that reads nothing all produce the same passing result. Only a run
that is made to fail, on a regression seeded for the purpose, shows the gate
still has teeth:

Green path
    The real registry at HEAD, compared against the committed baseline,
    produces exit 0. The output is additionally asserted to have measured a
    realistic population (non-vacuity), so an empty or errored run can never
    read as a pass.

Red path (seeded regression)
    A copy of the committed baseline with ``floors.composed_revisions`` raised
    to an impossible value makes the audit exit 1 and name
    ``composed_revisions`` in its violation output. The seeded file is
    temporary and never touches the committed baseline.

Lane
    Marked ``integration`` (subprocess; no ``lru_cache`` sharing across
    processes). Enrolled in ``ci-full.yml`` — the manual-dispatch 120-minute
    lane — because the composer walks every revision in the bundled registry
    and the real run takes minutes, beyond the per-push budget.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from .._paths import REPO_ROOT
from ..registry.conformance.manager import baseline_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = REPO_ROOT
_COMMITTED_FLOORS: Final[dict[str, int]] = json.loads(baseline_path().read_text(encoding="utf-8"))["floors"]
_COMPOSED_REVISIONS_FLOOR_PATTERN: Final = re.compile(r"floor population=composed_revisions current=(\d+)")


@pytest.mark.timeout(600)
def test_conformance_audit_passes_committed_baseline() -> None:
    """``audit --check`` exits 0 against the real registry at HEAD.

    Also asserts that the run examined at least the committed floor's worth of
    revisions, so a vacuous or errored run cannot read as a pass.
    """
    result = subprocess.run(
        [sys.executable, "-m", "dev.registry.conformance", "audit", "--check"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    _assert_realistic_population(result.stdout)
    assert result.returncode == 0, (
        "conformance audit --check exited non-zero on the committed baseline "
        f"(unexpected regression at HEAD):\n{result.stdout}\n{result.stderr}"
    )


@pytest.mark.timeout(600)
def test_conformance_audit_fails_seeded_floor_regression(tmp_path: Path) -> None:
    """A baseline with an impossible population floor makes the gate exit 1.

    The seeded file is a copy of the committed baseline with
    ``floors.composed_revisions`` raised by 99 999 — a value the real
    registry can never satisfy. The subprocess must exit 1 AND name
    ``composed_revisions`` in its output, proving both directions of the
    vacuity check.
    """
    raw = json.loads(baseline_path().read_text(encoding="utf-8"))
    raw["floors"]["composed_revisions"] = _COMMITTED_FLOORS["composed_revisions"] + 99_999
    seeded = tmp_path / "seeded-baseline.json"
    seeded.write_text(json.dumps(raw), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dev.registry.conformance",
            "audit",
            "--check",
            "--baseline",
            str(seeded),
        ],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 1, (
        f"seeded floor regression did NOT trigger exit 1 (exit={result.returncode}); "
        "the gate cannot detect a shrunken measurement population:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "composed_revisions" in result.stdout, (
        "violation output does not name 'composed_revisions'; "
        "the gate may not be reporting the failing floor:\n"
        f"{result.stdout}"
    )


def _assert_realistic_population(output: str) -> None:
    """Fail when the audit examined fewer revisions than the committed floor.

    Parses the ``floor population=composed_revisions current=N`` line that
    ``render_audit`` always emits and compares ``N`` against the committed
    baseline's own floor. A missing line means the run produced no audit
    output at all (vacuous or errored).
    """
    match = _COMPOSED_REVISIONS_FLOOR_PATTERN.search(output)
    if match is None:
        pytest.fail(
            "audit output contained no 'floor population=composed_revisions current=' line; "
            "the run may have been vacuous or errored:\n" + output
        )
    current = int(match.group(1))
    required = _COMMITTED_FLOORS["composed_revisions"]
    assert current >= required, (
        f"audit examined {current} composed revisions, below the committed floor of {required}; "
        "the run was not representative of the full registry"
    )
