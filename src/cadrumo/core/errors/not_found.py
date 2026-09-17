"""CoreNotFoundError — shared base for all not-found failures across layers.

:class:`CoreNotFoundError` gives callers a single catch surface for any
"resource or record does not exist" failure regardless of which layer raises
it.  Its canonical registered ancestry is :class:`CoreError`, which binds
lookup misses to the central error registry and the ``CoreError`` catch
surface.
"""

from __future__ import annotations

from .hierarchy import CoreError


class CoreNotFoundError(CoreError):
    """Raised when a requested resource or record cannot be located.

    Domain- and application-layer not-found errors should descend from this
    class rather than directly from :class:`core.errors.hierarchy.CadrumoError` so
    callers can catch the whole not-found surface with a single
    ``except CoreNotFoundError`` clause.

    Repository and catalogue lookup misses use this registered type rather
    than relying on ``KeyError`` compatibility ancestry.
    """
