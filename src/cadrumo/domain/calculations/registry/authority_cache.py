"""Bounded concurrent retention for immutable authority components."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future
from dataclasses import dataclass
from threading import RLock, local
from typing import cast

from ....core.errors.hierarchy import CadrumoError

DEFAULT_AUTHORITY_CACHE_BUDGET = 64 * 1024 * 1024


class AuthorityCacheCycleError(CadrumoError):
    """A component loader recursively requested a key already on its stack."""


@dataclass(frozen=True, slots=True)
class RetainedAuthorityValue[V]:
    """Loaded value and the retained bytes it contributes to the shared budget."""

    value: V
    exclusive_weight: int
    shared_weights: tuple[tuple[Hashable, int], ...] = ()

    def __post_init__(self) -> None:
        """Reject negative or contradictory accounting declarations."""
        if self.exclusive_weight < 0 or any(weight < 0 for _, weight in self.shared_weights):
            raise ValueError("authority cache weights must be non-negative")
        tokens = tuple(token for token, _ in self.shared_weights)
        if len(tokens) != len(set(tokens)):
            raise ValueError("authority cache shared-weight tokens must be unique per value")


@dataclass(frozen=True, slots=True)
class AuthorityCacheTelemetry:
    """Accounted retention state, distinct from process RSS and active leases."""

    budget: int
    retained_weight: int
    entries: int
    in_flight: int


class AccountedAuthorityCache[K: Hashable, V]:
    """Coalesce loads and retain successful immutable values within one LRU budget."""

    def __init__(self, budget: int = DEFAULT_AUTHORITY_CACHE_BUDGET) -> None:
        """Create an empty cache with one positive retained-weight budget."""
        if budget <= 0:
            raise ValueError("authority cache budget must be positive")
        self._budget = budget
        self._values: OrderedDict[K, RetainedAuthorityValue[V]] = OrderedDict()
        self._in_flight: dict[K, Future[RetainedAuthorityValue[V]]] = {}
        self._lock = RLock()
        self._loading = local()

    def get_or_load(
        self,
        key: K,
        loader: Callable[[], RetainedAuthorityValue[V]],
    ) -> V:
        """Return a retained value or share exactly one concurrent load for ``key``."""
        stack = getattr(self._loading, "keys", ())
        if key in stack:
            raise AuthorityCacheCycleError(f"recursive authority component load for {key!r}")
        with self._lock:
            retained = self._values.get(key)
            if retained is not None:
                self._values.move_to_end(key)
                return retained.value
            future = self._in_flight.get(key)
            owner = future is None
            if future is None:
                future = Future()
                self._in_flight[key] = future
        if not owner:
            return cast(V, future.result().value)
        self._loading.keys = (*stack, key)
        try:
            loaded = loader()
            with self._lock:
                if self._entry_weight(loaded) <= self._budget:
                    self._values[key] = loaded
                    self._values.move_to_end(key)
                    self._evict_to_budget()
                future.set_result(loaded)
            return loaded.value
        except BaseException as exc:
            future.set_exception(exc)
            # The owner observes the original exception directly. Mark the Future's
            # exception retrieved so a load without waiters emits no warning.
            future.exception()
            raise
        finally:
            self._loading.keys = stack
            with self._lock:
                self._in_flight.pop(key, None)

    def discard(self, key: K) -> None:
        """Stop retaining a key without affecting values already held by callers."""
        with self._lock:
            self._values.pop(key, None)

    def clear(self) -> None:
        """Drop retained cache ownership; active loads and caller values remain valid."""
        with self._lock:
            self._values.clear()

    def telemetry(self) -> AuthorityCacheTelemetry:
        """Return retained-accounting telemetry without claiming a process RSS bound."""
        with self._lock:
            return AuthorityCacheTelemetry(
                budget=self._budget,
                retained_weight=self._retained_weight(),
                entries=len(self._values),
                in_flight=len(self._in_flight),
            )

    @staticmethod
    def _entry_weight(value: RetainedAuthorityValue[V]) -> int:
        return value.exclusive_weight + sum(weight for _, weight in value.shared_weights)

    def _retained_weight(self) -> int:
        exclusive = sum(item.exclusive_weight for item in self._values.values())
        shared: dict[Hashable, int] = {}
        for item in self._values.values():
            for token, weight in item.shared_weights:
                previous = shared.setdefault(token, weight)
                if previous != weight:
                    raise RuntimeError(f"authority cache shared token {token!r} has contradictory weights")
        return exclusive + sum(shared.values())

    def _evict_to_budget(self) -> None:
        while self._values and self._retained_weight() > self._budget:
            self._values.popitem(last=False)
