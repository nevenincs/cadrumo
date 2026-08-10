"""Discardable evaluation harness for the full-screen TUI surfaces.

Renders any registered surface headlessly, drives it with real
keystrokes, and prints the frame as text an agent can read — alongside the
focus cycle, the offered key affordances, the flow engine's own state, and
the appearance defects a structural check cannot see.

This is an evaluation instrument, not a gate. It asserts nothing and
passes nothing; it reports what the surface does so a reviewer can judge
the experience, the correctness of the projection, and the cost of a
keystroke. The shipped gates under
``src/cadrumo/adapters/inbound/tui/tests/`` remain the pass/fail authority.

Development tooling: it lives under ``dev/`` and ships in no wheel. The
whole harness is one directory and one gitignored state folder, so
discarding it is deleting ``dev/tui/``.

Usage::

    uv run --no-sync python -m dev.tui surfaces
    uv run --no-sync python -m dev.tui open manager
    uv run --no-sync python -m dev.tui press tab enter
    uv run --no-sync python -m dev.tui undo
"""

from __future__ import annotations

from ._frame import Frame, capture, screen_text
from ._journal import Session, read_session, write_session
from ._replay import replay, screenshot
from ._surfaces import SURFACES, Surface, resolve

__all__ = [
    "SURFACES",
    "Frame",
    "Session",
    "Surface",
    "capture",
    "read_session",
    "replay",
    "resolve",
    "screen_text",
    "screenshot",
    "write_session",
]
