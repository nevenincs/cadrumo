"""Wait for a capture host's active screen to finish what its last gesture started.

A capture host drives its production screen from inside its own mount
handler: it types, chooses and presses, and each gesture posts messages that
the screen and its widgets handle on their own message pumps. A handler may
start a worker, push a dialog or post further messages. A frame is only
reviewable once all of that has run, and elapsed time promises none of it:
on a loaded machine a posted message can still be queued after any fixed pause.

Settling therefore waits on the pumps and workers themselves, the way
Textual's pilot waits for a screen: every pump on the active screen is asked
to run a callback after the messages already queued on it, every unfinished
worker is awaited, and the round repeats until it finds no queued message, no
unfinished worker and no change of screen. The host's own pump is left out:
it is busy running the mount handler that calls this, and the pilot drains it
once that handler returns.

Every wait is bounded and names what it was waiting for, so a step whose
precondition never arrives fails with that reason rather than with a lookup
error or a frame of the wrong state.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Final

from textual.app import App
from textual.dom import DOMNode
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Button
from textual.worker import Worker, WorkerCancelled

SETTLE_TIMEOUT_SECONDS: Final[float] = 60.0
"""Generous: frames are captured on loaded machines, and an expired wait is a failed capture."""


class SettleTimeoutError(TimeoutError):
    """A capture step's precondition did not arrive within its bound."""


def _pumps(screen: Screen[object]) -> tuple[Widget, ...]:
    return (screen, *screen.walk_children(Widget, with_self=False))


async def _within(work: Awaitable[object], *, deadline: float, waiting_for: str) -> None:
    left = max(deadline - asyncio.get_running_loop().time(), 0.0)
    try:
        await asyncio.wait_for(work, timeout=left)
    except TimeoutError:
        raise SettleTimeoutError(f"still waiting for {waiting_for}") from None


async def _drain(screen: Screen[object], *, deadline: float) -> None:
    """Return once every pump on ``screen`` has handled what was queued on it at the call."""
    remaining = 0
    drained = asyncio.Event()

    def one_drained() -> None:
        nonlocal remaining
        remaining -= 1
        if remaining == 0:
            drained.set()

    for pump in _pumps(screen):
        if pump.call_later(one_drained):
            remaining += 1
    if remaining:
        await _within(drained.wait(), deadline=deadline, waiting_for=f"{screen!r} to handle its queued messages")


async def _finish(workers: list[Worker[Any]]) -> None:
    """Await each worker; a worker replaced by an exclusive successor is finished, a failed one raises."""
    for worker in workers:
        with suppress(WorkerCancelled):
            await worker.wait()


def _quiet[ResultT](app: App[ResultT], screen: Screen[object]) -> bool:
    return (
        app.screen is screen
        and all(pump.message_queue_size == 0 for pump in _pumps(screen))
        and all(worker.is_finished for worker in app.workers)
    )


async def _settle_by[ResultT](app: App[ResultT], deadline: float) -> None:
    while True:
        screen = app.screen
        await _drain(screen, deadline=deadline)
        unfinished = [worker for worker in app.workers if not worker.is_finished]
        if unfinished:
            names = ", ".join(worker.name or repr(worker) for worker in unfinished)
            await _within(_finish(unfinished), deadline=deadline, waiting_for=f"workers {names}")
            continue
        if _quiet(app, screen):
            return


async def settle[ResultT](app: App[ResultT], *, timeout: float = SETTLE_TIMEOUT_SECONDS) -> None:
    """Return once the active screen's pumps are drained and every worker has finished.

    Raises:
        SettleTimeoutError: when the screen is still busy after ``timeout`` seconds.
        textual.worker.WorkerFailed: when a worker the gesture started raised.
    """
    try:
        await _settle_by(app, asyncio.get_running_loop().time() + timeout)
    except SettleTimeoutError as busy:
        raise SettleTimeoutError(f"the screen did not settle within {timeout:g}s: {busy}") from None


async def settle_until[ResultT](
    app: App[ResultT],
    reached: Callable[[], bool],
    waiting_for: str,
    *,
    timeout: float = SETTLE_TIMEOUT_SECONDS,
) -> None:
    """Settle, and keep settling until ``reached`` holds, within one bound.

    ``waiting_for`` names the state, so an expired wait says which step's
    precondition never arrived.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    expired = f"timed out after {timeout:g}s waiting for {waiting_for}"
    try:
        while True:
            await _settle_by(app, deadline)
            if reached():
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise SettleTimeoutError("the state never held on a settled screen")
    except SettleTimeoutError as busy:
        raise SettleTimeoutError(f"{expired}: {busy}") from None


async def press_when_enabled[ResultT](app: App[ResultT], button_id: str, *, within: DOMNode | None = None) -> None:
    """Press ``#button_id`` once it is shown and enabled, then settle what the press started.

    ``Button.press`` silently ignores a disabled or hidden button, so pressing
    before the previous step enabled it would capture the wrong state rather
    than fail. ``within`` defaults to the active screen at each check, which
    is where a dialog pushed by the previous step lives.
    """
    selector = f"#{button_id}"

    def pressable() -> bool:
        scope = app.screen if within is None else within
        return any(not button.disabled and button.display for button in scope.query(selector).results(Button))

    await settle_until(app, pressable, f"{selector} to be shown and enabled")
    (app.screen if within is None else within).query_one(selector, Button).press()
    await settle(app)


__all__ = ["SETTLE_TIMEOUT_SECONDS", "SettleTimeoutError", "press_when_enabled", "settle", "settle_until"]
