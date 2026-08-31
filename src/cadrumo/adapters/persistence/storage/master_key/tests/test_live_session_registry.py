"""Tests for the process-wide live bucket-session registry.

The registry exists for exactly one property: zeroising key material a
:class:`~contextvars.ContextVar` lookup cannot reach, because it was bound on a
different thread. Every test here drives real sessions with real key buffers and
asserts on the buffers themselves, never on a call count - a sweep that "ran" but
left cleartext key bytes in memory is the failure this guards against.
"""

# INTENTIONAL: unit because "live" here names the in-process registry of open
# bucket sessions, not a live AEAT surface. These tests contact no network and
# drive real in-memory key buffers only; the filename collides with the
# test_live_* convention for AEAT tests without sharing its meaning.

from __future__ import annotations

import threading

import pytest

from ......core.time._clock import now
from .._live_sessions import (
    close_all_live_bucket_sessions,
    live_bucket_session_count,
)
from ..active_session import (
    activate_session,
    close_active_bucket_session,
)
from ..bucket_session import BucketSession

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


def _dek_bytes(session: BucketSession) -> bytes:
    """Read the session's DEK buffer directly, sealed or not.

    Going through the private buffer is deliberate: the public accessor refuses
    once sealed, and the whole question here is what the BYTES are after a
    sweep, not whether the accessor guards them.
    """
    return bytes(session._dek_buffer)


def test_open_session_registers_and_close_deregisters() -> None:
    """A live session is counted; closing it stops counting it."""
    before = live_bucket_session_count()
    session = _open_session("bucket-count")
    try:
        assert live_bucket_session_count() == before + 1
    finally:
        session.close()
    assert live_bucket_session_count() == before


def test_sweep_zeroises_a_session_bound_on_another_thread() -> None:
    """The load-bearing case: keys bound in a worker are reachable from here.

    A worker thread binds a session through ``activate_session`` and parks. The
    main thread's ContextVar sees nothing of it - asserted, so the test proves
    the blind spot is real before proving the registry closes it - and then the
    registry sweep zeroises the worker's DEK anyway.
    """
    bound = threading.Event()
    release = threading.Event()
    holder: dict[str, BucketSession] = {}

    def _worker() -> None:
        session = _open_session("bucket-worker")
        holder["session"] = session
        with activate_session(session):
            bound.set()
            release.wait(timeout=30)

    worker = threading.Thread(target=_worker, name="registry-test-worker", daemon=True)
    worker.start()
    try:
        assert bound.wait(timeout=30), "worker never bound its session"
        session = holder["session"]

        # The blind spot this registry exists for: the main thread's
        # context-scoped close cannot see the worker's binding at all.
        close_active_bucket_session()
        assert session.sealed is False, "context close unexpectedly reached another thread"
        assert _dek_bytes(session) == _DEK

        closed = close_all_live_bucket_sessions()
        assert closed >= 1
        assert session.sealed is True
        assert _dek_bytes(session) == b"\x00" * len(_DEK), "the worker's DEK was not zeroised"
    finally:
        release.set()
        worker.join(timeout=30)


def test_sweep_is_idempotent_and_survives_an_already_sealed_session() -> None:
    """Double-sweeping is safe; an already-sealed session is not re-counted."""
    session = _open_session("bucket-idempotent")
    assert close_all_live_bucket_sessions() >= 1
    assert session.sealed is True
    # Second sweep closes nothing new and must not raise.
    before = live_bucket_session_count()
    assert close_all_live_bucket_sessions() == 0
    assert live_bucket_session_count() == before


def test_registry_holds_sessions_weakly() -> None:
    """A dropped session is collected rather than pinned by the registry.

    Holding sessions strongly would keep zeroisable key buffers alive past the
    point the owning code released them - the opposite of this module's purpose.
    """
    import gc

    before = live_bucket_session_count()
    session = _open_session("bucket-weak")
    assert live_bucket_session_count() == before + 1
    del session
    gc.collect()
    assert live_bucket_session_count() == before, "the registry pinned a dropped session"
