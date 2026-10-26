"""Scoped active-session absence for storage behavior tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..active_session import active_session


@contextmanager
def suspend_active_session() -> Generator[None]:
    """Temporarily clear the active :class:`BucketSession` for the current context."""
    with active_session.override(None):
        yield
