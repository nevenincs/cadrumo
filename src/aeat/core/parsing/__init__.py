"""Shared parsing primitives for the AEAT application layer.

Public surface
--------------

* :func:`_parse_bool` — parse a raw string token into ``True``, ``False``,
  or ``None`` (absent / unrecognised).
"""

from __future__ import annotations

from ._utils import _parse_bool

__all__ = ["_parse_bool"]
