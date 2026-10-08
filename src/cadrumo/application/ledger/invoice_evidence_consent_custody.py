"""Bridge synchronous consent-ledger saves to registered operation write custody."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from threading import Lock, get_ident

from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect
from ..operations.owner import OperationExecutorContext


class InvoiceEvidenceConsentCustody:
    """Keep one cancellation owner around each actual consent-ledger save.

    Construct on the operation's event loop. Give ``before_save`` and
    ``after_save`` to the injected consent ledger, and run extraction in a
    worker thread. The section lives in one event-loop task throughout the
    synchronous secure-object save; no section surrounds model inference.
    """

    def __init__(self, context: OperationExecutorContext) -> None:
        """Bind the operation context to the current running event loop."""
        self._context = context
        self._loop = asyncio.get_running_loop()
        self._loop_thread_id = get_ident()
        self._lock = Lock()
        self._active = False
        self._outcome: asyncio.Future[bool] | None = None
        self._session: Future[None] | None = None
        self._current_effect = OperationEffect.NONE

    @property
    def current_effect(self) -> OperationEffect:
        """Return the last successfully recorded consent write effect."""
        return self._current_effect

    def _require_worker_thread(self) -> None:
        if get_ident() == self._loop_thread_id:
            raise InternalInvariantError("consent-ledger save custody must run from a worker thread")

    async def _save_section(self, started: Future[None]) -> None:
        try:
            async with self._context.cancellation.irreversible_section():
                await self._context.events.effect(OperationEffect.UNKNOWN)
                self._current_effect = OperationEffect.UNKNOWN
                self._outcome = self._loop.create_future()
                started.set_result(None)
                if await self._outcome:
                    await self._context.events.effect(OperationEffect.UPDATED)
                    self._current_effect = OperationEffect.UPDATED
        except BaseException as exc:
            if not started.done():
                started.set_exception(exc)
            raise

    def before_save(self) -> None:
        """Enter write custody and durably mark UNKNOWN before storage can write."""
        self._require_worker_thread()
        with self._lock:
            if self._active:
                raise InternalInvariantError("consent-ledger save custody is already active")
            self._active = True
        started: Future[None] = Future()
        try:
            self._session = asyncio.run_coroutine_threadsafe(self._save_section(started), self._loop)
            started.result()
        except BaseException:
            with self._lock:
                self._active = False
            raise

    def after_save(self, saved: bool) -> None:
        """Settle the same section, retaining UNKNOWN for an uncertain save."""
        self._require_worker_thread()
        with self._lock:
            if not self._active or self._outcome is None or self._session is None:
                raise InternalInvariantError("consent-ledger save custody was not entered")
            outcome = self._outcome
            session = self._session
        try:
            self._loop.call_soon_threadsafe(outcome.set_result, saved)
            session.result()
        finally:
            with self._lock:
                self._active = False
                self._outcome = None
                self._session = None


__all__ = ["InvoiceEvidenceConsentCustody"]
