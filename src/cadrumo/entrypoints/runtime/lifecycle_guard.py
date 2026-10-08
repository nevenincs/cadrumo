"""Owned lifecycle exclusion with a FIFO handoff from polling to custody deletion."""

from __future__ import annotations

import time
from collections import deque
from threading import Condition, RLock, get_ident
from typing import Literal

from ...core.errors.hierarchy import InternalInvariantError

_LifecycleRole = Literal["exclusive", "poll", "delete"]


class RuntimeLifecycleGuard:
    """Retain reentrant exclusion while handing actual poll collisions to their waiters.

    Default acquisition keeps close/drain's existing nonblocking or supplied
    timeout behavior. Only deletion colliding with a foreign poll owner joins
    the FIFO. Ownership is transferred under the condition before notification,
    so another poll cannot steal a registered handoff. The existing bounded
    native serving pool owns these callers; this guard creates no worker.
    Only the current logical owner can change its reentrant depth without
    the monitor; foreign queue bookkeeping cannot release that ownership.
    """

    def __init__(self) -> None:
        """Keep ownership transfers and FIFO state under an independent condition."""
        self._state_lock = RLock()
        self._condition = Condition(self._state_lock)
        self._owner: int | None = None
        self._owner_role: _LifecycleRole | None = None
        self._depth = 0
        self._delete_waiters: deque[tuple[object, int]] = deque()
        self._handoff: object | None = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Keep ordinary lifecycle ownership reentrant and honor the caller's timeout."""
        identity = get_ident()
        if self._owner == identity:
            # Validate the native API before changing owner-exclusive depth.
            arguments = RLock()
            if not arguments.acquire(blocking=blocking, timeout=timeout):
                return False
            arguments.release()
            self._depth += 1
            return True
        deadline = None if timeout == -1 else time.monotonic() + timeout
        if not self._state_lock.acquire(blocking=blocking, timeout=timeout):
            return False
        try:
            if self._owner == identity:
                self._depth += 1
                return True
            while self._owner is not None:
                if not blocking:
                    return False
                if deadline is None:
                    self._condition.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._condition.wait(remaining)
            self._claim(identity, "exclusive")
            return True
        finally:
            self._state_lock.release()

    def acquire_poll(self) -> bool:
        """Admit a routine poll without waiting or cutting registered deletion work."""
        identity = get_ident()
        if self._owner == identity:
            self._depth += 1
            return True
        if not self._state_lock.acquire(blocking=False):
            return False
        try:
            if self._owner == identity:
                self._depth += 1
                return True
            if self._owner is not None or self._delete_waiters:
                return False
            self._claim(identity, "poll")
            return True
        finally:
            self._state_lock.release()

    def acquire_delete(self) -> bool:
        """Wait only for an actual poll handoff; fresh exclusive collisions still refuse."""
        identity = get_ident()
        if self._owner == identity:
            self._depth += 1
            return True
        with self._condition:
            if self._owner == identity:
                self._depth += 1
                return True
            if self._owner is None:
                self._claim(identity, "delete")
                return True
            if self._owner_role != "poll":
                return False
            ticket = object()
            waiter = (ticket, identity)
            self._delete_waiters.append(waiter)
            try:
                while self._handoff is not ticket:
                    self._condition.wait()
                self._handoff = None
                return True
            except BaseException:
                if self._handoff is ticket:
                    self._release_owner()
                else:
                    self._delete_waiters.remove(waiter)
                raise

    def release(self) -> None:
        """Release only this thread's ownership, transferring the final depth atomically."""
        with self._condition:
            if self._owner != get_ident():
                raise InternalInvariantError("cannot release un-acquired lock")
            self._depth -= 1
            if self._depth == 0:
                self._release_owner()

    def _claim(self, identity: int, role: _LifecycleRole) -> None:
        self._owner, self._owner_role, self._depth = identity, role, 1

    def _release_owner(self) -> None:
        if self._delete_waiters:
            ticket, identity = self._delete_waiters.popleft()
            self._claim(identity, "delete")
            self._handoff = ticket
        else:
            self._owner, self._owner_role, self._depth, self._handoff = None, None, 0, None
        self._condition.notify_all()
