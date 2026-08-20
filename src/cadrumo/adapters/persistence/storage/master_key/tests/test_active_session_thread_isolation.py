"""One thread's unlocked bucket session is invisible to another thread.

This is the property the whole multiuser story rests on. The active session
holds the bucket's unwrapped DEK, and it is resolved implicitly -- the
column-level encrypt path cannot be handed a session reference, so it reads
one from a ``ContextVar``. If that lookup were process-wide rather than
per-context, any thread in a long-lived process would decrypt with whichever
profile's key happened to be bound last. Both long-lived hosts here run worker
threads: the MCP transport and the TUI screens.

PEP 567 gives the isolation, so this file does not test ``contextvars``. It
tests that this substrate has not opted out of it -- with a plain ``.set()``
in :func:`bind_active_bucket_session` that outlives no block, an ``atexit``
sweep, and a live-session registry deliberately built to reach ACROSS threads,
there is more than one way for a binding to escape its context.

The interesting direction is the one that would pass vacuously. "Thread B sees
no session" is also true when the mechanism is broken and nobody sees one, so
the deliberate-propagation case is asserted alongside: a context copied with
:func:`contextvars.copy_context` and run in another thread DOES carry the
session, which is how the TUI's worker threads legitimately write. A test
suite that only proved absence would report isolation while the substrate was
simply inert.
"""

from __future__ import annotations

import threading
from contextvars import copy_context

import pytest

from ......core.time import now
from .._active_session import (
    activate_session,
    bind_active_bucket_session,
    close_active_bucket_session,
    current_active_bucket_session,
    has_active_bucket_session,
    suspend_active_session,
)
from .._bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_KEK = b"K" * 32
_DEK = b"D" * 32


def _open_session(bucket_id: str) -> BucketSession:
    """Open a real session holding real key buffers."""
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=30,
        opened_at=now(),
    )


def _observe_in_a_fresh_thread() -> tuple[bool, str | None]:
    """Return what a brand-new thread sees as the active session."""
    observed: list[tuple[bool, str | None]] = []

    def target() -> None:
        session = current_active_bucket_session()
        observed.append((has_active_bucket_session(), None if session is None else session.bucket_id))

    thread = threading.Thread(target=target, name="isolation-probe")
    thread.start()
    thread.join(timeout=10)

    assert observed, "the probe thread did not run"
    return observed[0]


def test_a_session_activated_here_is_invisible_to_a_fresh_thread() -> None:
    """DISCRIMINATING: the leak that would let one profile decrypt another's."""
    session = _open_session("aef4bd4b-2a08-454e-9e46-ad76d1928ac7")
    try:
        with activate_session(session):
            assert current_active_bucket_session() is session

            has_session, bucket_id = _observe_in_a_fresh_thread()

            assert has_session is False
            assert bucket_id is None
    finally:
        session.close()


def test_a_bare_binding_is_also_confined_to_its_thread() -> None:
    """``bind_active_bucket_session`` sets with no token, so it outlives no block.

    The contextmanager restores the previous value on exit; this one does not,
    which makes it the likelier of the two to escape. It is the call the login
    path uses, so its confinement is asserted separately rather than assumed
    from the contextmanager's.
    """
    session = _open_session("1b6da8e1-3c2f-4d5a-8e7b-9f0a1c2d3e4f")
    try:
        bind_active_bucket_session(session)
        assert current_active_bucket_session() is session

        has_session, bucket_id = _observe_in_a_fresh_thread()

        assert has_session is False
        assert bucket_id is None
    finally:
        close_active_bucket_session()


def test_a_deliberately_copied_context_does_carry_the_session() -> None:
    """ANTI-VACUITY: absence must not be the only thing this file can observe.

    "The other thread sees nothing" is equally true of a substrate where
    nothing is ever bound at all. This is the direction the TUI depends on --
    a worker thread running a copied context performs the operator's own
    writes -- so proving it carries the session proves the assertions above
    are observing a real binding rather than an inert one.
    """
    session = _open_session("2c7eb9f2-4d3a-4e6b-9f8c-0a1b2c3d4e5f")
    carried: list[str | None] = []

    def target() -> None:
        active = current_active_bucket_session()
        carried.append(None if active is None else active.bucket_id)

    try:
        with activate_session(session):
            context = copy_context()
            thread = threading.Thread(target=lambda: context.run(target), name="carried-probe")
            thread.start()
            thread.join(timeout=10)
    finally:
        session.close()

    assert carried == ["2c7eb9f2-4d3a-4e6b-9f8c-0a1b2c3d4e5f"]


def test_two_threads_hold_different_sessions_at_the_same_time() -> None:
    """Concurrent profiles must not overwrite one another's binding.

    TWO barriers, and the second one is the test. With only the first, both
    threads are merely bound at the same moment -- but the faster one can read,
    LEAVE its block, and have its unwind restore the slower one's value before
    the slower one reads. That sequence was observed against a deliberately
    broken substrate: a process-wide global passed this test, because the
    restore-on-exit handed the second reader exactly the answer isolation
    would have given it.

    The second barrier removes the scheduling luck. Neither block may unwind
    until both reads are done, so on a shared holder both reads necessarily
    return the last value written and the distinct expectation below fails.
    """
    first = _open_session("0f5cf7d0-9f8e-4b17-9a3d-6c1f2e8a4b71")
    second = _open_session("3d8fcab3-5e4b-4f7c-a09d-1b2c3d4e5f60")
    both_bound = threading.Barrier(2, timeout=10)
    both_read = threading.Barrier(2, timeout=10)
    seen: dict[str, str | None] = {}

    def hold(session: BucketSession, label: str) -> None:
        with activate_session(session):
            both_bound.wait()
            active = current_active_bucket_session()
            seen[label] = None if active is None else active.bucket_id
            both_read.wait()

    threads = [
        threading.Thread(target=hold, args=(first, "first"), name="holder-first"),
        threading.Thread(target=hold, args=(second, "second"), name="holder-second"),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
    finally:
        first.close()
        second.close()

    assert seen == {
        "first": "0f5cf7d0-9f8e-4b17-9a3d-6c1f2e8a4b71",
        "second": "3d8fcab3-5e4b-4f7c-a09d-1b2c3d4e5f60",
    }


def test_suspending_hides_the_session_and_restores_it() -> None:
    """The explicit un-binding boundary, in both directions."""
    session = _open_session("4e90dbc4-6f5c-4a8d-b1ae-2c3d4e5f6071")
    try:
        with activate_session(session):
            with suspend_active_session():
                assert has_active_bucket_session() is False

            assert current_active_bucket_session() is session
    finally:
        session.close()
