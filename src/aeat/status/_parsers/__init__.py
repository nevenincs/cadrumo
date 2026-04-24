"""Private parser modules for the AEAT status reader (#43).

Each parser is a pure function: ``(raw_html, *, source_url,
fetched_at, ...) -> tuple[Record, ...] | Record``. Parsers never
perform I/O, never touch the browser, and are exercised in unit
tests against trimmed fixture HTML under
``tests/fixtures/aeat-pages/<surface>/``.
"""

from __future__ import annotations

from .expedientes import parse_expedientes
from .notificaciones import parse_notificaciones

__all__ = ["parse_expedientes", "parse_notificaciones"]
