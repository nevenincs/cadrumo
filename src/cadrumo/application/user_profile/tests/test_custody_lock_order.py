"""The custody transaction takes the root lock before the profile lock.

`profile_custody_transaction_lock` states the invariant in one line -- "acquire
root then profile lock, the only accepted custody lock order" -- and nothing
enforced it. A lock ORDER is not a style preference: two processes that take
the same pair in opposite orders deadlock, and neither one is doing anything
individually wrong. The failure needs two operators, real contention and
unlucky timing, so it is close to unreproducible once shipped and invisible in
every single-process test.

Both locks are the same primitive over different PATHS -- the root lock is
`profile_custody_local_lock` on `.profile-custody-root.lock` -- so nothing in
the type system distinguishes them and nothing stops a future caller taking
them the other way round.

WHY THIS OBSERVES RATHER THAN SUBSTITUTES. The wrapper below records each lock
path and then delegates to the REAL implementation, which really acquires the
real file locks; nothing is faked and no acquisition is skipped. The recording
is the only addition. Order cannot be read off the filesystem afterwards --
both files exist once the block is entered, and which was created first is not
retained -- so observing the calls is what makes the invariant assertable at
all.

An empirical sweep over the custody suites (583 tests, 95 real acquisitions, 61
of them nested) found every nesting already in the declared order. This test
keeps it that way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage import custody
from ....adapters.persistence.storage.custody import _filesystem
from .._custody_repository import profile_custody_transaction_lock

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT_LOCK_NAME = ".profile-custody-root.lock"
_PROFILE_ID = UUID("aef4bd4b-2a08-454e-9e46-ad76d1928ac7")


def _recorded_lock_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    """Run the real transaction lock, returning the lock names in order taken."""
    taken: list[str] = []
    real_lock = _filesystem.profile_custody_local_lock

    def observing_lock(path: Path, **kwargs: object):
        taken.append(path.name)
        return real_lock(path, **kwargs)

    # Patched in BOTH places the primitive is reached from, which is the whole
    # difficulty: `profile_custody_root_lock` is itself a local lock, and it
    # calls the primitive through its OWN module global rather than the facade
    # attribute. Observing only the facade saw the profile lock and missed the
    # root acquisition entirely -- reporting an inversion that was not there.
    monkeypatch.setattr(_filesystem, "profile_custody_local_lock", observing_lock)
    monkeypatch.setattr(custody, "profile_custody_local_lock", observing_lock)

    with profile_custody_transaction_lock(tmp_path, _PROFILE_ID):
        pass
    return tuple(taken)


def test_the_root_lock_is_taken_before_the_profile_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DISCRIMINATING: the inversion two operators would deadlock on."""
    order = _recorded_lock_order(tmp_path, monkeypatch)

    assert order, "no lock was taken; the transaction lock is not reaching the custody primitive"
    assert order[0] == _ROOT_LOCK_NAME, (
        f"the custody transaction took {order[0]!r} before the root lock. Two processes taking this "
        "pair in opposite orders deadlock, and the declared order is root first."
    )
    profile_locks = [name for name in order if name.startswith(".profile-custody-") and name != _ROOT_LOCK_NAME]
    assert profile_locks, "the profile-scoped lock was never taken"
    assert order.index(_ROOT_LOCK_NAME) < order.index(profile_locks[0])


def test_the_profile_lock_names_the_profile_it_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ANTI-VACUITY: the second lock must be per-profile, not a second root.

    Ordering is only worth asserting if the two locks are genuinely different
    subjects. If the profile-scoped lock ever collapsed onto one shared path,
    every profile would serialise against every other and the assertion above
    would still pass.
    """
    order = _recorded_lock_order(tmp_path, monkeypatch)

    assert f".profile-custody-{_PROFILE_ID}.lock" in order
