"""Public compatibility surface for the relocated error hierarchy."""

from __future__ import annotations

from .core.errors import *  # noqa: F403
from .core.errors import __all__ as _core_errors_all

__all__ = list(_core_errors_all)
