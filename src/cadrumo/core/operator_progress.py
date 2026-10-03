"""Layer-neutral operator-progress schema and the context-scoped channel that carries it.

The channel lives in core so that whichever layer owns the operator's view can
arm it: the operation supervisor forwards each update's ``notice_code`` into
the operation's public notice events, and the CLI routes in-process updates to
stderr. An emitter running with no sink armed only records to its own log.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG

type OperatorProgressSink = Callable[[OperatorProgress], Awaitable[None]]


class OperatorProgress(BaseModel):
    """Actionable progress text plus a stable notice code and optional live countdown.

    ``notice_code`` is the only part that cros