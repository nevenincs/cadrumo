"""CoreNotFoundError — shared base for all not-found failures across layers.

:class:`CoreNotFoundError` gives callers a single catch surface for any
"resource or record does not exist" failure regardless of which layer raises
it.  It inherits from both :class:`CoreError` (binding it to the registry
and the ``CoreError`` catch surface) and :class:`KeyError` (binding lookup
misses to Python's mapping-style missing-key contract).
"""

from __future__ import annotations

from .hierarchy import CoreError


class CoreNotFoundError(CoreError, KeyError):
    """Raised when a requested resource or record cannot be located.

    Domain- and application-layer not-found errors should descend from this
    class rather than directly from :class:`core.errors.CadrumoError` so
    callers can catch the whole not-found surface with a single
    ``except CoreNotFoundError`` clause.

    Inherits from :class:`KeyError` so repository and catalogue lookup misses
    keep the same typed contract as Python mapping lookups.
    """
