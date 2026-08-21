"""A provider closes the session it owns, and never the one someone else bound.

``exit_provider_session`` states the property in its own docstring: if another
boundary already replaced the active binding, only the CAPTURED session is
closed and a different current session is never evicted. Nothing checked it --
the module sat at 32% line coverage, which is to say the body was unexecuted.

The property matters because the process is long-lived and the binding is
per-context. A provider unwinding is a routine event; if it reached for
``close_active_bucket_session`` unconditionally it would seal whatever session
happened to be bound at that moment, which is somebody else's unlocked bucket.
That failure has no bad input to reproduce it -- it needs two bindings and an
unwind in between -- so it is invisible to any single-session test.

Sessions here are real, with real key buffers, and closure is asserted on the
session's own sealed state rather than on a call count: a teardown that "ran"
while leaving a session usable is the failure being guarded against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from ......core.time import now
from .._active_session import activate_session, bind_active_bucket_session, current_active_bucket_session
from .._bucket_session import BucketSession
from .._provider_session import exit_provider_session

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OWNED = "0f5cf7d0-9f8e-4b17-9a3d-6c1f2e8a4b71"
_OTHER = "1b6da8e1-3c2f-4d5a-8e7b-9f0a1c2d3e4f"


@dataclass
class _Owner:
    """The provider bookkeeping the teardown reads, in its real shape."""

    _session: BucketSession | None = None
    _activation_cm: AbstractContextManager[None] | None = None


def _session(bucket_id: str) -> BucketSession:
    """Open a real session holding real key buffers."""
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=b"K" * 32,
        dek=b"D" * 32,
        idle_minutes=30,
        opened_at=now(),
    )


def test_the_owned_session_is_closed_when_it_is_the_active_one() -> None:
    """The ordinary unwind: the provider's own session is the bound one."""
    owned = _session(_OWNED)
    owner = _Owner(_session=owned)
    bind_active_bucket_session(owned)

    exit_provider_session(owner, None, None, None)

    assert owned.sealed
    assert current_active_bucket_session() is None
    assert owner._session is None


def test_a_session_bound_by_someone_else_survives_the_unwind() -> None:
    """DISCRIMINATING: the eviction this function exists to avoid.

    The provider still holds session A while B is the bound one. Closing A is
    correct; sealing B is another context's unlocked bucket taken away by an
    unwind it never participated in.
    """
    owned = _session(_OWNED)
    other = _session(_OTHER)
    owner = _Owner(_session=owned)

    with activate_session(other):
        exit_provider_session(owner, None, None, None)

        assert owned.sealed, "the provider's own session must still be closed"
        assert not other.sealed, "a session bound by another boundary must survive"
        assert current_active_bucket_session() is other, "the other binding must remain in place"

    other.close()


def test_a_second_exit_is_a_no_op() -> None:
    """Bookkeeping is detached before cleanup, so a repeated unwind does nothing.

    ANTI-TAUTOLOGY for the case above as well: it proves the survival of the
    other session is the guard working, not the teardown having quietly
    stopped doing anything after the first call.
    """
    owned = _session(_OWNED)
    other = _session(_OTHER)
    owner = _Owner(_session=owned)
    bind_active_bucket_session(owned)

    exit_provider_session(owner, None, None, None)
    bind_active_bucket_session(other)
    exit_provider_session(owner, None, None, None)

    assert owned.sealed
    assert not other.sealed, "a repeated exit must not reach a session it never owned"
    assert current_active_bucket_session() is other

    other.close()
