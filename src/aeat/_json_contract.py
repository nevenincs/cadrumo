"""Internal module-level shim for `aeat._json_contract`.

Canonical location: :mod:`aeat.core.json_contract` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.json_contract import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.json_contract"), "__all__", ())
