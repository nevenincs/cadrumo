"""Public compatibility surface for relocated submission policy errors."""

from __future__ import annotations

from .core.access_gate import LiveSubmitForbiddenError

__all__ = ["LiveSubmitForbiddenError"]
