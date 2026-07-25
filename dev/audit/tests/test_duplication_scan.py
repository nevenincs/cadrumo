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

from dev.audit.duplication import (
    DuplicationOutcome,
    run_duplication_scan,
)
from dev.audit.report import Status, audit_duplication

from ._duplication_support import (
    _REPO_ROOT,
    _recorded_dispositions,
    _uncovered_groups,
)

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


def test_real_production_tree_scan_reports_measured_clones() -> None:
    """The real production tree carries clones and must report them as AMBER debt.

    This is the assertion the old runner inverted. The count is advisory and
    drifts as code lands, so this pins the honest SHAPE (clones observed, with a
    real measured count over a real analysed corpus) rather than a brittle
    literal.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT)

    assert result.outcome is DuplicationOutcome.CLONES
    assert result.is_green is False, "the production tree carries clones; green here is the false-green defect"
    assert result.clone_count > 0
    assert result.files_analyzed > 1000, (
        "the production tree carries >1000 source files; a small count means a partial scan"
    )
    assert result.groups, "a clone verdict must carry the clone records backing it"
    assert result.duplicated_pct


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


def test_health_report_duplication_dimension_is_amber_with_a_measured_count() -> None:
    """End-to-end: the health dashboard must not render the false green.

    The tree carries clones, so the honest verdict is AMBER carrying the count.
    Per the advisory clone-count policy this dimension is never RED on clones.
    """
    _require_npx()
    dimension = audit_duplication(_REPO_ROOT)

    assert dimension.status is not Status.GREEN, "the production tree carries clones; GREEN is the reported lie"
    assert dimension.status is Status.AMBER
    assert "clone cluster(s)" in dimension.headline


def test_every_observed_clone_group_has_a_recorded_disposition() -> None:
    """Every clone group the live scan observes must carry a recorded disposition.

    The invariant -- every observed clone group carries an explicit recorded
    disposition -- had no gate anywhere in the tree; the claim could not be
    checked and could rot silently as consolidations landed. This asserts
    COVERAGE, never a COUNT of clones: the clone count is advisory debt by
    design, so a clone-count assertion would fight that and go red on every
    genuine consolidation. The record is a superset by
    design -- a group disappearing is progress, not a gate failure -- while a
    NEW, unrecorded group is exactly what this gate exists to catch.

    Coverage is measured per file-set as a MULTISET, not a set. A self-clone
    names one file twice, so its file-set collapses to a single path; under a
    plain set membership test any second, entirely unrelated clone group inside
    that same file matched the first one's entry and passed unseen. Seven of
    the recorded groups are self-clones, so seven files were unguarded against
    a new intra-file clone. Comparing how MANY groups each file-set carries
    closes that hole while still keying on paths rather than line spans, which
    drift on every unrelated edit.
    """
    _require_npx()
    result = run_duplication_scan(_REPO_ROOT)
    assert result.outcome is DuplicationOutcome.CLONES, (
        "the production tree is expected to carry advisory clone debt; "
        "if this ever goes clean, update this test rather than deleting it"
    )

    uncovered = [group.render() for group in _uncovered_groups(result.groups, _recorded_dispositions())]

    assert not uncovered, (
        "the live scan observed clone group(s) with no recorded disposition in "
        f"duplication_dispositions.toml:\n\n{chr(10).join(uncovered)}"
    )
