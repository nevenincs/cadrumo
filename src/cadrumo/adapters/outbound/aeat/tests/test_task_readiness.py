"""Failure-aware readiness must never hide a failed browser owner."""

from __future__ import annotations

import asyncio

import pytest

from .process_support import wait_for_task_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_early_owner_failure_propagates_without_readiness() -> None:
    ready = asyncio.Event()
    failure = RuntimeError("browser failed before authentication")

    async def failed_owner() -> None:
        raise failure

    owner = asyncio.create_task(failed_owner())
    with pytest.raises(RuntimeError) as raised:
        await wait_for_task_readiness(ready.wait(), owner, after="authentication")
    assert raised.value is failure
    assert owner.done()
    assert not ready.is_set()
    assert not ready._waiters


@pytest.mark.asyncio
async def test_successful_owner_exit_without_readiness_is_a_failure() -> None:
    ready = asyncio.Event()

    async def exited_owner() -> None:
        return None

    owner = asyncio.create_task(exited_owner())
    with pytest.raises(pytest.fail.Exception, match="Owner exited before readiness"):
        await wait_for_task_readiness(ready.wait(), owner, after="authentication")
    assert not ready._waiters


@pytest.mark.asyncio
async def test_readiness_keeps_owner_live_until_caller_cleanup() -> None:
    ready, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def live_owner() -> None:
        try:
            ready.set()
            await release.wait()
        finally:
            cleaned.set()

    owner = asyncio.create_task(live_owner())
    try:
        await wait_for_task_readiness(ready.wait(), owner, after="authentication")
        assert not owner.done()
        assert not cleaned.is_set()
    finally:
        owner.cancel()
        await asyncio.gather(owner, return_exceptions=True)
    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_missing_readiness_is_bounded_and_waiter_is_reaped() -> None:
    ready, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def live_owner() -> None:
        try:
            await release.wait()
        finally:
            cleaned.set()

    owner = asyncio.create_task(live_owner())
    try:
        with pytest.raises(pytest.fail.Exception, match="Owner did not reach readiness"):
            await wait_for_task_readiness(ready.wait(), owner, after="authentication", timeout_seconds=0.01)
        assert not ready._waiters
        assert not owner.done()
    finally:
        owner.cancel()
        await asyncio.gather(owner, return_exceptions=True)
    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_readiness_error_propagates_and_keeps_owner_close_reachable() -> None:
    release = asyncio.Event()
    failure = RuntimeError("HTTP boundary readiness failed")

    async def failed_readiness() -> None:
        raise failure

    owner = asyncio.create_task(release.wait())
    try:
        with pytest.raises(RuntimeError) as raised:
            await wait_for_task_readiness(failed_readiness(), owner, after="blocked proof")
        assert raised.value is failure
        assert not owner.done()
    finally:
        owner.cancel()
        await asyncio.gather(owner, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_readiness_reaps_its_waiter_without_detaching_owner() -> None:
    ready, release = asyncio.Event(), asyncio.Event()
    owner = asyncio.create_task(release.wait())
    waiter = asyncio.create_task(wait_for_task_readiness(ready.wait(), owner, after="authentication"))
    try:
        for _ in range(100):
            if ready._waiters:
                break
            await asyncio.sleep(0)
        assert ready._waiters
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not ready._waiters
        assert not owner.done()
    finally:
        if not waiter.done():
            waiter.cancel()
        owner.cancel()
        await asyncio.gather(waiter, owner, return_exceptions=True)
