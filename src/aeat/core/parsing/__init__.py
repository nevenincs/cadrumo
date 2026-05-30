"""Shared parsing primitives for the AEAT application layer.

Public surface
--------------

* :func:`_parse_bool` — parse a raw string token into ``True``, ``False``,
  or ``None`` (absent / unrecognised).
* :func:`_parse_iso8601_date` — parse an ISO-8601 date string (``YYYY-MM-DD``).
* :func:`_parse_ddmmyyyy_date` — parse a Spanish day-first date string
  (``DD-MM-YYYY`` or ``DD/MM/YYYY``).
"""

from __future__ import annotations

from ._dates import _parse_date, _parse_ddmmyyyy_date, _parse_iso8601_date
from ._utils import _parse_bool

__all__ = ["_parse_bool", "_parse_date", "_parse_ddmmyyyy_date", "_parse_iso8601_date"]
