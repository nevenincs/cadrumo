"""A Sede view shares the encrypted AEAT session custody the CLI and TUI syncs use.

Every case drives the real application auth path against a registered
profile, the real encrypted session store, the real certificate provider and
real headless Chromium behind the local HTTP boundary; only the operation
host is stood in.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from cadrumo.application.auth.acquisition_lock import (
    AuthAcquisitionLockState,
    acquire_auth_acquisition_lock,
)
from cadrumo.application.auth.protocols import BrowserContextPort, BrowserSessionFactoryPort
from cadrumo.application.auth.sessions import (
    ViewSessionBaseline,
    ViewSessionPublication,
    ViewSessionPublicationOutcome,
    ViewSessionSeed,
)
from cadrumo.application.auth_credentials import unnamed_certificate_credentials
from cadrumo.application.live.session import (
    ensure_live_authenticated_session,
    open_live_view_session,
    publish_live_view_session,
)
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings
from cadrumo.core.config_support import AEAT_CERTIFICATE_PROTECTED_URL
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...browser.tests.real_http_boundary import LocalHttpBoundary, opened_http_boundary, real_browser_factory
from .. import session_store
from ..authenticator import AeatAuthenticator
from .view_session_support import (
    CERTIFICATE_SECRET_BACKEND_FACTORY,
    OPERATOR_SCOPE_PORTS,
    SESSION_COOKIE,
    OperationHost,
    certificate_profile,
    lock_state,
    session_path,
    stored_cookie_names,
    stored_digest,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_OTHER_NIF = "00000000T"
_COOKIE_SCENARIO = "clave-permanente-success"


async def _open(
    factory: BrowserSessionFactoryPort,
    host: OperationHost,
    operation: PinnedAuthorityOperation,
) -> ViewSessionSeed:
    seed, _settings = await open_live_view_session(
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        authority_operation=operation,
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )
    return seed


async def _sync(
    factory: BrowserSessionFactoryPort,
    host: OperationHost,
    operation: PinnedAuthorityOperation,
) -> None:
    """A CLI or TUI sync: the canonical acquisition, publishing what it proves under the effect guard."""
    await ensure_live_authenticated_session(
        load_settings(),
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operation="sync-beside-view",
        target_url=None,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        profile_decode_context=operation.profile_decode_context(),
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )


async def _close(
    factory: BrowserSessionFactoryPort,
    host: OperationHost,
    operation: PinnedAuthorityOperation,
    *,
    baseline: ViewSessionBaseline,
    view_context: BrowserContextPort,
) -> ViewSessionPublication:
    return await publish_live_view_session(
        load_settings(),
        baseline=baseline,
        view_context=view_context,
        certificate_secret_backend_factory=CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
        authority_operation=operation,
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )


@asynccontextmanager
async def _view_context(
    boundary: LocalHttpBoundary,
    storage_state: Mapping[str, object] | None,
    *,
    browse_to_session_cookie: bool,
) -> AsyncGenerator[BrowserContextPort]:
    """Stand in for the view: a context seeded from custody, optionally browsed once."""
    browser = await real_browser_factory(boundary=boundary, profile_name="sede-view")(load_settings())
    try:
        context = await browser.create_context(storage_state=storage_state)
        try:
            if browse_to_session_cookie:
                boundary.configure(_COOKIE_SCENARIO)
                page = await context.new_page()
                await page.goto(AEAT_CERTIFICATE_PROTECTED_URL)
                await page.close()
            yield context
        finally:
            await context.close()
    finally:
        await browser.close()


def _cookie_names(storage_state: Mapping[str, object] | None) -> set[str]:
    assert storage_state is not None
    cookies = storage_state.get("cookies")
    assert isinstance(cookies, list)
    return {str(cookie.get("name")) for cookie in cookies if isinstance(cookie, dict)}


@pytest.mark.asyncio
async def test_a_verified_view_login_is_published_to_the_custody_every_sync_reuses(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The view seeds from custody, browses unlocked, and publishes what the next sync adopts."""
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-auth")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            assert seed.baseline.storage_state_sha256 == stored_digest()
            assert lock_state() is AuthAcquisitionLockState.ABSENT

            host = OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                # While the view browses, a sync can take the acquisition lock.
                with acquire_auth_acquisition_lock(
                    load_settings(), AuthProviderKind.CERTIFICATE, ttl_seconds=60, operation="sync-beside-view"
                ):
                    assert lock_state() is AuthAcquisitionLockState.HELD
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.PUBLISHED
            assert publication.baseline.storage_state_sha256 == stored_digest()
            assert publication.baseline.storage_state_sha256 != seed.baseline.storage_state_sha256
            assert host.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
            assert host.guard_entries == 1
            assert host.lock_state_at_unknown is AuthAcquisitionLockState.HELD
            assert lock_state() is AuthAcquisitionLockState.ABSENT
            assert SESSION_COOKIE in stored_cookie_names()

            reopened = await _open(factory, OperationHost(), operation)
            assert SESSION_COOKIE in _cookie_names(reopened.storage_state)


@pytest.mark.asyncio
async def test_an_unchanged_capture_writes_nothing(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-unchanged")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            host = OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=False) as context:
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.UNCHANGED
            assert publication.baseline == seed.baseline
            assert host.effects == []
            assert stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_a_session_whose_identity_is_not_the_active_profile_publishes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The provider accepts the capture, but its NIF is not the active profile NIF."""
    with certificate_profile(tmp_path, operation, tax_id=_OTHER_NIF):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-identity")
            settings = load_settings()
            async with AeatAuthenticator(
                settings, credentials=unnamed_certificate_credentials(settings), browser_session_factory=factory
            ) as authenticator:
                await authenticator.authenticate()
            stored = session_store.load(session_path())
            assert stored is not None
            baseline = ViewSessionBaseline(
                provider_kind=AuthProviderKind.CERTIFICATE,
                storage_state_sha256=stored.storage_state_sha256,
            )
            host = OperationHost()
            async with _view_context(boundary, stored.storage_state, browse_to_session_cookie=True) as context:
                publication = await _close(factory, host, operation, baseline=baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert host.effects == []
            assert stored_digest() == baseline.storage_state_sha256
            assert SESSION_COOKIE not in stored_cookie_names()


@pytest.mark.asyncio
async def test_a_refused_provider_probe_publishes_and_deletes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-refused")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            host = OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                boundary.configure("failure")
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert host.effects == []
            assert stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_a_session_another_acquisition_published_meanwhile_stands(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-newer")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                # A sync resumes the stored session and publishes its refreshed capture.
                await _sync(factory, OperationHost(), operation)
                newer = stored_digest()
                assert newer is not None
                assert newer != seed.baseline.storage_state_sha256
                host = OperationHost()
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.KEPT_NEWER
            assert publication.baseline == seed.baseline
            assert host.effects == []
            assert stored_digest() == newer


@pytest.mark.asyncio
async def test_a_live_acquisition_holding_the_lock_keeps_its_session(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-locked")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            host = OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                with acquire_auth_acquisition_lock(
                    load_settings(), AuthProviderKind.CERTIFICATE, ttl_seconds=60, operation="sync-acquiring"
                ):
                    publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.KEPT_NEWER
            assert host.effects == []
            assert stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_an_interruption_after_the_unknown_report_stays_unknown(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-unknown")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            host = OperationHost(interrupt_before_updated=RuntimeError("journal write interrupted"))
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.UNKNOWN
            assert publication.baseline == seed.baseline
            assert host.effects == [OperationEffect.UNKNOWN]
            assert lock_state() is AuthAcquisitionLockState.ABSENT


@pytest.mark.asyncio
async def test_a_cancellation_after_the_unknown_report_propagates_with_unknown_standing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-cancelled")
            await _sync(factory, OperationHost(), operation)
            seed = await _open(factory, OperationHost(), operation)
            host = OperationHost(interrupt_before_updated=asyncio.CancelledError())
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                with pytest.raises(asyncio.CancelledError):
                    await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert host.effects == [OperationEffect.UNKNOWN]
            assert lock_state() is AuthAcquisitionLockState.ABSENT
