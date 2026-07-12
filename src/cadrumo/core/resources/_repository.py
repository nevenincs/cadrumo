""":class:`ResourceCacheRepository` base for the resource-management API.

Every read-only bundled-data resource in the project is exposed
through one :class:`ResourceRepository` implementation. The
repository owns its loader and its Identity Map cache; consumers
go through :class:`ResourceRegistry` instead of importing loader
functions directly.

The base class implements the ``get(key)`` / ``clear_cache``
contract on top of an unbounded ``dict[K, T]``. Subclasses
override ``_load(key) -> T`` to perform the actual file read
and Pydantic validation. The cache strategy is documented in
the resource-management-api ADR: process-lifetime memoisation,
no eviction, because the bundled data is immutable per install.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from typing import Protocol, runtime_checkable


@runtime_checkable
class ResourceRepository[T, K: Hashable](Protocol):
    """Typed read-only resource repository protocol."""

    def get(self, key: K) -> T:
        """Return the resource identified by ``key``."""
        ...

    def all(self) -> Iterable[T]:
        """Return every resource the repository can produce."""
        ...

    def clear_cache(self) -> None:
        """Empty this repository's Identity Map."""
        ...


class ResourceCacheRepository[T, K: Hashable]:
    """Default Repository implementation with an Identity Map cache.

    Subclasses override :meth:`_load` to read and validate one
    resource per key. The base class owns the cache behind the
    :class:`ResourceRepository` protocol; subclasses never touch it
    directly.
    """

    def __init__(self) -> None:
        self._cache: dict[K, T] = {}

    def get(self, key: K) -> T:
        """Return the resource for ``key``, loading on first access."""
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        loaded = self._load(key)
        self._cache[key] = loaded
        return loaded

    def all(self) -> Iterable[T]:
        """Return every resource the repository can produce.

        The default implementation raises ``NotImplementedError``
        because enumeration requires per-repository knowledge of
        the available keys. Subclasses with a finite key space
        (year-keyed catalogues, etc.) override.
        """
        raise NotImplementedError(f"{type(self).__name__} does not implement all(); override per repository")

    def clear_cache(self) -> None:
        """Empty the Identity Map.

        Tests that override Settings or otherwise change the
        bundled-data location between cases call this to force a
        reload on the next ``get``. Production code should not
        need to call this because the bundled data is immutable.
        """
        self._cache.clear()

    def _load(self, key: K) -> T:
        """Load one resource for ``key``.

        Subclasses MUST override. The default raises
        ``NotImplementedError`` so a subclass that forgets to
        implement loading fails immediately on first access.
        """
        raise NotImplementedError(f"{type(self).__name__}._load")
