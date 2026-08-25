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

from textual.app import App
from textual.pilot import Pilot

from ._fixture import ensure_profile, ensure_session, harness_storage
from ._frame import Frame, capture
from ._journal import Click, Fill, Press, Session, Type
from ._surfaces import resolve


def _theme_name(appearance: str) -> str:
    """Resolve an appearance word to the registered Cadrumo theme name.

    Through the adapter's own resolver, never by spelling the theme name
    here: the harness must render under exactly the theme an operator
    with that preference gets.
    """
    from cadrumo.core.config import TuiAppearance
    from cadrumo.entrypoints.tui.components import resolve_theme_name

    return resolve_theme_name(TuiAppearance(appearance))


def _activate_locale(locale: str | None) -> None:
    """Make the process-wide output language match ``locale`` before build.

    ``locale is None`` deliberately does nothing: an explicit
    ``cadrumo_output_language`` (env var, ``override_settings``, or ``.env``)
    always outranks the active profile's stored preference in
    :func:`~cadrumo.core.i18n.output_language`'s resolution order, so forcing
    one on every walk would permanently shadow a profile-level language
    change — exactly the axis the ``manager`` surface's live language
    chooser needs read without interference.

    ``load_settings()`` holds a process-wide ``Settings`` singleton cached
    by the active-profile pointer, not by env var, so a raw ``os.environ``
    mutation alone is invisible to it once that singleton exists.
    ``reset_settings_cache`` is the sanctioned way to make a process
    environment change observed, and — unlike ``override_settings``'s
    contextvar — it stays valid across the asyncio Task boundary the
    Textual pilot's message pump runs on (see
    ``test_flow_tui_app.py::test_rebuild_for_locale_reassembles_copy_under_the_new_language``).
    """
    if locale is None:
        return

    import os

    from cadrumo.core.config import reset_settings_cache
    from cadrumo.core.i18n import OUTPUT_LANGUAGE_ENV_VAR, clear_output_language_cache

    os.environ[OUTPUT_LANGUAGE_ENV_VAR] = locale
    reset_settings_cache()
    clear_output_language_cache()


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
                # Scoped to the TOP screen, not ``pilot.app``: a modal (the
                # field-edit dialog, a confirm prompt) is a pushed
                # ``Screen``, and ``App.query_one`` does not reach into it —
                # ``fill`` raised ``NoMatches`` against every selector that
                # lived inside one, which is most of them. ``pilot.click``
                # a few lines below never had this problem because
                # ``Pilot`` already resolves a selector against the current
                # screen.
                pilot.app.screen.query_one(gesture.selector).value = gesture.value
            case Click():
                await pilot.click(gesture.selector)
        await pilot.pause()

    # A pushed modal is itself a settled, operator-visible state. Manager
    # actions deliberately keep their worker alive while that modal waits for
    # the next gesture, so waiting for every worker here would deadlock the
    # replay before the form could be captured or answered. Once the modal is
    # gone, wait for all work so storage and repaint land before the frame is
    # read.
    if len(pilot.app.screen_stack) == 1:
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()


def _run[T](session: Session, read: Callable[[App, float], Awaitable[T] | T]) -> T:
    """Build, drive and hand the settled app to ``read``.

    The one place a surface is constructed and walked. Both the frame
    capture and the SVG export come through here, so they can never
    disagree about what "the current frame" means.
    """
    surface = resolve(session.surface)
    width, height = session.size

    # Must run before ``harness_storage()`` opens below: that helper enters
    # an ``override_settings`` contextvar block that snapshots ``Settings``
    # (including ``cadrumo_output_language``) at ENTRY time and holds it for
    # the whole walk. Activating the locale after that point mutates the
    # environment but never reaches the snapshot the render path reads.
    _activate_locale(session.locale)

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
        if surface.provision is not None:
            stack.enter_context(surface.provision())
        elif surface.needs_profile:
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
            locale=session.locale or "auto",
            elapsed_ms=elapsed_ms,
        ),
    )


def screenshot(session: Session, path: str) -> str:
    """Write the SVG of the current frame, for colour and glyph review."""
    _run(session, lambda app, _elapsed: app.save_screenshot(path))
    return path


__all__ = ["replay", "screenshot"]
