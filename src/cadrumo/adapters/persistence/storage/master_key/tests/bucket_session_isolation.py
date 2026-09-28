"""Test boundaries for the process-wide bucket-session binding.

The binding has two layers: a process-wide value that an unscoped ``bind``
publishes, and a context-scoped override that ``activate_session`` installs for
one block. A boundary that observes only the merged view cannot restore both.
Re-binding what it saw publishes an override-held session process-wide, where it
outlives the fixture that scoped it and reaches every later test in the worker.

So an observation records both layers, and eviction restores each one to what
it recorded. The process layer is read from a fresh :class:`~contextvars.Context`,
which carries no override and therefore sees exactly the published value.
"""

from __future__ import annotations

import sys
from contextvars import Context
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bucket_session import BucketSession

_ACTIVE_SESSION_MODULE = "cadrumo.adapters.persistence.storage.master_key.active_session"


@dataclass(frozen=True, slots=True, eq=False)
class BucketSessionBinding:
    """The session this context sees and the session the process publishes, at one instant."""

    visible: BucketSession | None
    published: BucketSession | None

    def is_same_as(self, other: BucketSessionBinding) -> bool:
        """Compare by identity: a replacement session is a different binding even if equal."""
        return self.visible is other.visible and self.published is other.published


def observe_bucket_session_binding() -> BucketSessionBinding:
    """Record both layers of the binding without importing storage that is not loaded yet.

    Nothing can be bound before the owning module is imported, so a test that
    never touches storage pays nothing here.
    """
    if _ACTIVE_SESSION_MODULE not in sys.modules:
        return BucketSessionBinding(visible=None, published=None)
    from ..active_session import current_active_bucket_session

    return BucketSessionBinding(
        visible=current_active_bucket_session(),
        published=Context().run(current_active_bucket_session),
    )


def evict_bucket_sessions_bound_since(before: BucketSessionBinding) -> tuple[BucketSession, ...]:
    """Close every session bound after ``before`` and restore both layers to it.

    A session that ``before`` already held belongs to an outer owner and is
    left open, and a binding the caller only released is left released.
    Returns the sessions this call closed, so a caller can report a leak
    instead of only repairing it.
    """
    after = observe_bucket_session_binding()
    if after.is_same_as(before):
        return ()
    from ..active_session import (
        active_session,
        close_active_bucket_session,
        current_active_bucket_session,
    )

    inherited = (before.visible, before.published)
    evicted: list[BucketSession] = []
    if after.visible is not None and all(after.visible is not held for held in inherited):
        close_active_bucket_session()
        evicted.append(after.visible)
    if (
        after.published is not None
        and after.published is not after.visible
        and all(after.published is not held for held in inherited)
    ):
        Context().run(close_active_bucket_session)
        evicted.append(after.published)
    if not evicted:
        # The test only released a session it inherited; that is its own act.
        return ()
    # A bind refreshes an override in force here as well as the process value,
    # so this restores the view; the process value is then put back from a
    # context with no override, which touches nothing else.
    if current_active_bucket_session() is not before.visible:
        active_session.bind(before.visible)
    Context().run(active_session.bind, before.published)
    return tuple(evicted)


__all__ = ["BucketSessionBinding", "evict_bucket_sessions_bound_since", "observe_bucket_session_binding"]
