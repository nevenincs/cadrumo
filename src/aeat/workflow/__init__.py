"""Internal re-export shim for `aeat.workflow`.

Canonical location: :mod:`aeat.application.workflow` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.workflow import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.workflow"), "__all__", ())
