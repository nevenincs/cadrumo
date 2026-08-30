"""Layer-neutral schema for operator-visible progress updates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG


class OperatorProgress(BaseModel):
    """Actionable progress text plus an optional live countdown duration."""

    model_config = STRICT_FROZEN_CONFIG

    message: str = Field(min_length=1)
    timeout_seconds: int | None = Field(default=None, gt=0)

    def render(self, *, remaining_seconds: int | None = None) -> str:
        """Render the update for a frontend that cannot animate a timer."""
        seconds = self.timeout_seconds if remaining_seconds is None else remaining_seconds
        if seconds is None:
            return self.message
        minutes, remainder = divmod(max(0, seconds), 60)
        return f"{self.message} Time remaining {minutes}:{remainder:02d}."


__all__ = ["OperatorProgress"]
