"""Shared utilities for the workflow application layer.

This is a documented re-export bridge: :func:`normalise_key` and
:func:`utc_now` are re-exported here so the workflow package's own
submodules (``_events.py``, ``_models.py``) and its top-level facade can
depend on one shared local surface, rather than each importing
:mod:`domain.contribuyente` and :mod:`core.time` directly at every call
site. The canonical definitions remain owned by those two packages;
this module is a re-export boundary only.
"""

from __future__ import annotations

from ...core.time import now as utc_now
from ...domain.contribuyente import normalise_key

__all__ = ["normalise_key", "utc_now"]
