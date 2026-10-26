"""Wait, under the pilot, for an app to finish what the test's last gesture started.

A gesture only posts: ``Button.press`` posts ``Pressed``, assigning a
``Checkbox`` or ``Input`` value posts ``Changed``, and the handler that
starts the work runs when the message has bubbled to it, on a later turn of
each pump on the way. ``Pilot.pause`` waits only for the messages already
queued on the app and the active screen when it began, and its idle check
reads the process's own CPU time, so on a loaded machine it returns while
the message is still bubbling. A fixed number of pauses, or joining the
workers straight after the gesture, therefore waits for nothing that the
gesture has not already reached.

Settling waits on the pumps and workers themselves. Each round pauses,
awaits every unfinished worker, and then asks every pump on the app and on
each screen in the stack to run a callback. A pump that is waiting for its
next message runs it on the event loop's next turn; one that is still
handling a message runs it only after its handler returns. An empty queue
would not tell these apart: a pump takes a message off its queue before it
handles it, so a message bubbling from parent to parent, or a handler that
awaits, leaves every queue empty while the work goes on. Two consecutive
rounds in which every pump answered at once and no worker was unfinished,
on the same active screen, count as settled.

Every wait is bounded by a deadline, not by a count, and names what it was
waiting for, so a step whose work never finishes fails with that reason
rather than with an assertion about the wrong state.

A capture host drives its screen from inside its own mount handler, with no
pilot. ``settle_host`` and ``settle_host_until`` settle such an app the same
way, leaving out the app's own pump: it is busy running the handler that
waits, and the pilot drains it once that handler returns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any, Final

from textual.app import App
from textual.message_pump import MessagePump
from textual.pilot import Pilot
from textual.widget import Widget
from textual.worker import Worker, WorkerCancelled

SETTLE_TIMEOUT_SECONDS: Final = 180.0
"""Bounds a failure, not a success.

An app that settles at all usually settles within a few rounds, but a write
through the real encrypted door runs key derivation in a supervised child
process, and on a machine saturated by parallel test workers that can take
minutes. Expiring sooner would report the machine's load as a defect.
"""

_QUIET_ROUNDS: Final = 2

_PROMPT_TURNS: Final = 4
"""An idle pump runs a queued callback on the loop's next turn; the rest is margin, not a wait."""


class SettleTimeoutError(AssertionError):
    """The app was still busy, or the awaited state never held, when the deadline passed."""


def _pumps[ResultT](app: App[ResultT], *, with_app: bool) -> tuple[MessagePump, ...]:
    pumps: list[MessagePump] = [app] if with_app else []
    for screen in app.screen_stack:
        pumps.append(screen)
        pumps.extend(screen.walk_children(Widget, with_self=False))
    return tuple(pumps)


async def _still_handling[ResultT](app: App[ResultT], *, with_app: bool) -> tuple[str, ...]:
    """The pumps that did not run a callback within a few turns of the event loop, by name.

    The callback is queued behind whatever the pump holds, so a pump that
    runs it promptly held nothing and was handling nothing. One that does
    not is still busy; its callback runs later and records nothing that is
    read again.
    """
    answered: set[int] = set()
    asked = [pump for pump in _pumps(app, with_app=with_app) if pump.call_later(answered.add, id(pump))]
    for _ in range(_PROMPT_TURNS):
        await asyncio.sleep(0)
        if len(answered) == len(asked):
            return ()
    return tuple(f"{pump!r} is still handling a message" for pump in asked if id(pump) not in answered)


def _app_is_running[ResultT](app: App[ResultT]) -> bool:
    """Read the flag afresh: it changes across the awaits, so a narrowing from the loop test must not carry over."""
    return app.is_running


def _running[ResultT](app: App[ResultT]) -> tuple[str, ...]:
    return tuple(f"worker {worker.name or worker!r}" for worker in app.workers if not worker.is_finished)


async def _finish(workers: list[Worker[Any]]) -> None:
    """Await each worker; one replaced by an exclusive successor is finished, a failed one raises."""
    for worker in workers:
        with suppress(WorkerCancelled):
            await worker.wait()


async def _finished_by(workers: list[Worker[Any]], deadline: float) -> bool:
    """Whether every worker finished before the deadline; a worker still running then is left running."""
    left = max(deadline - asyncio.get_running_loop().time(), 0.0)
    try:
        await asyncio.wait_for(asyncio.shield(_finish(workers)), timeout=left)
    except TimeoutError:
        return False
    return True


async def _settled_until[ResultT](
    app: App[ResultT],
    reached: Callable[[], bool],
    waiting_for: str,
    *,
    pause: Callable[[], Awaitable[None]],
    with_app: bool,
    workers: bool,
    timeout: float,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    settled_rounds = 0
    settled_on: object = None
    why = "the app has not settled yet"
    while _app_is_running(app):
        await pause()
        if not _app_is_running(app):
            return
        unfinished = [worker for worker in app.workers if workers and not worker.is_finished]
        if unfinished:
            settled_rounds = 0
            if await _finished_by(unfinished, deadline):
                continue
            why = "; ".join(_running(app))
        else:
            busy = await _still_handling(app, with_app=with_app) + (_running(app) if workers else ())
            if busy:
                settled_rounds = 0
                why = "; ".join(busy)
            elif not reached():
                settled_rounds = 0
                why = "the state never held on a settled app"
            else:
                screen = app.screen
                settled_rounds = settled_rounds + 1 if screen is settled_on else 1
                settled_on = screen
                if settled_rounds >= _QUIET_ROUNDS:
                    return
                why = "the app had settled for only one round"
        if loop.time() >= deadline:
            raise SettleTimeoutError(f"timed out after {timeout:g}s waiting for {waiting_for}: {why}")


async def settle_until[ResultT](
    pilot: Pilot[ResultT],
    reached: Callable[[], bool],
    waiting_for: str,
    *,
    workers: bool = True,
    timeout: float = SETTLE_TIMEOUT_SECONDS,
) -> None:
    """Return once the app has settled and ``reached`` held on both of the last two settled rounds.

    ``waiting_for`` names the state, so an expired wait says which step's
    precondition never arrived. ``workers=False`` settles the pumps alone,
    for a test that holds a worker on purpose while it reads the screen. An
    app that has stopped running has nothing left to settle.

    Raises:
        SettleTimeoutError: when the app is still busy, or ``reached`` has not
            held on a settled app, ``timeout`` seconds after the call.
        textual.worker.WorkerFailed: when a worker the gesture started raised.
    """
    await _settled_until(
        pilot.app, reached, waiting_for, pause=pilot.pause, with_app=True, workers=workers, timeout=timeout
    )


async def settle[ResultT](
    pilot: Pilot[ResultT], *, workers: bool = True, timeout: float = SETTLE_TIMEOUT_SECONDS
) -> None:
    """Return once every message the last gesture posted is handled and every worker it started has finished.

    ``workers=False`` waits for the messages alone and leaves workers running.

    Raises:
        SettleTimeoutError: when the app is still busy ``timeout`` seconds after the call.
        textual.worker.WorkerFailed: when a worker the gesture started raised.
    """
    await settle_until(pilot, lambda: True, "the app to settle", workers=workers, timeout=timeout)


async def _next_turn() -> None:
    await asyncio.sleep(0)


async def settle_host_until[ResultT](
    app: App[ResultT],
    reached: Callable[[], bool],
    waiting_for: str,
    *,
    timeout: float = SETTLE_TIMEOUT_SECONDS,
) -> None:
    """``settle_until`` for a host settling its own screen from inside its mount handler.

    Raises:
        SettleTimeoutError: as ``settle_until``.
        textual.worker.WorkerFailed: when a worker the gesture started raised.
    """
    await _settled_until(app, reached, waiting_for, pause=_next_turn, with_app=False, workers=True, timeout=timeout)


async def settle_host[ResultT](app: App[ResultT], *, timeout: float = SETTLE_TIMEOUT_SECONDS) -> None:
    """``settle`` for a host settling its own screen from inside its mount handler.

    Raises:
        SettleTimeoutError: as ``settle``.
        textual.worker.WorkerFailed: when a worker the gesture started raised.
    """
    await settle_host_until(app, lambda: True, "the screen to settle", timeout=timeout)


__all__ = [
    "SETTLE_TIMEOUT_SECONDS",
    "SettleTimeoutError",
    "settle",
    "settle_host",
    "settle_host_until",
    "settle_until",
]
