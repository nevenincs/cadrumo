from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest

from ..authority_cache import AccountedAuthorityCache, AuthorityCacheCycleError, RetainedAuthorityValue

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
    assert cache.telemetry().retained_weight == 20
    cache.get_or_load("large", lambda: RetainedAuthorityValue("large", 21))
    assert cache.telemetry().entries == 2


def test_failures_release_waiters_and_recursive_loads_refuse() -> None:
    cache: AccountedAuthorityCache[str, str] = AccountedAuthorityCache(20)

    def recursive() -> RetainedAuthorityValue[str]:
        cache.get_or_load("cycle", recursive)
        raise AssertionError("unreachable")

    with pytest.raises(AuthorityCacheCycleError):
        cache.get_or_load("cycle", recursive)
    assert cache.telemetry().in_flight == 0
    assert cache.get_or_load("cycle", lambda: RetainedAuthorityValue("recovered", 1)) == "recovered"
