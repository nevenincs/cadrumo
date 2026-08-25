"""Tests for the shared trash-rename-then-remove primitive.

:func:`~cadrumo.adapters.persistence.storage.bucket.trash_rename_and_remove`
converges the two hand-rolled bucket-directory removal implementations that
prompted it: one in :mod:`cadrumo.application.user_profile.profile_repository`,
and one in a ``_orchestration`` module that has since been removed. These tests
pin both the rename-succeeds and rename-fails branches, and both
``on_trash_cleanup_error`` policies, against a real filesystem — no mocks.

The rename-fails branch is reproduced with a genuinely held-open file handle
inside the target directory, which Windows refuses to rename out from under
(``WinError 5: Access is denied``) — the same real-world shape the
docstring's SQLite-handle scenario describes, not a simulated failure.
``test_rename_fails_falls_back_and_the_fallback_succeeds`` additionally
reproduces the *release* half of that shape: the blocking handle is only
reachable through a reference cycle, so ordinary refcounting cannot free it
— only the ``gc.collect()`` the primitive itself runs, after the rename
fails, actually closes it. If that ``gc.collect()`` call were ever dropped,
this specific test (unlike the others, which hold the handle open for the
whole call) would start failing.
"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import BinaryIO

import pytest

from ......core.directory_scan import scan_directory
from .._layout import trash_rename_and_remove

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _make_target(tmp_path: Path, *, name: str = "target") -> Path:
    target = tmp_path / name
    target.mkdir()
    (target / "payload.txt").write_bytes(b"contents")
    return target


class _CycleHolder:
    """Keeps a file handle open until the cycle collector reaps it.

    A plain local variable holding the handle would close it (via
    refcounting) the moment the test function's frame is done with it, which
    would make the rename attempt racy rather than deterministic. Wiring a
    self-reference forces CPython's reference counting to leave it alone —
    only an explicit ``gc.collect()`` (either the test's own, or, in
    ``test_rename_fails_falls_back_and_the_fallback_succeeds``, the one
    :func:`~cadrumo.adapters.persistence.storage.bucket.trash_rename_and_remove`
    runs internally after the rename fails) reclaims it and closes the
    handle.
    """

    def __init__(self, handle: BinaryIO) -> None:
        self.handle = handle
        self.self_ref = self

    def __del__(self) -> None:
        self.handle.close()


# --------------------------------------------------------------------- #
# Rename succeeds                                                       #
# --------------------------------------------------------------------- #


def test_rename_succeeds_removes_the_directory(tmp_path: Path) -> None:
    target = _make_target(tmp_path)

    trash_rename_and_remove(target)

    assert not target.exists()
    # No trash sibling survives either -- the successful-rename path removes
    # the renamed directory, it does not leave it behind.
    assert scan_directory(tmp_path) == ()


def test_rename_succeeds_ignore_policy_also_removes_it(tmp_path: Path) -> None:
    """The "ignore" policy does not change the ordinary success-path outcome."""
    target = _make_target(tmp_path)

    trash_rename_and_remove(target, on_trash_cleanup_error="ignore")

    assert not target.exists()
    assert scan_directory(tmp_path) == ()


# --------------------------------------------------------------------- #
# Rename fails: a real held-open file handle blocks it (WinError 5)      #
# --------------------------------------------------------------------- #


def test_rename_fails_falls_back_and_the_fallback_succeeds(tmp_path: Path) -> None:
    """A held handle blocks the rename; once ``gc.collect()`` frees it, the in-place removal succeeds.

    Reproduces the exact production shape: a lingering reference (a
    cached SQLite engine handle, here a reference cycle) blocks the rename,
    and the primitive's own post-failure ``gc.collect()`` -- not the test --
    is what releases it in time for the in-place ``rmtree`` fallback to
    actually succeed.
    """
    target = _make_target(tmp_path)
    handle = (target / "payload.txt").open("rb")
    holder: _CycleHolder | None = _CycleHolder(handle)
    del holder  # only reachable via its own cycle now
    assert not handle.closed  # refcounting alone did not free it

    trash_rename_and_remove(target)

    assert not target.exists()
    assert handle.closed  # freed by the primitive's internal gc.collect()


def test_rename_fails_raise_policy_propagates_the_in_place_removal_failure(tmp_path: Path) -> None:
    """``on_trash_cleanup_error="raise"`` (the default) surfaces a genuine in-place removal failure.

    Both the rename AND the in-place ``rmtree`` are blocked by the same
    held-open handle (kept alive for the whole call, unlike the
    ``gc.collect()``-recoverable scenario above), so the fallback's own
    removal genuinely fails and must propagate -- the create-rollback
    caller's load-bearing contract.
    """
    target = _make_target(tmp_path)
    held = (target / "payload.txt").open("rb")
    try:
        with pytest.raises(OSError):
            trash_rename_and_remove(target, on_trash_cleanup_error="raise")
    finally:
        held.close()
        gc.collect()

    # The directory survives (genuinely not removed) once the handle is
    # released by test cleanup.
    assert target.exists()


def test_rename_fails_ignore_policy_swallows_the_in_place_removal_failure(tmp_path: Path) -> None:
    """``on_trash_cleanup_error="ignore"`` never raises, even when nothing was actually removed."""
    target = _make_target(tmp_path)
    held = (target / "payload.txt").open("rb")
    try:
        trash_rename_and_remove(target, on_trash_cleanup_error="ignore")  # must not raise
    finally:
        held.close()
        gc.collect()

    # The directory (still holding the file that blocked both removal
    # attempts) genuinely survives -- "ignore" tolerates leftover litter,
    # it does not pretend the removal happened.
    assert target.exists()


def test_raise_policy_is_the_default(tmp_path: Path) -> None:
    """Calling with no explicit policy behaves identically to ``"raise"`` on the ordinary success path."""
    target = _make_target(tmp_path)

    trash_rename_and_remove(target)  # default policy, ordinary success path

    assert not target.exists()
