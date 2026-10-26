"""Typed context variables consumed by structured event logging."""

from __future__ import annotations

from contextvars import ContextVar

from pydantic import BaseModel

from ..models import STRICT_FROZEN_CONFIG


class RunContextInfo(BaseModel):
    """Run correlation identity consumed by the installed log-record factory."""

    model_config = STRICT_FROZEN_CONFIG

    run_id: str


RUN_CONTEXT_VAR: ContextVar[RunContextInfo | None] = ContextVar(
    "_aeat_run_ctx",
    default=None,
)

STEP_CONTEXT_VAR: ContextVar[str | None] = ContextVar(
    "_aeat_step_ctx",
    default=None,
)
