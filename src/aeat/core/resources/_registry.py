"""Central resource registry and process-wide factory.

The :class:`ResourceRegistry` aggregates every Repository the
project exposes. The :func:`resources` factory builds the
registry once per process; subsequent calls return the cached
instance. Tests that override :class:`aeat.core.config.Settings`
to change the bundled-data location must call
``resources.cache_clear()`` to force a rebuild on the next
access.

The Repository fields land in subsequent phases of the
resource-management-api migration. For the foundation phase the
registry has no fields; the surface exists so consumers can
import :func:`resources` and the test suite can validate the
factory contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache


@dataclass(slots=True, frozen=True)
class ResourceRegistry:
    """Aggregate of every Repository the project exposes.

    Repository fields are added per migration phase. Each
    Repository owns its Identity Map cache; the registry
    aggregates them and exposes a uniform :meth:`clear` method.
    """

    def clear(self) -> None:
        """Clear every Repository's Identity Map.

        Iterates over every dataclass field whose value is a
        Repository instance and calls ``clear_cache()``. The
        method tolerates the empty foundation-phase registry
        (no fields) without error.
        """

        from ._repository import ResourceRepository

        for attr in self.__dataclass_fields__:
            value = getattr(self, attr)
            if isinstance(value, ResourceRepository):
                value.clear_cache()


@cache
def resources() -> ResourceRegistry:
    """Return the process-wide resource registry.

    Cached at first call. Tests that mutate Settings between
    cases call ``resources.cache_clear()`` to rebuild the
    registry with the new Settings values. Production code does
    not need to clear the cache because the bundled data is
    immutable for the process lifetime.
    """

    return ResourceRegistry()
