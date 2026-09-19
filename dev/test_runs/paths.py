"""Canonical paths for date-partitioned development run output.

Run output is transient by construction: one invocation writes a directory here,
nothing reads it back, and every base below is reclaimed. The word "evidence"
does not appear in this module's vocabulary on purpose -- a finding that must
outlive its run belongs in durable evidence, not in a path under ``.logs``.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dev._paths import REPO_ROOT

LOGS_STEM = ".logs"
"""The one directory name every run family lives under, whatever the base."""

TEST_RUNS_FAMILY = "test-runs"
"""The family a pytest controller invocation writes, and the only one with an owner."""


def run_log_bases() -> tuple[Path, ...]:
    """Return every base directory that can hold a ``.logs`` run family.

    Two bases, not one, and the second is why this function exists. Repository
    tooling -- the audit report, the lane runner, the edition migration -- passes
    its own checkout, so those families land under the worktree. A pytest
    controller does not: ``conftest.py`` deliberately roots its run under
    :func:`tempfile.gettempdir` to keep collection storage out of the checkout.

    A reaper that knew only the repository base left the pytest base growing
    without bound, which is the exact accrual :mod:`dev.env.temp_reaper` exists to
    prevent and which its own docstring opens by describing. Both bases are
    returned from here so that adding a third cannot be done in one place and
    forgotten in the other.
    """
    return (REPO_ROOT, Path(tempfile.gettempdir()))


def run_log_roots(family: str, *, bases: tuple[Path, ...] | None = None) -> tuple[Path, ...]:
    """Return every existing ``.logs/<family>`` root across ``bases``.

    Absent bases are filtered out rather than reported: a checkout that has never
    run the audit tooling simply has no such root, and that is not a condition a
    reclamation report should raise. ``bases`` is injectable so a caller can be
    tested against a tree it controls without substituting this module.
    """
    candidates = run_log_bases() if bases is None else bases
    roots = tuple(dict.fromkeys(base / LOGS_STEM / family for base in candidates))
    return tuple(root for root in roots if root.is_dir())


def allocate_run_directory(
    repository: Path,
    *,
    family: str,
    label: str,
    now: datetime | None = None,
) -> Path:
    """Return a collision-resistant run path below ``repository``'s ``.logs``.

    The PID in the marker is load-bearing rather than decorative: it is what lets
    the reaper resolve a directory's owner against the OS and so distinguish a run
    still being written from output that can go.
    """
    started = now or datetime.now(tz=UTC)
    marker = f"{started:%Y%m%dT%H%M%S.%fZ}-{label}-{os.getpid()}-{uuid4().hex[:8]}"
    return repository / LOGS_STEM / family / f"{started:%Y-%m-%d}" / marker
