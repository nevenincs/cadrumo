"""Bounded concurrent retention for immutable authority components."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future
from dataclasses import dataclass, fields, is_dataclass
from sys import getsizeof
from threading import RLock, get_ident, local

from ....core.errors.hierarchy import CadrumoError, InternalInvariantError
from ....core.type_guards import is_object_collection, is_object_mapping

DEFAULT_AUTHORITY_CACHE_BUDGET = 64 * 1024 * 1024


_SCALAR_LEAF_TYPES: frozenset[type] = frozenset({str, bytes, int, float, bool, complex, type(None)})
_DATACLASS_FIELD_NAMES: dict[type, tuple[str, ...]] = {}
_MODEL_FIELD_NAMES: dict[type, tuple[str, ...]] = {}


def _member_names(item_type: type, item: object) -> tuple[str, ...] | None:
    """Return the attribute names a dataclass or Pydantic model contributes, cached per type."""
    names = _DATACLASS_FIELD_NAMES.get(item_type)
    if names is not None:
        return names
    names = _MODEL_FIELD_NAMES.get(item_type)
    if names is not None:
        return names
    if is_dataclass(item):
        names = tuple(field.name for field in fields(item))
        _DATACLASS_FIELD_NAMES[item_type] = names
        return names
    model_fields = getattr(item_type, "model_fields", None)
    if is_object_mapping(model_fields):
        names = tuple(name for name in model_fields if isinstance(name, str))
        _MODEL_FIELD_NAMES[item_type] = names
        return names
    return None


def retained_object_size(value: object) -> int:
    """Estimate a decoded immutable graph without following types or callables.

    Every reachable object is counted once by identity; the walk is iterative
    because a large revision component reaches millions of members.
    """
    seen: set[int] = set()
    total = 0
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity)
        total += getsizeof(item)
        item_type = type(item)
        if item_type in _SCALAR_LEAF_TYPES or isinstance(item, type):
            continue
        if is_object_mapping(item):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif is_object_collection(item):
            stack.extend(item)
        else:
            names = _member_names(item_type, item)
            if names is not None:
                stack.extend(getattr(item, name) for name in names)
    return total


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
        self._exclusive_total = 0
        self._shared_total = 0
        self._shared_holders: dict[Hashable, tuple[int, int]] = {}
        self._in_flight: dict[K, Future[RetainedAuthorityValue[V]]] = {}
        self._owners: dict[K, int] = {}
        self._waiting_for: dict[int, K] = {}
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
                future = Future[RetainedAuthorityValue[V]]()
                self._in_flight[key] = future
                self._owners[key] = get_ident()
        if not owner:
            waiter = get_ident()
            with self._lock:
                self._refuse_wait_cycle(waiter, key)
                self._waiting_for[waiter] = key
            try:
                return future.result().value
            finally:
                with self._lock:
                    self._waiting_for.pop(waiter, None)
        self._loading.keys = (*stack, key)
        try:
            loaded = loader()
            with self._lock:
                if self._entry_weight(loaded) <= self._budget:
                    self._admit(key, loaded)
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
                self._owners.pop(key, None)

    def _refuse_wait_cycle(self, waiter: int, key: K) -> None:
        """Reject a wait edge that closes a cross-thread loader dependency cycle."""
        owner = self._owners.get(key)
        visited: set[int] = set()
        while owner is not None and owner not in visited:
            if owner == waiter:
                raise AuthorityCacheCycleError(f"concurrent authority component load cycle through {key!r}")
            visited.add(owner)
            owner_wait = self._waiting_for.get(owner)
            if owner_wait is None:
                return
            owner = self._owners.get(owner_wait)

    def discard(self, key: K) -> None:
        """Stop retaining a key without affecting values already held by callers."""
        with self._lock:
            released = self._values.pop(key, None)
            if released is not None:
                self._release(released)

    def clear(self) -> None:
        """Drop retained cache ownership; active loads and caller values remain valid."""
        with self._lock:
            self._values.clear()
            self._exclusive_total = 0
            self._shared_total = 0
            self._shared_holders.clear()

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

    def _admit(self, key: K, loaded: RetainedAuthorityValue[V]) -> None:
        """Retain ``loaded`` under ``key`` and account its weight incrementally.

        Running totals make admission and eviction cost one dictionary update
        per shared token rather than a walk over every retained entry. A shared
        token is charged once however many entries hold it, and a contradictory
        weight for a held token is refused before the entry is retained.
        """
        for token, weight in loaded.shared_weights:
            held = self._shared_holders.get(token)
            if held is not None and held[0] != weight:
                raise InternalInvariantError(f"authority cache shared token {token!r} has contradictory weights")
        previous = self._values.pop(key, None)
        if previous is not None:
            self._release(previous)
        self._values[key] = loaded
        self._exclusive_total += loaded.exclusive_weight
        for token, weight in loaded.shared_weights:
            held = self._shared_holders.get(token)
            if held is None:
                self._shared_holders[token] = (weight, 1)
                self._shared_total += weight
            else:
                self._shared_holders[token] = (weight, held[1] + 1)

    def _release(self, released: RetainedAuthorityValue[V]) -> None:
        self._exclusive_total -= released.exclusive_weight
        for token, weight in released.shared_weights:
            _, holders = self._shared_holders[token]
            if holders == 1:
                del self._shared_holders[token]
                self._shared_total -= weight
            else:
                self._shared_holders[token] = (weight, holders - 1)

    def _retained_weight(self) -> int:
        return self._exclusive_total + self._shared_total

    def _evict_to_budget(self) -> None:
        while self._values and self._retained_weight() > self._budget:
            _, evicted = self._values.popitem(last=False)
            self._release(evicted)
