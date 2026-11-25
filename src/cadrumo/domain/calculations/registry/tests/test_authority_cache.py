from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from sys import getsizeof
from threading import Barrier, Lock, Thread

import pytest

from ..authority_cache import (
    AccountedAuthorityCache,
    AuthorityCacheCycleError,
    RetainedAuthorityValue,
    retained_object_size,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_same_key_concurrent_misses_share_one_load() -> None:
    cache: AccountedAuthorityCache[str, object] = AccountedAuthorityCache(100)
    barrier = Barrier(4)
    loads = 0
    lock = Lock()

    def read() -> object:
        barrier.wait()

        def load() -> RetainedAuthorityValue[object]:
            nonlocal loads
            with lock:
                loads += 1
            return RetainedAuthorityValue(object(), 10)

        return cache.get_or_load("one", load)

    with ThreadPoolExecutor(max_workers=4) as executor:
        values = tuple(executor.map(lambda _: read(), range(4)))
    assert loads == 1
    assert all(value is values[0] for value in values)


def test_budget_accounts_shared_values_once_and_does_not_retain_oversize() -> None:
    cache: AccountedAuthorityCache[str, str] = AccountedAuthorityCache(20)
    cache.get_or_load("a", lambda: RetainedAuthorityValue("a", 5, (("shared", 10),)))
    cache.get_or_load("b", lambda: RetainedAuthorityValue("b", 5, (("shared", 10),)))
    assert cache.stats().retained_weight == 20
    cache.get_or_load("large", lambda: RetainedAuthorityValue("large", 21))
    assert cache.stats().entries == 2


def test_decoded_graph_estimate_counts_shared_members_once_and_callers_survive_eviction() -> None:
    shared = ("grounded", "authority")
    value: dict[str, tuple[str, ...]] = {"left": shared, "right": shared}
    distinct = {"left": (*shared,), "right": (*shared,)}
    assert retained_object_size(value) < retained_object_size(distinct)

    cache: AccountedAuthorityCache[str, dict[str, tuple[str, ...]]] = AccountedAuthorityCache(1)
    caller_value = cache.get_or_load("first", lambda: RetainedAuthorityValue(value, 2))
    assert cache.stats().entries == 0
    assert caller_value == value


def test_failures_release_waiters_and_recursive_loads_refuse() -> None:
    cache: AccountedAuthorityCache[str, str] = AccountedAuthorityCache(20)

    def recursive() -> RetainedAuthorityValue[str]:
        cache.get_or_load("cycle", recursive)
        raise AssertionError("unreachable")

    with pytest.raises(AuthorityCacheCycleError):
        cache.get_or_load("cycle", recursive)
    assert cache.stats().in_flight == 0
    assert cache.get_or_load("cycle", lambda: RetainedAuthorityValue("recovered", 1)) == "recovered"


def test_cross_thread_dependency_cycle_fails_promptly_and_releases_both_loads() -> None:
    cache: AccountedAuthorityCache[str, str] = AccountedAuthorityCache(20)
    loaders_entered = Barrier(2)
    errors: list[BaseException | None] = [None, None]

    def loader(key: str, dependency: str) -> RetainedAuthorityValue[str]:
        loaders_entered.wait(timeout=2)
        cache.get_or_load(dependency, lambda: RetainedAuthorityValue(dependency, 1))
        raise AssertionError(f"cycle loader {key!r} unexpectedly completed")

    def run(index: int, key: str, dependency: str) -> None:
        try:
            cache.get_or_load(key, lambda: loader(key, dependency))
        except BaseException as exc:  # Capture both owner and waiter failures.
            errors[index] = exc

    threads = (
        Thread(target=run, args=(0, "a", "b"), daemon=True),
        Thread(target=run, args=(1, "b", "a"), daemon=True),
    )
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads), "cross-thread cache cycle did not resolve promptly"
    assert all(isinstance(error, AuthorityCacheCycleError) for error in errors)
    assert cache.stats().in_flight == 0


def test_a_composition_charges_its_parts_once_and_keeps_them_charged_after_their_own_eviction() -> None:
    cache: AccountedAuthorityCache[str, object] = AccountedAuthorityCache(100)
    part = ("part",)
    builds = 0

    def build() -> object:
        nonlocal builds
        builds += 1
        return (cache.get_or_load("part", lambda: RetainedAuthorityValue(part, 0, (("part-token", 40),))),)

    composed = cache.get_or_compose("composed", build)
    own_weight = getsizeof(composed)
    assert cache.stats().retained_weight == 40 + own_weight
    assert cache.stats().entries == 2

    cache.discard("part")
    assert cache.stats().retained_weight == 40 + own_weight
    assert cache.get_or_compose("composed", build) is composed
    assert builds == 1

    cache.discard("composed")
    assert cache.stats().retained_weight == 0


def test_a_composition_charges_exclusive_part_weight_but_not_what_its_parts_load_for_themselves() -> None:
    cache: AccountedAuthorityCache[str, object] = AccountedAuthorityCache(1000)

    def part_loader() -> RetainedAuthorityValue[object]:
        cache.get_or_load("dependency", lambda: RetainedAuthorityValue("dependency", 0, (("dependency-token", 300),)))
        return RetainedAuthorityValue("part", 7)

    composed = cache.get_or_compose("composed", lambda: (cache.get_or_load("part", part_loader),))

    assert cache.stats().retained_weight == 300 + 7 + 7 + getsizeof(composed)
    cache.discard("part")
    cache.discard("dependency")
    assert cache.stats().retained_weight == 7 + getsizeof(composed)


def test_a_composition_heavier_than_the_budget_is_returned_without_retention() -> None:
    cache: AccountedAuthorityCache[str, object] = AccountedAuthorityCache(50)
    builds = 0

    def build() -> object:
        nonlocal builds
        builds += 1
        return (cache.get_or_load("part", lambda: RetainedAuthorityValue("part", 0, (("part-token", 45),))),)

    first = cache.get_or_compose("composed", build)
    second = cache.get_or_compose("composed", build)

    assert first == second
    assert builds == 2
    assert cache.stats().entries == 1
    assert cache.stats().retained_weight == 45
