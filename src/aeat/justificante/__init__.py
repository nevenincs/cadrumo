"""Internal re-export shim for `aeat.justificante`.

Canonical location: :mod:`aeat.domain.justificante` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.justificante import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.justificante"), "__all__", ())
