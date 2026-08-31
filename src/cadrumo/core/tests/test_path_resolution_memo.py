"""Resolving a configured path twice must not hit the filesystem twice.

``Settings`` re-derives every configured path field on every construction,
and a construction happens several times per operator action, so the same
handful of paths were resolved over and over. ``Path.resolve`` is a syscall:
on Windows it walks each component through ``nt._getfinalpathname``. One
profile field edit measured 424 of those calls, none of which could return a
different answer than the call before it.

These tests pin the memo, and the controls keep it honest. A memo is easy to
make look right and be wrong in two opposite ways -- one that never caches
still passes a correctness assertion, and one that never invalidates serves a
stale location forever -- so the reuse test is paired with a control proving
a real resolution still happens when the cache is empty, and an invalidation
test proving entries can be dropped.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ..config_state_root import StateRootInputs, platform_user_data_root
from ..paths import _resolved_path, clear_resolved_path_cache, resolve_project_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(autouse=True)
def _empty_cache():
    """Start every test from an empty memo, and leave one behind.

    The memo is process-wide, so a test that inherited a warm entry from an
    earlier test would measure the earlier test's work.
    """
    clear_resolved_path_cache()
    yield
    clear_resolved_path_cache()


def _misses() -> int:
    return _resolved_path.cache_info().misses


def test_repeated_resolution_of_one_path_touches_the_filesystem_once(tmp_path: Path) -> None:
    """The second and later resolutions are served from the memo.

    Counted at the memo rather than timed: a duration is a property of the
    machine, while a miss is the syscall itself.
    """
    target = tmp_path / "cadrumo-storage" / "buckets"

    before = _misses()
    first = resolve_project_path(target)
    after_first = _misses()

    for _ in range(20):
        resolve_project_path(target)
    after_many = _misses()

    assert after_first - before == 1, "the first resolution must actually resolve"
    assert after_many == after_first, "later resolutions must not re-enter the filesystem"
    assert first == resolve_project_path(target)


def test_an_empty_cache_really_resolves(tmp_path: Path) -> None:
    """Control: the memo is not simply never consulted.

    Without this, a broken memo that returned a constant -- or a test that
    measured a counter nothing increments -- would satisfy the reuse test.
    """
    target = tmp_path / "control"

    resolve_project_path(target)
    warm = _misses()
    resolve_project_path(target)
    assert _misses() == warm, "sanity: the warm path must not miss"

    # ``cache_clear`` resets the counters too, so the post-invalidation miss
    # is counted from zero rather than added to the warm total.
    clear_resolved_path_cache()
    assert _misses() == 0
    resolve_project_path(target)
    assert _misses() == 1, "after invalidation the path must be resolved again"


def test_memo_agrees_with_an_uncached_resolution(tmp_path: Path) -> None:
    """The cached answer equals what the filesystem would have said.

    Compared against ``Path.resolve`` directly rather than against a second
    call to the function under test, so the assertion cannot be satisfied by
    the memo agreeing with itself.
    """
    for name in ("plain", "MiXeD", "with space", "deep/nest/leaf"):
        candidate = tmp_path / name
        clear_resolved_path_cache()
        cold = resolve_project_path(candidate)
        warm = resolve_project_path(candidate)
        assert cold == warm
        assert warm == Path(candidate).expanduser().resolve()


def test_creating_a_path_after_resolving_it_does_not_change_its_location(tmp_path: Path) -> None:
    """The case the memo is exposed to in production is safe.

    Configured directories are routinely resolved before they exist and
    created afterwards. Were creation to change a path's resolution, a
    memo filled during the first construction would pin the pre-creation
    form; this pins that it does not.
    """
    target = tmp_path / "created" / "later"

    before = resolve_project_path(target)
    target.mkdir(parents=True)
    clear_resolved_path_cache()

    assert resolve_project_path(target) == before


def test_relative_and_absolute_paths_of_the_same_name_do_not_collide(tmp_path: Path) -> None:
    """One memo serves both arms, so the key must be the composed path.

    A key built from the caller's argument would let the relative override
    ``logs`` and an absolute ``/…/logs`` share an entry.
    """
    inputs = StateRootInputs(
        platform=sys.platform,
        environ={},
        home=tmp_path / "home",
    )
    anchor = platform_user_data_root(inputs)

    relative = resolve_project_path("probe-logs", state_root_inputs=inputs)
    absolute = resolve_project_path(tmp_path / "probe-logs")

    assert relative == (anchor / "probe-logs").resolve()
    assert absolute == (tmp_path / "probe-logs").resolve()
    assert relative != absolute


def _bind_directory(link: Path, target: Path) -> None:
    """Make ``link`` resolve to ``target``, by whichever mechanism the OS allows.

    This replaces a ``pytest.skip`` that fired whenever ``os.symlink`` was
    refused. That skip was reached for a reason narrower than it looked:
    Windows withholds SYMLINK creation without developer mode or elevation,
    but a directory JUNCTION needs neither and rebinds resolution identically
    — which is why :func:`clear_resolved_path_cache` names both. Only symlink
    had been tried, so the one test pinning the invalidation contract quietly
    did not run on any ordinary Windows workstation.

    Falls through to a hard failure rather than a skip when no mechanism is
    available: a deterministic test that cannot establish its precondition has
    to say so, not report success it did not earn.
    """
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        if sys.platform != "win32":
            raise
        import _winapi

        create_junction = getattr(_winapi, "CreateJunction", None)
        if create_junction is None:  # pragma: no cover - absent only on non-CPython builds
            raise
        create_junction(str(target), str(link))


def test_invalidation_is_required_when_a_directory_is_rebound(tmp_path: Path) -> None:
    """The one case that genuinely invalidates a memo entry.

    Replacing a real directory with a link to a different target is the only
    measured way a path's resolution changes underneath a live process --
    creating, deleting, and re-creating a directory at the same location all
    leave it resolving where it did. This pins WHY
    :func:`clear_resolved_path_cache` exists: without the call the stale
    entry survives, and with it the new target is seen.
    """
    real = tmp_path / "real-target"
    real.mkdir()
    swap = tmp_path / "swap"
    swap.mkdir()

    before = resolve_project_path(swap)
    swap.rmdir()
    _bind_directory(swap, real)

    assert resolve_project_path(swap) == before, "the stale entry is what the memo is for"

    clear_resolved_path_cache()
    assert resolve_project_path(swap) == real.resolve(), "invalidation must expose the new target"
