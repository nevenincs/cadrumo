"""Real Playwright lifecycle tests for the default browser-session factory."""

from __future__ import annotations

import asyncio
import time

import psutil
import pytest

from ......core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ......core.config import Settings
from ...auth.authenticator_types import BrowserSessionLike
from ...tests import wait_for_process_exit
from .. import BrowserError, Profile, create_browser_session, opened_browser_page, shared_playwright_runtime
from .._errors import BrowserPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _descendant_pids(pid: int) -> tuple[int, ...]:
    try:
        process = psutil.Process(pid)
        return tuple(int(child.pid) for child in process.children(recursive=True) if child.is_running())
    except psutil.NoSuchProcess:
        return ()


async def _wait_for_descendants(
    pid: int,
    *,
    expect_non_empty: bool,
    timeout_seconds: float = 10.0,
) -> tuple[int, ...]:
    deadline = time.monotonic() + timeout_seconds
    observed = _descendant_pids(pid)
    while time.monotonic() < deadline:
        if bool(observed) is expect_non_empty:
            return observed
        await asyncio.sleep(0.1)
        observed = _descendant_pids(pid)
    return observed


async def _wait_for_owner_entry(
    entered: asyncio.Event,
    owner_task: asyncio.Task[None],
    *,
    timeout_seconds: float = 20.0,
) -> None:
    """Wait for a real owner boundary while observing early task failure."""
    deadline = time.monotonic() + timeout_seconds
    while not entered.is_set():
        if owner_task.done():
            await owner_task
            pytest.fail("Playwright owner exited before reaching its body boundary")
        if time.monotonic() >= deadline:
            owner_task.cancel()
            await asyncio.gather(owner_task, return_exceptions=True)
            pytest.fail("Playwright owner did not reach its body boundary")
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_shared_playwright_runtime_reaps_its_real_driver() -> None:
    """The shared runtime context manager deterministically stops its owner."""
    async with shared_playwright_runtime() as playwright:
        driver_pid = playwright._impl_obj._connection._transport._proc.pid
        assert psutil.pid_exists(driver_pid)

    await wait_for_process_exit(driver_pid, after="session close")


@pytest.mark.asyncio
async def test_shared_playwright_runtime_finishes_real_teardown_under_cancellation() -> None:
    """Body cancellation cannot orphan the shared Playwright driver."""
    entered = asyncio.Event()
    hold_body = asyncio.Event()
    driver_pid = 0

    async def cancelled_owner() -> None:
        nonlocal driver_pid
        async with shared_playwright_runtime() as playwright:
            driver_pid = playwright._impl_obj._connection._transport._proc.pid
            entered.set()
            await hold_body.wait()

    owner_task = asyncio.create_task(cancelled_owner())
    await _wait_for_owner_entry(entered, owner_task)
    owner_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner_task

    assert driver_pid > 0
    await wait_for_process_exit(driver_pid, after="session close")


@pytest.mark.asyncio
async def test_opened_browser_page_reaps_all_real_owners_under_repeated_cancellation() -> None:
    """Repeated cancellation cannot split page/context/session/runtime teardown."""
    entered = asyncio.Event()
    hold_body = asyncio.Event()
    driver_pid = 0

    async def cancelled_owner() -> None:
        nonlocal driver_pid
        async with shared_playwright_runtime() as playwright:
            driver_pid = playwright._impl_obj._connection._transport._proc.pid
            async with opened_browser_page(
                playwright,
                Settings(),
                _profile("opened-page-cancel"),
            ) as (page, _context):
                await page.goto("data:text/html,<title>opened-page-cancel</title>")
                entered.set()
                await hold_body.wait()

    owner_task = asyncio.create_task(cancelled_owner())
    await _wait_for_owner_entry(entered, owner_task)
    owner_task.cancel()
    await asyncio.sleep(0)
    owner_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await owner_task

    assert driver_pid > 0
    await wait_for_process_exit(driver_pid, after="session close")


def _profile(name: str) -> Profile:
    return Profile(
        name=name,
        locale="es-ES",
        timezone_id="Europe/Madrid",
    )


def _assert_terminal_contract(
    error: BrowserError,
    *,
    condition: BrowserPreconditionCondition,
    facts: dict[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> None:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition.value
    assert evidence.evidence_id == f"{condition.value}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts


@pytest.mark.asyncio
async def test_default_browser_session_is_protocol_complete_and_reaps_runtime() -> None:
    """The production session owns Chromium and its Playwright driver."""
    settings = Settings()
    session = await create_browser_session(settings, _profile("protocol"))
    assert isinstance(session, BrowserSessionLike)

    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
    context = await session.create_context()
    page = await context.new_page()
    await page.goto("data:text/html,<title>browser-lifecycle</title>")
    assert await page.title() == "browser-lifecycle"
    assert await page.evaluate("navigator.webdriver") is False

    live_descendants = await _wait_for_descendants(driver_pid, expect_non_empty=True)
    assert live_descendants
    with pytest.raises(BrowserError) as excinfo:
        await session.create_context()
    assert "call close" not in str(excinfo.value).lower()
    assert excinfo.value.failure_mode == "session_busy"
    _assert_terminal_contract(
        excinfo.value,
        condition=BrowserPreconditionCondition.SESSION_AVAILABLE,
        facts={"browser_session_available": False},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )

    await context.close()
    assert await _wait_for_descendants(driver_pid, expect_non_empty=True)

    await session.close()
    await session.close()
    await wait_for_process_exit(driver_pid, after="session close")


@pytest.mark.asyncio
async def test_default_browser_session_reaps_browser_after_real_context_failure() -> None:
    """A real Playwright context-construction failure must not leave Chromium alive."""
    session = await create_browser_session(Settings(), _profile("context-failure"))
    driver_pid = session._playwright._impl_obj._connection._transport._proc.pid

    with pytest.raises(BrowserError) as excinfo:
        await session.create_context(
            storage_state={
                "cookies": "not-a-cookie-array",
                "origins": [],
            },
        )

    _assert_terminal_contract(
        excinfo.value,
        condition=BrowserPreconditionCondition.CONTEXT_CREATABLE,
        facts={
            "browser_context_creatable": False,
            "storage_state_supplied": True,
            "provisioner_supplied": False,
        },
        outcome=NoRecoveryOutcome.SAFETY,
    )

    assert await _wait_for_descendants(driver_pid, expect_non_empty=False) == ()
    await session.close()
    await wait_for_process_exit(driver_pid, after="session close")


@pytest.mark.asyncio
async def test_launch_failure_is_a_factual_typed_safety_outcome() -> None:
    """A real unavailable channel must not author a local install command."""
    settings = Settings(cadrumo_browser_channel="msedge-beta")
    session = await create_browser_session(settings, _profile("launch-hint"))
    try:
        with pytest.raises(BrowserError) as excinfo:
            await session.create_context()
        assert "playwright install" not in str(excinfo.value).lower()
        assert "playwright-doctor" not in str(excinfo.value).lower()
        assert excinfo.value.failure_mode == "browser_launch_failed"
        _assert_terminal_contract(
            excinfo.value,
            condition=BrowserPreconditionCondition.BROWSER_LAUNCHABLE,
            facts={"browser_launchable": False},
            outcome=NoRecoveryOutcome.SAFETY,
        )
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_context_creation_cancellation_reaps_browser_after_real_launch() -> None:
    """Cancellation drains Playwright context work before retained cleanup."""
    loop = asyncio.get_running_loop()
    prior_exception_handler = loop.get_exception_handler()
    unhandled_contexts: list[dict[str, object]] = []

    def capture_unhandled(_loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
        unhandled_contexts.append(context)

    loop.set_exception_handler(capture_unhandled)
    try:
        session = await create_browser_session(Settings(), _profile("context-cancel"))
        driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
        create_task = asyncio.create_task(session.create_context())
        try:
            deadline = time.monotonic() + 10
            while session._session._browser is None and not create_task.done():
                if time.monotonic() >= deadline:
                    pytest.fail("real Chromium launch did not reach the retained-owner boundary")
                await asyncio.sleep(0.01)
            assert session._session._browser is not None
            assert not create_task.done()

            create_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await create_task
            assert session._session._browser is None
        finally:
            if not create_task.done():
                create_task.cancel()
                await asyncio.gather(create_task, return_exceptions=True)
            await session.close()
            await wait_for_process_exit(driver_pid, after="session close")
        await asyncio.sleep(0)
        assert unhandled_contexts == [], f"Playwright left unhandled async outcomes: {unhandled_contexts!r}"
    finally:
        loop.set_exception_handler(prior_exception_handler)


@pytest.mark.asyncio
async def test_storage_state_is_loaded_only_from_explicit_in_memory_state() -> None:
    """Decrypted in-memory state is the only supported browser resume input."""
    settings = Settings()
    profile = _profile("explicit-storage")
    cookie_name = "explicit-storage-authority"

    seed_session = await create_browser_session(settings, profile)
    seed_context = await seed_session.create_context(storage_state={})
    try:
        await seed_context.add_cookies(
            [
                {
                    "name": cookie_name,
                    "value": "test-only",
                    "url": "https://example.test",
                },
            ],
        )
        seeded_state = await seed_context.storage_state()
    finally:
        await seed_context.close()
        await seed_session.close()

    implicit_session = await create_browser_session(settings, profile)
    implicit_context = await implicit_session.create_context()
    try:
        implicit_state = await implicit_context.storage_state()
        implicit_cookies = implicit_state.get("cookies", [])
        assert all(cookie.get("name") != cookie_name for cookie in implicit_cookies)
    finally:
        await implicit_context.close()
        await implicit_session.close()

    explicit_session = await create_browser_session(settings, profile)
    explicit_context = await explicit_session.create_context(
        storage_state=seeded_state,
    )
    try:
        explicit_state = await explicit_context.storage_state()
        explicit_cookies = explicit_state.get("cookies", [])
        assert any(cookie.get("name") == cookie_name for cookie in explicit_cookies)
    finally:
        await explicit_context.close()
        await explicit_session.close()


@pytest.mark.asyncio
async def test_real_browser_process_count_returns_to_zero_across_repeated_cycles() -> None:
    """Repeated real Chromium sessions must reap every Playwright driver."""
    settings = Settings()

    for index in range(3):
        session = await create_browser_session(settings, _profile(f"cycle-{index}"))
        driver_pid = session._playwright._impl_obj._connection._transport._proc.pid
        context = await session.create_context()
        page = await context.new_page()
        await page.goto(f"data:text/html,<title>cycle-{index}</title>")
        assert await page.title() == f"cycle-{index}"

        await context.close()
        await session.close()
        await wait_for_process_exit(driver_pid, after="session close")
