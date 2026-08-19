"""The routed-settings memo must survive an alternating pair of sources.

Deriving a bucket route re-validates the whole settings model and resolves
every configured directory, so the session memoises it. The memo originally
held ONE entry, on the stated premise that the access pattern is the same
source asked repeatedly.

Measurement disproved the premise. One profile field edit asks for the route
twice -- once under a settings override and once outside it -- and those two
sources alternate strictly, so each arm evicted the other and the memo served
zero hits across an entire editing session. It recomputed, every single time,
the derivation it existed to avoid.

These tests pin the working set, and the controls keep the memo honest: one
that never evicts would grow without bound, and one that ignores its key
would hand a caller another source's route.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ......core.config import Settings
from ...bucket import BucketLockedError
from .._bucket_session import _ROUTED_SETTINGS_MEMO_SIZE, BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "bafde89c-041e-4756-882b-933aaf16cad8"  # was '11111111-1111-1111-1111-111111111111'
_KEK = b"k" * 32
_DEK = b"d" * 32
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=30,
        opened_at=_NOW,
    )


def _derivations(session: BucketSession) -> int:
    """How many distinct routes the session currently holds."""
    return len(session._routed_settings)


def test_two_alternating_sources_are_both_retained(tmp_path) -> None:
    """The measured production pattern must not thrash.

    Asserted on the memo's contents rather than on a duration: a timing is a
    property of the machine, while an entry evicted by its counterpart is
    the defect itself.
    """
    session = _session()
    first = Settings(cadrumo_local_storage_root=tmp_path / "one")
    second = Settings(cadrumo_local_storage_root=tmp_path / "two")

    session.routed_settings(first)
    session.routed_settings(second)
    assert _derivations(session) == 2, "an alternating pair must both stay resident"

    held = dict(session._routed_settings)
    for _ in range(10):
        session.routed_settings(first)
        session.routed_settings(second)

    assert session._routed_settings == held, "alternating must not re-derive or evict"


def test_each_source_gets_its_own_route(tmp_path) -> None:
    """Control: the memo keys on the source, and does not serve a neighbour's route.

    Without this, a memo that returned whatever it held would satisfy the
    reuse test above while handing callers the wrong database.
    """
    session = _session()
    first = Settings(cadrumo_local_storage_root=tmp_path / "one")
    second = Settings(cadrumo_local_storage_root=tmp_path / "two")

    routed_first = session.routed_settings(first)
    routed_second = session.routed_settings(second)

    assert routed_first != routed_second
    assert session.routed_settings(first) == routed_first
    assert session.routed_settings(second) == routed_second


def test_the_memo_stays_bounded(tmp_path) -> None:
    """Control: retention is bounded, so a long session cannot grow without limit."""
    session = _session()

    for index in range(_ROUTED_SETTINGS_MEMO_SIZE + 6):
        session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / f"root-{index}"))

    assert _derivations(session) <= _ROUTED_SETTINGS_MEMO_SIZE


def test_invalidation_drops_every_retained_route(tmp_path) -> None:
    """A re-materialised bucket must not be served a route resolved before it.

    The memo resolves configured paths against the filesystem, so the
    invalidation that accompanies an engine reset has to clear ALL retained
    entries, not just the most recent one -- the reason this is a control
    and not an afterthought is that the single-slot version could only ever
    hold one, so "clear the slot" was trivially complete and stopped being
    so the moment the memo retained a set.
    """
    session = _session()
    session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "one"))
    session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "two"))
    assert _derivations(session) == 2

    session.invalidate_engine()

    assert _derivations(session) == 0, "invalidation must drop every retained route"


def test_a_sealed_session_serves_no_route(tmp_path) -> None:
    """Closing a session must not leave a usable route behind it."""
    session = _session()
    session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "one"))
    session.close()

    assert _derivations(session) == 0
    with pytest.raises(BucketLockedError):
        session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "one"))


def test_deadline_is_untouched_by_route_derivation(tmp_path) -> None:
    """Sanity: memoising a route is not an activity that extends a session.

    Guards against a future optimisation quietly touching the session to
    keep its own cache warm, which would let a busy render defeat the idle
    timeout the substrate relies on.
    """
    session = _session()
    before = session._idle_deadline

    session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "one"))
    session.routed_settings(Settings(cadrumo_local_storage_root=tmp_path / "two"))

    assert session._idle_deadline == before
    assert session._idle_deadline < _NOW + timedelta(days=1)
