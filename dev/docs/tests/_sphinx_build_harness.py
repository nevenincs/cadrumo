"""Shared harness for the real nitpicky Sphinx build gates.

The docs lane's dominant cost is its set of real ``-n -W`` Sphinx builds (full
scope, user scope, and one per translation language). Two structural choices
keep the lane fast without weakening any check:

* **One heavy build per test module.** pytest-xdist distributes by file
  (``--dist=loadfile``), so a module that carries several multi-minute builds
  serialises them all on one worker while the rest of the lane idles. Each
  gate build therefore lives in its own module, importing this harness, and
  the builds run concurrently.
* **Build-invariant hook work runs once per lane, not once per build.** Every
  gate build sets the explicit opt-outs for the two ``builder-inited`` hooks
  whose outcome cannot vary across these builds and which the lane already
  enforces through dedicated gates: the cli-sequence golden check (the check
  subprocess pins its own environment — scrubbed ``CADRUMO_*``, English
  output — so its verdict is identical for every scope/language; the
  dedicated goldens gate executes it once, and the divergence-reds fixture
  proves the hook itself still fails a build) and the ``cli-tree.json``
  projection (a walk of the live CLI tree with its own gate coverage; the
  ``dummy`` builder ships no static assets, so the artifact is unread here).
  Production builds set neither opt-out and keep both hooks live.

The remaining per-build hook work (CLI reference, glossary, and casilla page
generation) is genuinely needed by each build's read set — the pages must
exist for the toctrees and cross-references the ``-n -W`` gate resolves — and
stays untouched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..._paths import REPO_ROOT

DOCS = REPO_ROOT / "docs"

#: Wall ceiling for every spawned gate-build subprocess, set BELOW the 1800 s
#: per-test ceiling so the subprocess timeout wins the race and names itself
#: (``TimeoutExpired`` reports the command and the limit) instead of pytest
#: dumping a stack with no indication of which build hung.
SUBPROCESS_TIMEOUT_S = 1200

#: Bounded default width for gate builds: parallel enough to finish, small
#: enough to leave the host usable. Overridable via ``CADRUMO_DOCS_JOBS``.
_GATE_BUILD_JOBS_DEFAULT = "4"


def gate_build_jobs() -> str:
    """Resolve the Sphinx ``-j`` width for a gate build.

    A gate wants determinism and a bounded footprint, not peak speed, so this
    does NOT default to ``auto``. ``auto`` takes one worker per core -- 24 on
    the current build host -- which is the same unbounded-width pattern
    ``.github/ci-control-plane.md`` bans for ``pytest -n auto``, and for the
    same reason: co-resident CI lanes and peer agents already contend for those
    cores, so an uncapped build starves itself and everything beside it.

    An explicit ``CADRUMO_DOCS_JOBS`` still wins, routed through the shared
    :func:`~dev.docs.build.docs_build_jobs` resolver so the deployment knob
    keeps one validation path rather than two.

    Windows note: Sphinx parallel workers require ``os.fork``
    (``sphinx.util.parallel.parallel_available`` is ``False`` on win32), so on
    a Windows host EVERY value here is a no-op and the build runs serial.
    Tuning this number locally on Windows measures nothing; it only ever
    bounds POSIX (Linux CI) builds.

    Returns:
        The ``-j`` value string to hand to ``sphinx-build``.
    """
    if "CADRUMO_DOCS_JOBS" in os.environ:
        from ..build import docs_build_jobs

        return docs_build_jobs(os.environ)
    return _GATE_BUILD_JOBS_DEFAULT


def copy_docs_source(tmp_path: Path) -> Path:
    """Copy the committed docs tree into an isolated per-test source root.

    Excludes the build output and the generated ``cli`` reference tree (the
    ``builder-inited`` hook regenerates it fresh inside the copy), exactly as
    every gate build has always done.
    """
    docs_source = tmp_path / "docs-source"
    shutil.copytree(DOCS, docs_source, ignore=shutil.ignore_patterns("_build", "cli"))
    return docs_source


def gate_build_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """Build the hermetic environment for one gate build subprocess.

    Offline intersphinx, an isolated storage root, and the two build-invariant
    hook opt-outs described in the module docstring. ``extra`` entries win.
    """
    env = {
        **os.environ,
        "CADRUMO_DOCS_OFFLINE": "1",
        "CADRUMO_DOCS_PROJECT_ROOT": str(REPO_ROOT),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-docs-state"),
        "CADRUMO_DOCS_SKIP_SEQUENCE_CHECK": "1",
        "CADRUMO_DOCS_SKIP_CLI_TREE": "1",
    }
    env.update(extra)
    return env


def run_nitpicky_dummy_build(
    docs_source: Path,
    out_dir: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one real ``-b dummy -n -W`` Sphinx build over ``docs_source``.

    Uses the ``dummy`` builder, not ``html``: the gate only asserts that the
    full parse and cross-reference resolution (where ``-n`` nitpicky warnings
    fire) raise no warnings under ``-W``; it does not need rendered HTML, so
    rendered-page emission is skipped.
    """
    return subprocess.run(  # noqa: S603 - fixed interpreter, repository-owned inputs.
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "dummy",
            "-n",
            "-W",
            "-j",
            gate_build_jobs(),
            str(docs_source),
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_S,
    )
