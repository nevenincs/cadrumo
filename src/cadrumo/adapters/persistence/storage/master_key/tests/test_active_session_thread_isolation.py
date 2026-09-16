"""The two binding scopes, and which threads each one reaches.

The active session holds the bucket's unwrapped DEK and is resolved
implicitly -- the column-level encrypt path cannot be handed a session
reference, so it reads one from the module's binding. This file pins which
threads that read reaches, because the two binding doors deliberately answer
differently and conflating them has produced a defect in each direction.

:func:`activate_session` is SCOPED. It shadows the binding for one span of
work and unwinds on exit, so a span that bridges into a staged bucket cannot
be observed by a sibling thread and cannot leak past its own ``with``. That
isolation is what lets two spans hold different profiles at the same instant,
and it is PEP 567's, so the tests below do not test ``contextvars`` -- they
test that this substrate has not opted out of it, which an ``atexit`` sweep
and a live-session registry built to reach ACROSS threads both give it ways
to do.

:func:`bind_active_bucket_session` is UNSCOPED and process-wide, because what
it publishes is a fact about the process rather than about a span: exactly one
profile is logged in, and the login door closes any other live session before
publishing. A credential surface that authenticates on a Textual thread
worker, or inside its own :func:`asyncio.run` frame, must be observable from
the frame that reads storage afterwards -- and under a plain ``ContextVar``
it was not, which reached the operator as a correct login followed by a
workbench that could not find the profile it had just unlocked.

The absence assertions are paired with propagation assertions on purpose.
"The other thread sees nothing" is equally true of a substrate where nothing
is ever bound at all, so a file that only proved absence would report
isolation while the substrate was simply inert.
"""

from __future__ import annotations

import threading
from contextvars import copy_context
from datetime import timedelta

import pytest

from ......core.time.clock import now
from ..active_session import (
    activate_session,
    bind_active_bucket_session,
    close_active_bucket_session,
    current_active_bucket_session,
    has_active_bucket_session,
    suspend_active_session,
)
from ..bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_DEK = b"D" * 32


def _open_session(bucket_id: str) -> BucketSession:
    """Open a real session holding real key buffers."""
    _opened_at = now()
    return BucketSession.open_resumed(
        bucket_id=bucket_id,
        dek=_DEK,
        idle_minutes=30,
        opened_at=_opened_at,
        idle_deadline=_opened_at + timedelta(minutes=30),
        absolute_deadline=_opened_at + timedelta(minutes=240),
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


def test_a_bare_binding_is_the_whole_process_s_answer() -> None:
    """``bind_active_bucket_session`` publishes the process's login, not a span's.

    The contextmanager restores the previous value on exit; this door has no
    block to unwind and is not meant to have one. It is the call the login
    path uses, and who is logged in is a property of the process: a fresh
    thread that asks must be told the same thing the binding thread would be
    told, or the CLI and the TUI answer the operator differently about the
    same login.

    This is the assertion that flipped. It previously demanded confinement,
    which made a login performed on a Textual thread worker invisible to the
    workbench that ran next. Confinement remains available and remains tested
    -- it is what :func:`activate_session` provides -- but it is not what this
    door means.
    """
    session = _open_session("1b6da8e1-3c2f-4d5a-8e7b-9f0a1c2d3e4f")
    try:
        bind_active_bucket_session(session)
        assert current_active_bucket_session() is session

        has_session, bucket_id = _observe_in_a_fresh_thread()

        assert has_session is True
        assert bucket_id == "1b6da8e1-3c2f-4d5a-8e7b-9f0a1c2d3e4f"
    finally:
        close_active_bucket_session()


def test_a_binding_made_on_a_worker_thread_reaches_the_thread_that_reads_next() -> None:
    """DISCRIMINATING: the TUI's actual shape, in the direction that was broken.

    Textual runs a credential door on a thread worker, under a context copied
    from the screen's own, and every context write made there is discarded
    when that context ends. The login must survive it, because the surface
    that composes the workbench reads the binding from a different frame
    entirely.
    """
    session = _open_session("5a1c3e7d-8b2f-4c6a-9d0e-1f2a3b4c5d6e")
    bound = threading.Barrier(2, timeout=10)

    def authenticate_on_worker() -> None:
        copy_context().run(bind_active_bucket_session, session)
        bound.wait()

    worker = threading.Thread(target=authenticate_on_worker, name="credential-worker")
    try:
        worker.start()
        bound.wait()
        worker.join(timeout=10)

        active = current_active_bucket_session()
        assert active is session
        assert _observe_in_a_fresh_thread() == (True, "5a1c3e7d-8b2f-4c6a-9d0e-1f2a3b4c5d6e")
    finally:
        close_active_bucket_session()


def test_closing_a_process_binding_from_inside_a_span_evicts_it_everywhere() -> None:
    """A retired session must not be resurrected by the span's own unwind.

    Closing zeroises in place, so a sealed session that survives as the value
    the next caller reads is worse than no binding at all: it is advertised as
    live and fails deep inside a decrypt. A token reset restoring the retired
    object is exactly how that happened, so the eviction is asserted to reach
    both the span's shadow and the process value.
    """
    session = _open_session("6b2d4f8e-9c3a-4d7b-8e1f-2a3b4c5d6e7f")
    bind_active_bucket_session(session)

    with activate_session(session):
        close_active_bucket_session()
        assert current_active_bucket_session() is None

    assert current_active_bucket_session() is None
    assert session.sealed is True
    assert _observe_in_a_fresh_thread() == (False, None)


def test_closing_a_scoped_session_leaves_the_process_login_intact() -> None:
    """Eviction is identity-scoped: a span's close must not log the operator out."""
    logged_in = _open_session("7c3e5a9f-0d4b-4e8c-9f2a-3b4c5d6e7f80")
    bridged = _open_session("8d4f6b0a-1e5c-4f9d-a03b-4c5d6e7f8091")
    bind_active_bucket_session(logged_in)

    try:
        with activate_session(bridged):
            close_active_bucket_session()
            assert current_active_bucket_session() is None

        assert current_active_bucket_session() is logged_in
        assert bridged.sealed is True
        assert logged_in.sealed is False
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


def test_two_spans_hold_different_sessions_at_the_same_time() -> None:
    """Concurrent scoped spans must not overwrite one another's binding.

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
