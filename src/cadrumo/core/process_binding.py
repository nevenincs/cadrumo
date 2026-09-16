"""One process-wide binding with a context-scoped override.

A :class:`~contextvars.ContextVar` is the right shape for a value that must
stay private to one span of work, and the wrong shape for a value that names
what is true of the whole process. The live profile session is the second
kind: exactly one profile is logged in per process, and every entry point --
a parsed CLI invocation, a Textual thread worker, a second
:func:`asyncio.run` frame in the same program -- must observe the same
answer.

PEP 567 semantics defeat that on their own. ``asyncio.run`` runs its loop in
a fresh context, a thread does not inherit its spawner's context, and
:meth:`contextvars.Context.run` discards every write made inside it. A
binding installed in any of those frames is therefore invisible to the frame
that reads it, which presents to the operator as a correct login followed by
a surface that cannot find the profile it just authenticated.

This binding composes both needs. The process-wide value is guarded by a
lock and is what an unscoped ``bind`` publishes; the context-scoped override
is what a ``with`` block installs for the duration of one span and unwinds on
exit. Reads consult the override first, so a nested span still shadows the
process value exactly as a plain ``ContextVar`` did, and fall back to the
process value when no override is in force.

The binding holds a reference, never a copy: an owner that zeroises key
material on close keeps that responsibility, and this type only decides who
can see the object.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import final


@final
class ProcessScopedBinding[T]:
    """Publish one value process-wide while allowing a scoped override.

    The override is stored as a one-tuple rather than the bare value so that
    "no override in this context" and "an override deliberately set to
    ``None``" stay distinguishable. The second is a real state: a caller that
    suspends the binding for a block is asserting an absence, and collapsing
    it into the first would let the process value show through the very block
    that hid it.
    """

    __slots__ = ("_lock", "_override", "_value")

    def __init__(self, name: str) -> None:
        """Create an unbound binding whose override variable is named ``name``."""
        self._override: ContextVar[tuple[T | None] | None] = ContextVar(name, default=None)
        self._lock = threading.Lock()
        self._value: T | None = None

    def get(self) -> T | None:
        """Return the override in force for this context, else the process value."""
        override = self._override.get()
        if override is not None:
            return override[0]
        with self._lock:
            return self._value

    def bind(self, value: T | None) -> None:
        """Publish ``value`` process-wide, and into any override in force here.

        Refreshing an override in force is what keeps an unscoped bind
        truthful to its own caller: a bind performed inside a span that
        shadows the process value would otherwise be published to every
        context except the one that performed it.
        """
        with self._lock:
            self._value = value
        if self._override.get() is not None:
            self._override.set((value,))

    def clear_bound(self, expected: T) -> None:
        """Remove ``expected`` wherever this context can still observe it.

        A retiring owner must unbind the exact object it observed, from the
        override in force here as well as from the process value, because a
        session closed inside an overriding block is bound in both places and
        clearing only one leaves a zeroised object advertised as live.

        Identity, not equality: a replacement installed reentrantly during the
        retirement is a different object and must survive it, which is exactly
        what an equality comparison would fail to preserve.
        """
        override = self._override.get()
        if override is not None and override[0] is expected:
            self._override.set((None,))
        with self._lock:
            if self._value is expected:
                self._value = None

    @contextmanager
    def override(self, value: T | None) -> Generator[None]:
        """Shadow the process value with ``value`` for the duration of the block.

        Overrides stack and unwind through the :class:`~contextvars.Token`
        the override variable returns, so a nested block restores the exact
        binding its caller observed. The process value is never touched here;
        only :meth:`bind` and :meth:`clear_bound` change what the rest of the
        program sees.
        """
        token = self._override.set((value,))
        try:
            yield
        finally:
            self._override.reset(token)


__all__ = ["ProcessScopedBinding"]
