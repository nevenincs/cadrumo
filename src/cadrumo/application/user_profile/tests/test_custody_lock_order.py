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

HOW THE ORDER IS OBSERVED, WITHOUT PATCHING ANYTHING. An earlier version of
this module wrapped the lock primitive to record each path. That wrapper
delegated to the real implementation and faked nothing, but it was still
monkeypatch machinery in a deterministic test, which this project forbids
outright -- and the ratchet that says so lives in `dev/tests`, which no
per-push lane runs, so it went unreported.

Real contention answers the same question without touching the code under
test. A sibling PROCESS holds the ROOT lock; a thread here then enters the
transaction and must block. While it is blocked, this process acquires the
PROFILE lock itself. That acquisition SUCCEEDING is the proof: had the
transaction taken the profile lock first, the lock would already be held and
the probe would fail. The probe is a real acquisition of the real file lock,
and on Windows the primitive opens its leaf with no sharing, so a second
acquire fails even from the same process -- which is what makes the probe
discriminating rather than decorative.

An empirical sweep over the custody suites (583 tests, 95 real acquisitions, 61
of them nested) found every nesting already in the declared order. This keeps
it that way.
"""

from __future__ import annotations

import multiprocessing as mp
import threading
from queue import Empty
from typing import TYPE_CHECKING, Any
from uuid import UUID

import pytest

from ....adapters.persistence.storage import custody
from ....core import StorageCategory, storage_location
from ....core.paths import effective_storage_root
from cadrumo.application.user_profile.custody_repository import profile_custody_transaction_lock

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("aef4bd4b-2a08-454e-9e46-ad76d1928ac7")

#: Long enough that a real acquisition wins, short enough that a HELD lock
#: reports quickly rather than hanging the suite for the 30 s default.
_PROBE_SECONDS = 3.0

#: How long the blocked transaction is given to prove it is genuinely blocked.
_BLOCKED_WINDOW_SECONDS = 1.0


def _profile_lock_path(root: Path) -> Path:
    """Resolve the per-profile lock leaf exactly as the transaction does."""
    capsules_root = effective_storage_root(root) / storage_location(StorageCategory.BUCKETS).relative_path()
    return capsules_root / f".profile-custody-{_PROFILE_ID}.lock"


def _hold_root_lock_in_sibling(root_text: str, release_event: Any, result_queue: Any) -> None:
    """Hold ONLY the root lock in a separate interpreter.

    Only the root lock, deliberately: holding the whole transaction would also
    hold the profile lock, and then the probe below could not distinguish "the
    transaction under test took it" from "the sibling took it".

    ``ready`` is published before the acquisition so a caller timing the
    contention window is not timing a Windows spawn plus a cadrumo import.
    """
    from pathlib import Path as _Path

    from ....adapters.persistence.storage import custody as _custody
    from ....core.paths import effective_storage_root as _effective_root

    result_queue.put("ready")
    with _custody.profile_custody_root_lock(_effective_root(_Path(root_text))):
        result_queue.put("locked")
        release_event.wait(30)


def _await(queue: Any, expected: str, *, timeout: float = 30.0) -> None:
    """Block until ``expected`` arrives, failing the test rather than hanging."""
    try:
        received = queue.get(timeout=timeout)
    except Empty:  # pragma: no cover - only on a genuinely wedged sibling
        pytest.fail(f"sibling never published {expected!r}")
    assert received == expected, f"expected {expected!r} from the sibling, got {received!r}"


def test_the_root_lock_is_taken_before_the_profile_lock(tmp_path: Path) -> None:
    """DISCRIMINATING: the inversion two operators would deadlock on.

    Proven against real file locks in two processes: no wrapper, no patch, and
    every acquisition below is the production primitive doing its real work.
    """
    # The transaction creates this directory itself, but only AFTER taking the
    # root lock -- so while it is blocked the probe would have no parent to
    # anchor against and would fail for the wrong reason. Creating it here is
    # what the transaction would do anyway, and it is idempotent.
    _profile_lock_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)

    context = mp.get_context("spawn")
    release_root = context.Event()
    from_sibling = context.Queue()
    sibling = context.Process(
        target=_hold_root_lock_in_sibling,
        args=(str(tmp_path), release_root, from_sibling),
    )
    sibling.start()
    entered = threading.Event()

    def _enter_transaction() -> None:
        with profile_custody_transaction_lock(tmp_path, _PROFILE_ID):
            entered.set()

    transaction = threading.Thread(target=_enter_transaction, daemon=True)
    try:
        _await(from_sibling, "ready")
        _await(from_sibling, "locked")
        transaction.start()

        assert not entered.wait(_BLOCKED_WINDOW_SECONDS), (
            "the transaction entered while a sibling process held the ROOT lock, so it is not "
            "taking the root lock first -- or not taking it at all"
        )

        # The proof. A free profile lock means the blocked transaction has not
        # taken it, so root is genuinely first. Released before the root lock
        # is, or the transaction would block again on this very handle.
        with custody.profile_custody_local_lock(_profile_lock_path(tmp_path), timeout_seconds=_PROBE_SECONDS):
            pass
    finally:
        release_root.set()
        sibling.join(timeout=30)
        transaction.join(timeout=30)

    assert entered.is_set(), "the transaction never completed once the root lock was released"


def test_the_probe_fails_when_the_profile_lock_is_genuinely_held(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the probe must be able to say "held".

    The assertion above is an acquisition SUCCEEDING. If this lock were freely
    re-acquirable -- a re-entrant primitive, a path that never really locks --
    that success would mean nothing and the test would pass against an inverted
    implementation. This holds the same leaf and requires a second acquire to
    refuse.
    """
    target = _profile_lock_path(tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    # The TYPE is named rather than accepting any exception. A bare
    # `pytest.raises(Exception)` is satisfied by a missing parent directory, a
    # typo in the leaf path, or an import error in the primitive -- every one of
    # which would let this proof pass while proving nothing about exclusivity.
    # Determined by observation, not assumption: the second acquire raises
    # `ProfileCustodyRecordError("local custody lock cannot be exclusively
    # opened")`.
    #
    # The MESSAGE is matched as well as the type, because this one class
    # carries ten distinct refusals in the lock module alone -- a non-positive
    # timeout, absent flock support, a leaf that is a reparse point, an
    # identity-verification failure. Any of those satisfies the bare type while
    # saying nothing about exclusivity, and a later edit passing
    # `timeout_seconds=0` here would keep this proof green having tested
    # argument validation instead. Both the POSIX and Windows paths raise this
    # same wording, so the match is platform-neutral. Matching the message is
    # the established practice for this class in `custody/tests/test_capsule.py`.
    with (
        custody.profile_custody_local_lock(target, timeout_seconds=_PROBE_SECONDS),
        pytest.raises(custody.ProfileCustodyRecordError, match="cannot be exclusively opened"),
        custody.profile_custody_local_lock(target, timeout_seconds=0.5),
    ):
        pass


def test_the_profile_lock_names_the_profile_it_scopes(tmp_path: Path) -> None:
    """ANTI-VACUITY: the second lock must be per-profile, not a second root.

    Ordering is only worth asserting if the two locks are genuinely different
    subjects. If the profile-scoped lock ever collapsed onto one shared path,
    every profile would serialise against every other and the assertion above
    would still pass. Observed from the filesystem: entering the transaction
    materialises the leaf, and its name carries the profile id.
    """
    with profile_custody_transaction_lock(tmp_path, _PROFILE_ID):
        target = _profile_lock_path(tmp_path)

        assert target.is_file(), f"the per-profile lock leaf was never materialised at {target}"
        assert str(_PROFILE_ID) in target.name
        assert target.name != ".profile-custody-root.lock"
