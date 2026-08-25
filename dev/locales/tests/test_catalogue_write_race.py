"""Concurrent catalogue edits must not silently discard one another.

Every catalogue edit is a read-modify-write over a whole file. Two overlapping
edits both read the same base and both write, so the first writer's change
disappears with no error: inter-locale parity checks key *presence*, never
value correctness, so a lost value edit restores stale operator-facing prose
with every gate green.

These exercise the real manager against real files with real concurrency: no
test doubles, no patched clocks, and no sequential stand-in for a race.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from .._write_guard import LOCK_FILENAME, catalogue_write_guard
from ..errors import LocaleError, LocaleWriteConflictError
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_WRITERS = 4
_EDITS_PER_WRITER = 12


def _catalogue_body(leaf_count: int) -> dict[str, dict[str, str]]:
    """Build a catalogue big enough that a read-modify-write takes real time."""
    return {"cli": {f"seed_{index:04d}": f"value {index}" for index in range(leaf_count)}}


@pytest.fixture
def manager(tmp_path: Path) -> LocaleManager:
    """A manager over a real, non-trivial catalogue set in ``tmp_path``."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    for locale in _LOCALES:
        (locales_dir / f"{locale}.yml").write_text(
            yaml.dump(_catalogue_body(400), allow_unicode=True, sort_keys=True, default_flow_style=False),
            encoding="utf-8",
        )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    return LocaleManager(src_dir, locales_dir)


def _read_leaves(path: Path) -> dict[str, str]:
    """Return the ``cli`` namespace of a catalogue as a flat mapping."""
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(loaded["cli"])


def test_concurrent_writers_do_not_lose_each_others_edits(manager: LocaleManager) -> None:
    """Four real threads editing one catalogue must all survive.

    This is the load-bearing test. Without serialisation the writers interleave
    their read-modify-write cycles and the losers' keys are simply absent from
    the final file.
    """
    target = manager.locales_dir / "en.yml"
    start = threading.Barrier(_WRITERS)
    expected: set[str] = set()

    def edit(writer: int) -> None:
        start.wait(timeout=30)
        for index in range(_EDITS_PER_WRITER):
            manager.set_locale_value("en", f"cli.w{writer}_{index:03d}", f"writer {writer} edit {index}")

    for writer in range(_WRITERS):
        expected.update(f"w{writer}_{index:03d}" for index in range(_EDITS_PER_WRITER))

    with ThreadPoolExecutor(max_workers=_WRITERS) as pool:
        for future in [pool.submit(edit, writer) for writer in range(_WRITERS)]:
            future.result(timeout=180)

    written = _read_leaves(target)
    missing = sorted(key for key in expected if key not in written)
    assert missing == [], f"{len(missing)} concurrent edit(s) were silently discarded: {missing[:10]}"
    assert len(written) == 400 + len(expected), "a concurrent write dropped pre-existing catalogue content"


def test_write_is_refused_when_the_file_moved_under_the_edit(manager: LocaleManager) -> None:
    """A writer that never took the lock must not be silently overwritten.

    A hand edit or an editor save cannot be excluded by any lock, so the guard
    fingerprints what it read and refuses to replace bytes it never saw.
    """
    target = manager.locales_dir / "en.yml"

    with catalogue_write_guard(manager.locales_dir) as guard:
        text = guard.read_text(target)
        target.write_text(text + "outsider:\n  key: 'landed first'\n", encoding="utf-8")

        with pytest.raises(LocaleWriteConflictError, match="changed while this edit was in flight"):
            guard.write_text(target, text + "mine:\n  key: 'would clobber'\n")

    assert "landed first" in target.read_text(encoding="utf-8")
    assert "would clobber" not in target.read_text(encoding="utf-8")


def test_write_without_a_paired_read_is_refused(manager: LocaleManager) -> None:
    """A write path that bypasses the guard's read must fail loudly.

    Without this the guard would silently degrade to an unchecked write the
    moment a new writer forgot to read through it.
    """
    target = manager.locales_dir / "en.yml"

    with catalogue_write_guard(manager.locales_dir) as guard, pytest.raises(LocaleError, match="not read through"):
        guard.write_text(target, "cli:\n  a: 'b'\n")


def test_a_lock_left_by_a_dead_process_is_reclaimed(manager: LocaleManager) -> None:
    """A crashed writer must not wedge the catalogues permanently."""
    lock = manager.locales_dir / LOCK_FILENAME
    # PID 0 is never a live user process on any supported platform, and
    # ``pid_is_alive`` rejects it without probing the OS.
    lock.write_text("0", encoding="utf-8")

    manager.set_locale_value("en", "cli.after_crash", "recovered")

    assert _read_leaves(manager.locales_dir / "en.yml")["after_crash"] == "recovered"
    assert not lock.exists(), "the lock must be released after the cycle completes"


def test_a_live_holder_is_waited_out_then_refused(manager: LocaleManager) -> None:
    """A lock held by this live process must block a second cycle, not be stolen."""
    with (
        catalogue_write_guard(manager.locales_dir),
        pytest.raises(LocaleError, match="Timed out"),
        catalogue_write_guard(manager.locales_dir, wait_seconds=0.2),
    ):
        pytest.fail("the second cycle must not acquire a lock this process still holds")

    assert not (manager.locales_dir / LOCK_FILENAME).exists()
