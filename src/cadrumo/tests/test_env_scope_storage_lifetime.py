"""The temporary storage roots ``env_scope`` mints do not outlive the session.

``settings_without_env_file`` mints a temporary root whenever the caller
supplies none and the environment carries none, and holds it open because the
returned :class:`Settings` names that path. Holding it open is correct;
holding it forever was not. A runtime write census measured 457 of them in the
operator's temp directory, the oldest three weeks old -- one per call, across
every session ever run, covered by no sweep.

These pin the lifetime rather than the mechanism: that a root is created and
usable while it is needed, and gone once released.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory
from .collection_storage_root import (
    _ABANDONED_AFTER_SECONDS,
    _STALE_AFTER_SECONDS,
    _STEM,
    SETTINGS_STEM,
    process_is_live,
    sweep_stale_roots,
)
from .env_scope import (
    _SETTINGS_STORAGE_DIRECTORIES,
    isolated_aeat_env,
    release_settings_storage_directories,
    settings_without_env_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60


def _age(directory: Path, seconds: float) -> None:
    """Backdate ``directory``'s mtime so the sweep sees it as that old."""
    stamp = directory.stat().st_mtime - seconds
    os.utime(directory, (stamp, stamp))


def _a_genuinely_dead_pid() -> int:
    """Run a real process to completion and return its now-unused identifier.

    A real reaped process rather than a fabricated number: an arbitrary large
    integer would also read as dead, but it would prove only that the probe
    dislikes unfamiliar numbers, not that it tracks a real process's actual
    lifetime. Closing the handle (leaving the context manager) matters on
    Windows, where an open handle keeps the identifier reserved.
    """
    with subprocess.Popen([sys.executable, "-c", "pass"]) as child:  # fixed interpreter argv, no external input.
        child.wait(timeout=_SUBPROCESS_TIMEOUT_SECONDS)
        pid = child.pid
    return pid


def test_a_minted_root_exists_while_it_is_held() -> None:
    """The directory is real while the Settings that names it is in use.

    The positive control for every assertion below: releasing something that
    was never created would satisfy a removal check trivially.
    """
    with isolated_aeat_env():
        settings = settings_without_env_file()
        root = Path(settings.cadrumo_local_storage_root)

        assert root.is_dir()
        assert root.name.startswith("cadrumo-settings-")
        assert _SETTINGS_STORAGE_DIRECTORIES, "the mint must be tracked, or nothing can release it"

    release_settings_storage_directories()


def test_release_removes_every_minted_root() -> None:
    """After release the directories are gone and nothing is still tracked."""
    with isolated_aeat_env():
        roots = [Path(settings_without_env_file().cadrumo_local_storage_root) for _ in range(3)]

    assert len(set(roots)) == 3, "each call must mint its own root, or isolation is shared"
    assert all(root.is_dir() for root in roots)

    release_settings_storage_directories()

    assert not any(root.exists() for root in roots), f"still on disk: {[r for r in roots if r.exists()]}"
    assert not _SETTINGS_STORAGE_DIRECTORIES


def test_release_is_safe_to_repeat_and_safe_when_nothing_was_minted() -> None:
    """Session teardown must not depend on whether any root was minted.

    The fixture runs for every session, including ones that never call the
    factory, and a teardown that raised there would fail sessions unrelated to
    the thing being cleaned up.
    """
    release_settings_storage_directories()
    release_settings_storage_directories()

    assert not _SETTINGS_STORAGE_DIRECTORIES


def test_a_caller_supplied_root_is_not_minted_or_released(tmp_path: Path) -> None:
    """Only roots this module created are its to remove.

    The guard that matters for a destructive teardown: a caller that names its
    own storage root owns that directory, and release must not reach it.
    """
    supplied = tmp_path / "operator-owned"
    supplied.mkdir()

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=supplied)

    assert Path(settings.cadrumo_local_storage_root) == supplied
    assert not _SETTINGS_STORAGE_DIRECTORIES, "a supplied root must not be tracked for removal"

    release_settings_storage_directories()

    assert supplied.is_dir(), "release deleted a directory it did not create"


def test_the_sweep_reclaims_a_stale_per_call_root(tmp_path: Path) -> None:
    """A root left by a killed process is reclaimed once it is stale.

    The complement to the session finalizer. A worker killed rather than torn
    down runs neither ``atexit`` nor pytest teardown, so the finalizer never
    fires and only a sweep can reach what it left. On a loaded shared box that
    is routine, not exceptional.
    """
    stale = tmp_path / f"{SETTINGS_STEM}killed-worker"
    stale.mkdir()
    _age(stale, _STALE_AFTER_SECONDS + 60)

    assert sweep_stale_roots(tmp_path) == 1
    assert not stale.exists()


def test_the_sweep_spares_a_root_still_in_use(tmp_path: Path) -> None:
    """A fresh root belongs to a live session and must survive.

    The assertion that stops the sweep being a liability: a concurrent pytest
    invocation sharing this temp directory is mid-run, and reclaiming its
    storage root would fail its tests rather than tidy up after it.
    """
    live = tmp_path / f"{SETTINGS_STEM}live-session"
    live.mkdir()
    (live / "in-use.txt").write_text("held", encoding="utf-8")

    assert sweep_stale_roots(tmp_path) == 0
    assert (live / "in-use.txt").read_text(encoding="utf-8") == "held"


def test_the_sweep_ignores_directories_it_does_not_own(tmp_path: Path) -> None:
    """Age alone is not licence: the prefix decides what is ours to remove.

    A shared OS temp directory holds other tools' artefacts, many of them
    older than a day. Sweeping by age without the prefix would delete them.
    """
    foreign = tmp_path / "some-other-tool-workspace"
    foreign.mkdir()
    _age(foreign, _STALE_AFTER_SECONDS * 30)

    assert sweep_stale_roots(tmp_path) == 0
    assert foreign.is_dir()


def test_the_liveness_probe_separates_a_running_process_from_a_reaped_one() -> None:
    """The positive control for every liveness-grounded assertion below.

    Without this pair, a probe that answered "dead" to everything would satisfy
    the reclaim tests and a probe that answered "live" to everything would
    satisfy the sparing tests -- each half looks green on its own.
    """
    assert process_is_live(os.getpid()), "this very process must read as running"
    assert not process_is_live(_a_genuinely_dead_pid()), "a reaped process must read as gone"


def test_the_sweep_reclaims_a_root_whose_owning_process_is_gone(tmp_path: Path) -> None:
    """An abandoned root is reclaimed on the owner's death, not a day later.

    The leak this closes: a killed worker's root used to wait out the full
    24h mtime ceiling, and on this box they accrued faster than the ceiling
    released them. The filename names its owner, so the sweep can ask directly
    rather than inferring abandonment from an mtime that says nothing about
    whether anyone is still holding the directory.
    """
    abandoned = tmp_path / f"{_STEM}{_a_genuinely_dead_pid()}"
    abandoned.mkdir()
    (abandoned / "cadrumo.db").write_text("payload the killed worker left", encoding="utf-8")
    _age(abandoned, _ABANDONED_AFTER_SECONDS + 60)

    assert sweep_stale_roots(tmp_path) == 1
    assert not abandoned.exists()


def test_the_sweep_spares_a_root_whose_owning_process_is_still_running(tmp_path: Path) -> None:
    """The load-bearing guarantee: a live session's store is never reclaimed.

    Many pytest sessions share one temp directory on this box -- xdist workers
    plus several agents at once -- so a startup sweep that mistook a running
    session for an abandoned one would fail that session's tests rather than
    tidy up after it. This root is named for a process that is definitively
    alive (this one), and is old enough that the abandonment grace has long
    since elapsed: only the liveness answer can save it.
    """
    live = tmp_path / f"{_STEM}{os.getpid()}"
    live.mkdir()
    (live / "cadrumo.db").write_text("held by a running session", encoding="utf-8")
    _age(live, _ABANDONED_AFTER_SECONDS * 6)

    assert sweep_stale_roots(tmp_path) == 0
    assert (live / "cadrumo.db").read_text(encoding="utf-8") == "held by a running session"


def test_the_sweep_spares_a_recently_abandoned_root_until_the_grace_elapses(tmp_path: Path) -> None:
    """Death alone is not licence; the grace absorbs the exit-race window.

    A process that has just exited may still be mid-``rmtree`` in its own
    ``atexit`` hook, and an mtime read can disagree with a liveness read by a
    little clock skew. The grace covers both without reintroducing the day-long
    wait.
    """
    just_gone = tmp_path / f"{_STEM}{_a_genuinely_dead_pid()}"
    just_gone.mkdir()

    assert sweep_stale_roots(tmp_path) == 0
    assert just_gone.is_dir()


def test_the_sweep_spares_the_calling_processs_own_root(tmp_path: Path) -> None:
    """The sweep must never reclaim the root the caller is about to use.

    Its owner is live, so the liveness rule already spares it; the explicit
    exclusion means the caller does not have to depend on that reasoning
    holding for every future family the sweep grows.
    """
    own = tmp_path / f"{_STEM}{os.getpid()}"
    own.mkdir()
    _age(own, _STALE_AFTER_SECONDS * 10)
    (own / "cadrumo.db").write_text("this session's own store", encoding="utf-8")

    assert sweep_stale_roots(tmp_path, exclude=own) == 0
    assert (own / "cadrumo.db").read_text(encoding="utf-8") == "this session's own store"


def test_the_sweep_is_safe_to_run_concurrently(tmp_path: Path) -> None:
    """Many workers start near-simultaneously and all sweep the same directory.

    Nothing the sweep removes belongs to a live session, so two sweepers
    reaching one directory at once can each partially remove it without any run
    observing the difference. What must hold is that no invocation raises and
    that the live root survives all of them.
    """
    dead_pid = _a_genuinely_dead_pid()
    for index in range(12):
        abandoned = tmp_path / f"{_STEM}{dead_pid + index * 100000}"
        abandoned.mkdir()
        for leaf in range(5):
            (abandoned / f"payload-{leaf}.db").write_text("x" * 2048, encoding="utf-8")
        _age(abandoned, _ABANDONED_AFTER_SECONDS + 60)
    live = tmp_path / f"{_STEM}{os.getpid()}"
    live.mkdir()
    (live / "cadrumo.db").write_text("held throughout", encoding="utf-8")
    _age(live, _ABANDONED_AFTER_SECONDS * 6)

    failures: list[BaseException] = []

    def _sweep() -> None:
        try:
            sweep_stale_roots(tmp_path)
        except BaseException as error:  # the assertion under test is that none escapes.
            failures.append(error)

    workers = [threading.Thread(target=_sweep) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=_SUBPROCESS_TIMEOUT_SECONDS)

    assert not failures, f"concurrent sweeps raised: {failures}"
    survivors = scan_directory(tmp_path, pattern=f"{_STEM}*")
    assert not [path for path in survivors if path != live]
    assert (live / "cadrumo.db").read_text(encoding="utf-8") == "held throughout"


def test_the_reclaim_runs_at_startup_and_not_only_at_exit(tmp_path: Path) -> None:
    """The whole fix, proved against the failure mode it exists for.

    A real subprocess that leaves via ``os._exit`` runs no ``atexit`` hook and
    no pytest teardown -- the same shape as the killed workers whose roots
    accumulated. If the abandoned siblings are gone afterwards, only a sweep
    that ran when the process STARTED can have removed them.

    This is also the anti-vacuity proof: with the sweep back at exit only, this
    child reaches no sweep at all and both siblings survive. Both swept
    families are represented, since each leaks by the same mechanism.
    """
    parent = tmp_path / "shared-temp"
    parent.mkdir()
    abandoned_pytest_root = parent / f"{_STEM}{_a_genuinely_dead_pid()}"
    abandoned_pytest_root.mkdir()
    (abandoned_pytest_root / "cadrumo.db").write_text("killed worker's store", encoding="utf-8")
    _age(abandoned_pytest_root, _ABANDONED_AFTER_SECONDS + 60)
    abandoned_settings_root = parent / f"{SETTINGS_STEM}killed-worker"
    abandoned_settings_root.mkdir()
    _age(abandoned_settings_root, _STALE_AFTER_SECONDS + 60)
    live_sibling = parent / f"{_STEM}{os.getpid()}"
    live_sibling.mkdir()
    (live_sibling / "cadrumo.db").write_text("a concurrent session's store", encoding="utf-8")
    _age(live_sibling, _ABANDONED_AFTER_SECONDS * 6)

    probe = textwrap.dedent(
        f"""
        import os
        from pathlib import Path

        from cadrumo.tests.collection_storage_root import register_collection_storage_root_cleanup

        parent = Path({str(parent)!r})
        root = parent / f"cadrumo-pytest-{{os.getpid()}}"
        root.mkdir()
        register_collection_storage_root_cleanup(root)
        # Leave the way a killed worker leaves: no atexit hooks, no teardown.
        os._exit(0)
        """,
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter argv; probe source is a test-local literal.
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 0, f"probe failed:\n{completed.stdout}\n{completed.stderr}"
    assert not abandoned_pytest_root.exists(), (
        "the startup sweep did not reclaim an abandoned per-process root; only an exit-time "
        "sweep would have missed it, and this child ran no exit hooks"
    )
    assert not abandoned_settings_root.exists(), "the startup sweep skipped the per-call root family"
    assert (live_sibling / "cadrumo.db").read_text(encoding="utf-8") == "a concurrent session's store", (
        "the startup sweep reclaimed a running session's store"
    )
    survivors = {path.name for path in scan_directory(parent, pattern=f"{_STEM}*")}
    assert live_sibling.name in survivors
    assert survivors - {live_sibling.name}, (
        "the child's own root should have been LEFT behind -- it exited without running its "
        "atexit hook, which is precisely the leak a successor's startup sweep has to reclaim; "
        "if it is gone, this probe no longer reproduces the failure mode"
    )


def test_the_mint_prefix_is_the_swept_prefix() -> None:
    """The name is declared once, so the sweep cannot miss what the mint makes.

    Two spellings of one prefix is how a sweep silently stops covering the
    thing it was added for. This reads the real minted directory rather than
    comparing the constant with itself.
    """
    with isolated_aeat_env():
        root = Path(settings_without_env_file().cadrumo_local_storage_root)

    assert root.name.startswith(SETTINGS_STEM)
    release_settings_storage_directories()
