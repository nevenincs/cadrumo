"""Shared parsing primitives for the AEAT application layer.

Public surface
--------------

* :func:`parse_bool` — parse a raw string token into ``True``, ``False``,
  or ``None`` (absent / unrecognised).
* :func:`parse_date` — unified date parser with format and error-policy axes.
* :func:`parse_iso8601_date` — parse an ISO-8601 date string (``YYYY-MM-DD``).
* :func:`parse_ddmmyyyy_date` — parse a Spanish day-first date string
  (``DD-MM-YYYY`` or ``DD/MM/YYYY``).

The underscore-prefixed aliases (``_parse_iso8601_date``,
``_parse_ddmmyyyy_date``, ``_parse_date``, ``_parse_bool``) are
preserved for backward compatibility with existing in-package
consumers; new cross-package consumers MUST use the public names
above so the ``no-private-name-cross-package-imports`` diagnostic
gate stays green.
"""

from __future__ import annotations

from ._dates import _parse_date, _parse_ddmmyyyy_date, _parse_iso8601_date, parse_date
from ._utils import _parse_bool, parse_bool

# Public-name aliases for the parsing primitives that other packages
# consume. The leading-underscore originals stay reachable for the
# parsing-package's own in-place consumers; cross-package callers MUST
# import the non-underscored names below.
parse_iso8601_date = _parse_iso8601_date
parse_ddmmyyyy_date = _parse_ddmmyyyy_date

__all__ = [
    "_parse_bool",
    "_parse_date",
    "_parse_ddmmyyyy_date",
    "_parse_iso8601_date",
    "parse_bool",
    "parse_date",
    "parse_ddmmyyyy_date",
    "parse_iso8601_date",
]
