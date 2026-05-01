"""Internal re-export shim for `aeat.llm`.

Canonical location: :mod:`aeat.adapters.outbound.llm` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.outbound.llm import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.outbound.llm"), "__all__", ())
