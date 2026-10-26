"""Unbind ambient validation authority when exercising explicit-lease contracts."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ..governed_fact_scope import _VALIDATING_GOVERNED_FACTS


@contextmanager
def outside_governed_fact_validation() -> Generator[None]:
    """Run a block as if no registry validation were in progress.

    A component that must acquire its own authority lease is only proven to do
    so when no enclosing validation scope can lend it one.
    """
    token = _VALIDATING_GOVERNED_FACTS.set(None)
    try:
        yield
    finally:
        _VALIDATING_GOVERNED_FACTS.reset(token)
