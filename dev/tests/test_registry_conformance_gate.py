"""CI gate: ``conformance closure --offline --check`` is exercised through a real subprocess.

The gate invokes ``python -m dev.registry.conformance closure`` as a separate
process so the CI lane sees the exit code the verb actually returns, rather
than relying on a developer to run it by hand and read the rows.

Two proofs are required, because a gate never observed failing is not a gate:

Report path
    ``closure --offline`` exits 0 and emits one ``closure`` summary row plus a
    ``closure_row`` per bundled revision. The summary is asserted to carry a
    realistic revision population and to state ``release_eligible`` in the
    same breath as ``satisfied_revisions``/``refused_revisions``, so an empty
    or errored run can never read as a report.

Check path
    ``closure --offline --check`` exits 1 whenever the summary row says
    ``release_eligible=false`` and 0 whenever it says ``release_eligible=true``.
    The two invocations are compared against each other in the same run, so
    the gate is proven to block on exactly the predicate it prints, never on
    an unrelated failure. ``--offline`` is the mode that marks the live-proof
    limbs ``unmeasured``; an unmeasured limb is a refusal, never a pass, so
    an offline check can detect a regression but cannot approve a release.

Lane
    Marked ``integration`` (subprocess; no ``lru_cache`` sharing across
    processes). The composer walks every revision in the bundled registry and
    the real run takes minutes, beyond the per-push budget.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT: Final[Path] = REPO_ROOT
_SUMMARY_PATTERN: Final = re.compile(
    r"^closure .*\brelease_eligible=(?P<eligible>true|false)\b.*\brevisions=(?P<revisions>\d+)\b",
    re.MULTILINE,
)
_MINIMUM_REALISTIC_REVISIONS: Final[int] = 2


def _run_closure(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dev.registry.conformance", "closure", "--offline", *extra],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        check=False,
    )


def _summary(output: str) -> tuple[bool, int]:
    match = _SUMMARY_PATTERN.search(output)
    if match is None:
        pytest.fail("closure output carried no 'closure … release_eligible=… revisions=…' summary row:\n" + output)
    return bool(match.group("eligible") == "true"), int(match.group("revisions"))


@pytest.mark.timeout(900)
def test_closure_report_exits_zero_and_measures_the_registry() -> None:
    result = _run_closure()

    assert result.returncode == 0, f"closure --offline exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    _eligible, revisions = _summary(result.stdout)
    assert revisions >= _MINIMUM_REALISTIC_REVISIONS, (
        f"closure composed only {revisions} revision row(s); the run was not representative of the bundled registry"
    )
    assert result.stdout.count("\nclosure_row ") + result.stdout.startswith("closure_row ") == revisions, (
        "closure_row count disagrees with the summary's revisions figure:\n" + result.stdout
    )


@pytest.mark.timeout(900)
def test_closure_check_blocks_on_exactly_the_printed_predicate() -> None:
    report = _run_closure()
    checked = _run_closure("--check")

    eligible, _revisions = _summary(report.stdout)
    assert _summary(checked.stdout) == _summary(report.stdout), (
        "the checked run printed a different summary than the report run; the gate is not deterministic"
    )
    expected = 0 if eligible else 1
    assert checked.returncode == expected, (
        f"closure --offline --check exited {checked.returncode} while the summary row says "
        f"release_eligible={'true' if eligible else 'false'}:\n{checked.stdout}\n{checked.stderr}"
    )
