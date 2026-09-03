"""The duplication gates that run a real jscpd scan over the tree.

These spawn the vendored scanner through npx and read what it actually reports,
so they are ``integration``: they need node on PATH and they walk the whole
source tree. The instrument-honesty gates live here because a scan that reports
zero clones while clones exist is the failure they exist to catch, and only a
real scan can prove it.

The parsing and coverage-arithmetic checks are in ``test_duplication``; the
shared record readers are in ``_duplication_support``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from ..duplication import (
    DuplicationOutcome,
    run_duplication_scan,
)
from ..report import Status, audit_duplication
from ._duplication_support import _REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _require_npx() -> None:
    """Assert the real npx binary is present for an integration test.

    The sanctioned convention for external-binary integration tests in this
    repo is to assert the tool is present, not to self-skip when it is absent
    (see ``dev/release/tests/test_justfile_release_guidance.py`` and
    ``dev/packaging/tests/test_smoke_split_install_sequence.py``). ``skipif`` is
    forbidden by ``test_no_skip_xfail`` for tests outside the source tree.
    """
    assert shutil.which("npx") is not None, "npx is required to run the real jscpd duplication scan"


def test_real_clean_subtree_scan_observes_zero() -> None:
    """A real zero-clone jscpd run over a real clone-free tree is observed_zero.

    ``dev/audit`` is genuinely clone-free, so this is the only honest route to
    the green state: a real subprocess that really looked at real files.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, source_root=Path("dev/audit"))

    assert result.outcome is DuplicationOutcome.OBSERVED_ZERO
    assert result.is_green is True
    assert result.clone_count == 0
    assert result.files_analyzed > 0, "a green verdict must prove files were analysed"


def test_real_bad_source_path_is_unavailable_not_green() -> None:
    """A real scan of a path that matches nothing must refuse to claim cleanliness."""
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, source_root=Path("src/cadrumo/no-such-directory"))

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False


def test_real_timeout_is_unavailable_not_green() -> None:
    """A real jscpd run cut off by the timeout must report unavailable."""
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT, timeout=0.001)

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
    """
    result = run_duplication_scan(_REPO_ROOT, which=lambda _name: sys.executable)

    assert result.outcome is DuplicationOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "exited" in result.reason


def test_real_failure_diagnostic_reaches_the_reason() -> None:
    """The failed process's own diagnostic must survive into the reason.

    ``run_duplication_scan`` builds the unavailable reason from the failed
    process's stderr, falling back to stdout and then to a fixed
    ``no diagnostic output`` sentinel. Asserting only that the reason says
    ``exited`` cannot tell those apart: drop the stderr capture entirely and the
    reason still reads ``jscpd exited 2: no diagnostic output``, so the amber
    verdict stays correct while the evidence explaining it silently vanishes.

    This pins the evidence rather than the verdict. The tail is a real
    interpreter's own error text, which varies by version and locale, so the
    assertion is structural -- a non-empty tail that is not the fallback
    sentinel -- never the literal message.
    """
    result = run_duplication_scan(_REPO_ROOT, which=lambda _name: sys.executable)

    _, _, tail = result.reason.partition(": ")

    assert tail, f"the reason carried no diagnostic tail at all: {result.reason!r}"
    assert tail != "no diagnostic output", (
        f"the failed process wrote a diagnostic but it did not reach the reason: {result.reason!r}"
    )


def test_health_report_duplication_dimension_reflects_the_live_scan() -> None:
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
    result = run_duplication_scan(_REPO_ROOT)
    dimension = audit_duplication(_REPO_ROOT)

    assert result.outcome is not DuplicationOutcome.UNAVAILABLE, result.reason
    assert result.files_analyzed > 0, "neither verdict is honest without proof of inspection"

    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        assert dimension.status is Status.GREEN
        assert "no clones found" in dimension.headline
    else:
        assert dimension.status is Status.AMBER
        assert str(result.clone_count) in dimension.headline
        assert "no clones found" not in dimension.headline
