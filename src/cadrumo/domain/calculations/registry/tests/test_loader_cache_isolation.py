"""Registry loader cache isolation under pytest.

The loader's cross-process ``/tmp`` ``cadrumo_registry_*.pkl`` disk pickle is keyed by
file mtime and SHARED across pytest-xdist worker processes, so a parallel ``-n`` run
could serve a stale/transient compiled registry from one worker to another, flaking
tests that depend on a specific registry compile. The loader originally skipped that
disk pickle under pytest ENTIRELY -- including collection before
``PYTEST_CURRENT_TEST`` is set -- which closed that race but forced every xdist
worker and every subprocess-spawning test to independently pay the full
multi-second registry compile, since a cold compile+validate of the bundled tree
costs single-to-double-digit seconds on this codebase's registry size.

The gate is now scoped to the ROOT: a mutable/synthetic root (a ``tmp_path`` test
fixture, or any path that is not the resolved package-bundled root) keeps the disk
pickle disabled under pytest, preserving the isolation invariant exactly -- such a
root can be edited mid-run by the very test that built it. The package-bundled, read-only
registry tree is never mutated during a run, so it is exempt: under pytest it now
shares ONE compiled disk pickle across every worker/subprocess that requests it,
collapsing N independent cold compiles into one compile the rest read.

These tests pin both invariants: the gate stays OFF for a mutable/default root (no
cross-worker stale-pickle race is possible there), turns ON for the bundled root, and
removing the pytest env markers restores the unconditional production path (so the
gate is genuine pytest-detection, not an unconditional disable). They read the real
gate -- no mocks, no tautology. :func:`test_bundled_root_disk_cache_is_shared_across_processes`
and :func:`test_synthetic_tmp_path_root_disk_cache_stays_disabled_under_pytest` prove
the end-to-end behavior through the real ``load_registry_tree`` entry point and the
real ``/tmp`` pickle file, not just the boolean gate.

The bundled-tree fingerprint TTL tests below pin a related but distinct
invariant: the fingerprint cache's directory-mtime walk is only skippable for
the package-bundled, read-only registry tree, never for a mutable authoring
tree (a ``tmp_path`` synthetic registry, or any path other than the bundled
root), so a live TOML edit to an authoring tree is never masked by an
overlong TTL window.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.config import override_settings
from .....core.resources import bundled_path
from .....tests.env_scope import scoped_env_var
from ..loader import (
    _collect_registry_tree_fingerprints,
    _load_registry_tree_cached,
    _registry_fingerprint_cache,
    clear_fingerprint_cache,
    is_bundled_registry_root,
    load_registry_tree,
    registry_disk_cache_enabled,
)
from .._loader_cache import REGISTRY_DISK_CACHE_DIR_ENV_VAR
from ._loader_directory_mode_support import _standard_manifest_text, _standard_revision_preamble_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REPO_ROOT = Path(__file__).resolve().parents[6]
# Hang guard only, not a performance assertion: each spawned REAL pytest
# session compiles the bundled registry (~9s on an idle machine) and this
# suite runs on a heavily loaded shared box (pytest-xdist workers plus
# concurrent agent sessions), where a 60s budget produced false timeouts
# unrelated to the purge regression this module guards against.
_SUBPROCESS_TIMEOUT_SECONDS = 300


def test_registry_disk_cache_disabled_under_pytest_for_a_mutable_root() -> None:
    """The shared ``/tmp`` disk pickle is gated OFF under pytest for a non-bundled root.

    The pytest process itself is enough to disable the gate for the
    ``is_bundled=False`` default, including collection before
    ``PYTEST_CURRENT_TEST`` is present -- the invariant that removes the
    cross-worker stale-pickle race the #44 root-cause identified, preserved
    for every mutable/synthetic root after the bundled-root carve-out below.
    """
    assert "PYTEST_CURRENT_TEST" in os.environ, "sanity: this test runs under pytest"
    assert registry_disk_cache_enabled() is False
    assert registry_disk_cache_enabled(is_bundled=False) is False


def test_registry_disk_cache_enabled_under_pytest_for_the_bundled_root() -> None:
    """The gate is ON under pytest when the caller identifies the root as bundled.

    The package-bundled read-only registry tree is never mutated during a test
    run, so it is exempt from the #44 isolation concern: every pytest-xdist
    worker and every subprocess-spawning test may safely share its compiled
    disk pickle. See :func:`test_bundled_root_disk_cache_is_shared_across_processes`
    for the real cross-process proof this boolean gate enables.
    """
    assert "PYTEST_CURRENT_TEST" in os.environ, "sanity: this test runs under pytest"
    assert registry_disk_cache_enabled(is_bundled=True) is True


def test_registry_disk_cache_enabled_without_pytest_markers() -> None:
    """With the pytest env markers removed, the production disk cache is ENABLED.

    Proves the gate is genuine pytest-detection (not an unconditional disable):
    a clean child interpreter without pytest loaded and without pytest env markers
    restores the production path, so production keeps its startup-time registry disk cache.
    """
    env = os.environ.copy()
    for name in ("PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER", "PYTEST_VERSION"):
        env.pop(name, None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from cadrumo.domain.calculations.registry.loader import registry_disk_cache_enabled; "
                "print(registry_disk_cache_enabled())"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    assert completed.stdout.strip() == "True"


def test_is_bundled_registry_root_identifies_the_real_bundled_tree() -> None:
    """The predicate recognises the package-bundled registry root by resolved path."""
    bundled_root = bundled_path("registry", "aeat").resolve()
    assert is_bundled_registry_root(bundled_root) is True


def test_is_bundled_registry_root_rejects_a_mutable_authoring_tree(tmp_path: Path) -> None:
    """A ``tmp_path`` synthetic registry is never mistaken for the bundled tree.

    This is the safety half of the bundled-TTL win: a mutable authoring tree
    (a test fixture here, but structurally the same shape as a dev checkout
    path passed explicitly) must never receive the longer bundled TTL, or a
    concurrent edit to it would go undetected for the longer window.
    """
    registry_root = tmp_path / "registry" / "aeat"
    registry_root.mkdir(parents=True)
    assert is_bundled_registry_root(registry_root) is False
    assert is_bundled_registry_root(registry_root.resolve()) is False


def test_bundled_tree_fingerprint_cache_hit_skips_the_directory_walk() -> None:
    """A same-process bundled-tree fingerprint call within the TTL reuses the cached tuple.

    Proves the real behavior (not a mock): two fingerprint calls milliseconds
    apart on the bundled tree return the SAME tuple object, which is only
    possible when the second call short-circuited before rebuilding the
    fingerprint list -- i.e. it skipped the directory-mtime walk entirely
    rather than recomputing it to compare against the cached copy.
    """
    clear_fingerprint_cache()
    bundled_root = bundled_path("registry", "aeat").resolve()
    assert is_bundled_registry_root(bundled_root) is True

    first = _collect_registry_tree_fingerprints(bundled_root)
    second = _collect_registry_tree_fingerprints(bundled_root)
    assert second is first, "a bundled-tree cache hit must reuse the cached fingerprint tuple, not rebuild it"


def test_bundled_tree_fingerprint_ttl_window_is_not_consumed_by_its_own_walk() -> None:
    """The bundled cache entry is stamped when the walk FINISHED, not when it began.

    The TTL bounds how often the expensive directory walk is redone on a
    read-only bundled tree. Stamping the entry with the clock read at walk START
    charges the walk's own cost against the window: the walk covers 17k+ entries
    and measures ~1s on an idle machine but has been measured at 9.05s under
    parallel-suite load, leaving under a second of the 10s window -- and a
    marginally slower walk consumes it outright, so the very next call misses and
    rebuilds. That is precisely the sibling cache-hit test's failure mode, seen
    only in a loaded full-suite run.

    Real elapsed time, no mocked clock, and the bounds are expressed as fractions
    of the walk's OWN measured duration so they discriminate at any host speed
    rather than encoding a wall-clock threshold. Under the start-stamping defect
    ``stamped - started`` is zero for a walk of any length, so the second
    assertion fails outright; it cannot pass vacuously on a fast machine.
    """
    clear_fingerprint_cache()
    bundled_root = bundled_path("registry", "aeat").resolve()
    assert is_bundled_registry_root(bundled_root) is True

    # The production stamp is taken from `time.time()`, so the test must compare
    # against that same clock rather than a monotonic one.
    started = time.time()
    fingerprints = _collect_registry_tree_fingerprints(bundled_root)
    returned = time.time()

    stamped, _cached_directories, cached_value = _registry_fingerprint_cache[bundled_root]
    assert cached_value is fingerprints
    walk_seconds = returned - started
    assert walk_seconds > 0.0, "the cold bundled walk must take measurable time for this proof to bite"
    assert stamped - started >= walk_seconds / 2, (
        "the bundled fingerprint entry must be stamped after the walk completed, not at walk start: "
        f"stamp landed {stamped - started:.3f}s into a {walk_seconds:.3f}s walk"
    )
    assert returned - stamped <= walk_seconds / 2, (
        "the caller must receive effectively the whole TTL window: "
        f"{returned - stamped:.3f}s of a {walk_seconds:.3f}s walk was already spent when it returned"
    )


def test_bundled_tree_fingerprint_cache_survives_past_the_mutable_tree_ttl() -> None:
    """The bundled tree's TTL window outlives the strict mutable-tree window.

    Sleeping past the 1-second mutable-tree TTL and then re-requesting the
    bundled tree's fingerprint must still hit the cache (real elapsed time,
    no mocked clock), proving the bundled tree genuinely gets a longer TTL
    rather than merely tolerating a race on an unmodified test machine.
    """
    clear_fingerprint_cache()
    bundled_root = bundled_path("registry", "aeat").resolve()

    first = _collect_registry_tree_fingerprints(bundled_root)
    time.sleep(1.2)
    second = _collect_registry_tree_fingerprints(bundled_root)
    assert second is first, "the bundled tree's TTL must outlive the strict 1-second mutable-tree window"


def _bundled_registry_disk_cache_files(cache_dir: Path) -> set[Path]:
    """List every ``cadrumo_registry_*.pkl`` in ``cache_dir``.

    ``cache_dir`` is required, and every caller passes a test-owned directory
    scoped by ``CADRUMO_REGISTRY_DISK_CACHE_DIR``. It previously defaulted to
    the real OS temp directory, which is where the loader sends every worker's
    bundled-root pickle under pytest and which it prunes to the retained-entry
    ceiling on each write -- so any before/after snapshot taken there measures
    concurrent xdist workers and sibling pytest invocations on the host rather
    than the call under test. Keeping the parameter required removes that
    default rather than leaving it for the next caller to fall into.
    """
    return set(scan_directory(cache_dir, pattern="cadrumo_registry_*.pkl"))


def test_bundled_root_disk_cache_is_shared_across_processes(
    tmp_path: Path,
) -> None:
    """Under pytest, the bundled root's disk pickle is written once and shared.

    Real end-to-end proof through the actual ``load_registry_tree`` entry point
    and the actual pickle file on disk, not just the boolean gate above: after
    this (pytest) process compiles the bundled tree and writes its disk pickle,
    a SEPARATE child process -- launched with ``PYTEST_CURRENT_TEST`` set, so it
    is itself pytest-like exactly as an xdist worker would be -- reads the SAME
    pickle rather than recompiling and rewriting it. Reusing the identical file
    (unchanged mtime and size) is the only way this can happen, since a rewrite
    would touch both.

    Isolated onto a test-owned cache directory via
    ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` (propagated to the child process's own
    ``env=``, not just this process's ``os.environ``): this test's
    exclusive-state assertions ("exactly one file", "mtime unchanged") would
    otherwise be confused by a SIBLING pytest-xdist worker concurrently
    touching the real shared bundled-root pickle in the real OS temp
    directory under a parallel ``-n`` run. The test still exercises the real
    filesystem and the real pickle read/write path end-to-end (no mock of the
    loader's own behavior) -- only the directory is test-owned, not the
    mechanism.

    Proof is STRUCTURAL (mtime and size unchanged), not timing-based: a
    machine under heavy concurrent load (this is a shared, multi-agent
    worktree) can make even a genuine cache-hit read take several seconds
    once subprocess startup and unpickling ~20MB of compiled registry data
    are counted, overlapping the range a cold compile itself takes on this
    codebase's registry size -- a wall-clock threshold cannot reliably tell
    the two apart here. The mtime/size identity check has no such ambiguity:
    a rewrite touches both, unconditionally, on every real filesystem.
    """
    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()
    # ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` backs the Settings field
    # ``cadrumo_registry_disk_cache_dir``; ``load_settings()`` caches the
    # constructed ``Settings`` per active-profile pointer, so a plain
    # ``os.environ`` mutation via ``scoped_env_var`` is invisible to the
    # in-process resolver once any earlier call has already built and cached
    # a ``Settings`` instance. ``override_settings`` is the mechanism that
    # actually takes effect for this in-process load.
    with override_settings(cadrumo_registry_disk_cache_dir=isolated_cache_dir):
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

        bundled_root = bundled_path("registry", "aeat").resolve()
        modelos, _catalogues = load_registry_tree(bundled_root)
        assert modelos, "sanity: the bundled tree must compile at least one modelo"

        written = _bundled_registry_disk_cache_files(isolated_cache_dir)
        assert len(written) == 1, (
            f"expected exactly one bundled-root disk pickle after the first compile, got {written}"
        )
        cache_path = next(iter(written))
        stat_before = cache_path.stat()

        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from cadrumo.domain.calculations.registry.loader import load_registry_tree\n"
                    "from cadrumo.core.resources import bundled_path\n"
                    "root = bundled_path('registry', 'aeat').resolve()\n"
                    "modelos, _ = load_registry_tree(root)\n"
                    "print(len(modelos))\n"
                ),
            ],
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "PYTEST_CURRENT_TEST": "simulated_worker::test_shares_bundled_disk_cache",
                REGISTRY_DISK_CACHE_DIR_ENV_VAR: str(isolated_cache_dir),
            },
            text=True,
            timeout=60,
        )
        child_modelo_count = int(completed.stdout.strip())
        assert child_modelo_count == len(modelos), (
            "the child process must compile the identical modelo set from the shared pickle"
        )

        after_child = _bundled_registry_disk_cache_files(isolated_cache_dir)
        assert after_child == written, "the child process must not have written a second disk pickle"
        stat_after = cache_path.stat()
        assert stat_after.st_mtime_ns == stat_before.st_mtime_ns, (
            "the child process rewrote the shared pickle instead of reading it"
        )
        assert stat_after.st_size == stat_before.st_size, (
            "the child process rewrote the shared pickle instead of reading it"
        )


def test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions(
    tmp_path: Path,
) -> None:
    """The per-session cache-isolation fixture must not purge the bundled disk pickle.

    Regression proof for a real defect: an earlier version of
    ``_isolate_registry_caches`` (``src/cadrumo/conftest.py``) purged EVERY
    ``cadrumo_registry_*.pkl`` unconditionally at session start. Under
    pytest-xdist, ``scope="session"`` means "per worker process" -- there is
    no single controlling session spanning all workers -- so every worker's
    own session start deleted the very pickle a sibling worker (or an earlier
    invocation) had just written, forcing each one to independently recompile
    the bundled tree from scratch with zero cross-worker sharing. Measured
    directly during this fix's investigation: two separate real ``pytest``
    invocations against the same bundled-tree content took 8.6-8.9s EACH
    before the purge was removed, and 8.9s then 1.3s after.

    This test proves it through TWO REAL, SEPARATE ``pytest`` subprocess
    invocations (not simulated via env vars, and not the same process
    twice) against a throwaway scratch package materialised under this
    test's OWN ``tmp_path`` -- never under the tracked ``src/cadrumo`` tree,
    which every source-tree AST gate (the import-hygiene scanner, the
    codebase-size and layering ratchets) walks and reads live. An earlier
    version of this proof wrote its scratch module directly into this real
    ``tests/`` directory; under a parallel ``-n`` run that write/run/unlink
    window raced a sibling worker's AST scan of the same directory,
    surfacing as a transient ``FileNotFoundError`` in an unrelated gate. The
    scratch package instead carries its OWN ``conftest.py`` re-exporting the
    real ``src/cadrumo/conftest.py`` autouse fixture by absolute import, so the
    spawned session is still governed by the SAME fixture a real xdist
    worker's own test file would load -- the proof is unweakened, only its
    location moved off the walked tree.

    Isolated onto a test-owned cache directory via
    ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` (set in this process's own environment,
    which both spawned ``pytest`` subprocesses inherit): otherwise a SIBLING
    pytest-xdist worker concurrently touching the real shared bundled-root
    pickle in the real OS temp directory under a parallel ``-n`` run could
    make this test's exclusive-state assertions ("exactly one file", "mtime
    unchanged") fail for a reason unrelated to what this test actually
    guards against.
    """
    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()

    scratch_pkg = tmp_path / "purge_isolation_proof_pkg"
    scratch_pkg.mkdir()
    (scratch_pkg / "conftest.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "# Re-exports the real session-scoped autouse cache-isolation fixture so this\n"
        "# out-of-tree scratch package, invoked as its own pytest session, is governed\n"
        "# by the identical fixture a real xdist worker's own src/cadrumo test file loads.\n"
        "from cadrumo.conftest import _isolate_registry_caches as _isolate_registry_caches\n",
        encoding="utf-8",
    )
    scratch_module_path = scratch_pkg / "test_touch_bundled_registry.py"
    scratch_module_path.write_text(
        "from __future__ import annotations\n"
        "\n"
        "import pytest\n"
        "\n"
        "from cadrumo.core.resources import bundled_path\n"
        "from cadrumo.domain.calculations.registry.loader import load_registry_tree\n"
        "\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]\n"
        "\n"
        "\n"
        "def test_touch_bundled_registry() -> None:\n"
        "    root = bundled_path('registry', 'aeat').resolve()\n"
        "    modelos, _catalogues = load_registry_tree(root)\n"
        "    assert modelos\n",
        encoding="utf-8",
    )

    def _run_real_pytest_session() -> subprocess.CompletedProcess[str]:
        node_id = f"{scratch_module_path}::test_touch_bundled_registry"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                # Pin rootdir to the throwaway scratch package so collection
                # NEVER walks the shared OS temp tree. Without this, pytest
                # infers a rootdir across the Y:-drive cwd and the C:\Temp
                # scratch node, and the inherited testpaths=["src/cadrumo"]
                # drives a broad collection walk that lstat()s sibling temp
                # dirs -- a concurrent agent deleting its own transient
                # ``cli-sequence-*`` temp dir mid-walk then surfaces here as a
                # spurious collection FileNotFoundError, flaking this proof.
                "--rootdir",
                str(scratch_pkg),
                "--override-ini",
                "testpaths=",
                "-n0",
                "-m",
                "unit",
                node_id,
            ],
            cwd=scratch_pkg,
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(isolated_cache_dir)):
        for stale in _bundled_registry_disk_cache_files(isolated_cache_dir):
            stale.unlink(missing_ok=True)

        first = _run_real_pytest_session()
        assert first.returncode == 0, f"first real pytest session failed:\n{first.stdout}\n{first.stderr}"
        written = _bundled_registry_disk_cache_files(isolated_cache_dir)
        assert len(written) == 1, f"expected exactly one bundled-root disk pickle after session 1, got {written}"
        cache_path = next(iter(written))
        stat_after_first = cache_path.stat()

        second = _run_real_pytest_session()
        assert second.returncode == 0, f"second real pytest session failed:\n{second.stdout}\n{second.stderr}"
        stat_after_second = cache_path.stat()

        assert _bundled_registry_disk_cache_files(isolated_cache_dir) == written, (
            "a second real pytest session must not write a second disk pickle"
        )
        assert stat_after_second.st_mtime_ns == stat_after_first.st_mtime_ns, (
            "the second real pytest session's own autouse session-start fixture purged and "
            "recompiled the shared bundled-root pickle instead of reading it -- the #148 "
            "cross-worker sharing regression this test guards against"
        )
        assert stat_after_second.st_size == stat_after_first.st_size, (
            "the second real pytest session rewrote the shared pickle instead of reading it"
        )


def test_synthetic_tmp_path_root_disk_cache_stays_disabled_under_pytest(tmp_path: Path) -> None:
    """A mutable ``tmp_path`` registry never gets a disk pickle under pytest, even now.

    Builds a minimal, real, successfully-loadable synthetic registry tree (the
    same fixture shape :mod:`test_loader_directory_mode` uses) and loads it
    through the real ``load_registry_tree`` entry point under the current
    pytest process. Because ``is_bundled_registry_root`` rejects any path other
    than the resolved package-bundled root, this call must never write a disk
    pickle -- the #44 isolation invariant for exactly the kind of root a test
    can mutate mid-run.

    Isolated onto a test-owned cache directory via
    ``CADRUMO_REGISTRY_DISK_CACHE_DIR``, for the same reason the sibling
    exclusive-state tests above are: with no override,
    ``registry_disk_cache_dir()`` resolves to the host-shared OS temp directory,
    where every sibling xdist worker and every concurrent pytest invocation on
    the host legitimately writes its own bundled-root pickle AND prunes the
    others past the retained-entry ceiling. A before/after snapshot of that
    directory therefore measures the whole host, not this call: a foreign
    create or evict lands between the two globs and fails the assertion while
    the code under test behaved correctly. A test-owned directory makes the
    invariant exact -- it must be empty on both sides, since the synthetic root
    is the only thing loaded inside the block. The real filesystem and the real
    write path are still exercised; only the directory is test-owned.
    """
    registry_root = tmp_path / "registry" / "aeat"
    legal_dir = registry_root / "legal"
    legal_dir.mkdir(parents=True)
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025]\n",
        encoding="utf-8",
        newline="\n",
    )
    modelos_dir = registry_root / "modelos"
    modelos_dir.mkdir()
    (modelos_dir / "999.toml").write_text(
        _standard_manifest_text("Synthetic disk-cache isolation test") + "\n" + _standard_revision_preamble_text(),
        encoding="utf-8",
    )
    assert is_bundled_registry_root(registry_root.resolve()) is False

    isolated_cache_dir = tmp_path / "registry-disk-cache"
    isolated_cache_dir.mkdir()
    with scoped_env_var(REGISTRY_DISK_CACHE_DIR_ENV_VAR, str(isolated_cache_dir)):
        before = _bundled_registry_disk_cache_files(isolated_cache_dir)
        assert before == set(), "the test-owned cache directory must start empty for the assertion below to bite"

        modelos, catalogues = load_registry_tree(registry_root)
        assert {modelo.id for modelo in modelos} == {"999"}
        assert catalogues.supported_filing_years is not None
        assert catalogues.supported_filing_years.years == (2025,)

        after = _bundled_registry_disk_cache_files(isolated_cache_dir)
        assert after == set(), (
            f"a mutable/synthetic root must never write a disk pickle under pytest, found {sorted(after)}"
        )
