"""CoreNotFoundError — shared base for all not-found failures across layers.

:class:`CoreNotFoundError` gives callers a single catch surface for any
"resource or record does not exist" failure regardless of which layer raises
it.  It inherits from both :class:`CoreError` (binding it to the registry
and the ``CoreError`` catch surface) and :class:`KeyError` (maintaining
compatibility with existing code that catches ``KeyError`` for missing-key
scenarios).
"""

from __future__ import annotations

from . import CoreError


class CoreNotFoundError(CoreError, KeyError):
    """Raised when a requested resource or record cannot be located.

    Domain- and application-layer not-found errors should descend from this
    class rather than directly from :class:`aeat.core.errors.AeatError` so
    callers can catch the whole not-found surface with a single
    ``except CoreNotFoundError`` clause.

    Inherits from :class:`KeyError` to maintain compatibility with existing
    call sites that catch ``KeyError`` for missing-key scenarios (e.g.
    ``dict``-like repository lookups).
    """
