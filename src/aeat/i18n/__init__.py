"""Internal re-export shim for `aeat.i18n`.

Canonical location: :mod:`aeat.core.i18n` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..core.i18n import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.i18n"), "__all__", ())
