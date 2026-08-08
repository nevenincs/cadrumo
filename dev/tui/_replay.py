"""Replay a journal from birth and read the resulting frame.

Nothing is cached and no process survives a command. The app is
constructed, mounted under Textual's headless Pilot, driven through the
recorded gestures in order, and read. A frame is therefore always a
statement about the current tree, never about a tree that existed when
some daemon started.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import ExitStack
from typing import TypeVar

from textual.app import App
from textual.pilot import Pilot

from ._fixture import ensure_profile, ensure_session, harness_storage
from ._frame import Frame, capture
from ._journal import Click, Fill, Press, Session, Type
from ._surfaces import resolve

T = TypeVar("T")


def _theme_name(appearance: str) -> str:
    """Resolve an appearance word to the registered Cadrumo theme name.

    Through the adapter's own resolver, never by spelling the theme name
    here: the harness must render under exactly the theme an operator
    with that preference gets.
    """
    from cadrumo.adapters.inbound.tui import resolve_theme_name
    from cadrumo.core.config import TuiAppearance

    return resolve_theme_name(TuiAppearance(appearance))


async def _apply(pilot: Pilot, session: Session) -> None:
    """Deliver every recorded gesture, in order, through the real pipeline."""
    for gesture in session.gestures:
        match gesture:
            case Press():
                for key in gesture.keys:
                    await pilot.press(key)
            case Type():
                for char in gesture.text:
                    await pilot.press(char)
            case Fill():
                pilot.app.query_one(gesture.selector).value = gesture.value
            case Click():
                await pilot.click(gesture.selector)
        await pilot.pause()

    # Any storage call a gesture kicked off must land before anything is
    # read, or the reading is about the harness's timing rather than the
    # surface's behaviour.
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _run(session: Session, read: Callable[[App, float], Awaitable[T] | T]) -> T:
    """Build, drive and hand the settled app to ``read``.

    The one place a surface is constructed and walked. Both the frame
    capture and the SVG export come through here, so they can never
    disagree about what "the current frame" means.
    """
    surface = resolve(session.surface)
    width, height = session.size

    async def _drive() -> T:
        started = time.perf_counter()
        app = surface.build()
        async with app.run_test(size=(width, height)) as pilot:
            app.theme = _theme_name(session.theme)
            await pilot.pause()
            await _apply(pilot, session)
            elapsed_ms = (time.perf_counter() - started) * 1000
            result = read(app, elapsed_ms)
            if isinstance(result, Awaitable):
                result = await result
            app.exit(None)
        return result

    with ExitStack() as stack:
        if surface.needs_profile:
            stack.enter_context(harness_storage())
            ensure_session() if surface.needs_session else ensure_profile()
        return asyncio.run(_drive())


def replay(session: Session) -> Frame:
    """Rebuild, replay, and read every band off the settled screen."""
    width, height = session.size
    return _run(
        session,
        lambda app, elapsed_ms: capture(
            app,
            index=len(session.gestures),
            surface=session.surface,
            width=width,
            height=height,
            theme=session.theme,
            elapsed_ms=elapsed_ms,
        ),
    )


def screenshot(session: Session, path: str) -> str:
    """Write the SVG of the current frame, for colour and glyph review."""
    _run(session, lambda app, _elapsed: app.save_screenshot(path))
    return path


__all__ = ["replay", "screenshot"]
