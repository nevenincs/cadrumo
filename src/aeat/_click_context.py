"""Internal module-level shim for `aeat._click_context`.

Canonical location: :mod:`aeat.core.click_context` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.click_context import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.click_context"), "__all__", ())
