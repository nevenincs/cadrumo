"""A Sede view shares the encrypted AEAT session custody the CLI and TUI syncs use.

Every case drives the real application auth path against a registered
profile, the real encrypted session store, the real certificate provider and
real headless Chromium behind the local HTTP boundary. Only the operation
host's effect guard and effect reporter are stood in, because the supervisor
that supplies them is not the behaviour under test.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.acquisition_lock import (
    AuthAcquisitionLockState,
    acquire_auth_acquisition_lock,
    inspect_auth_acquisition_lock,
)
from cadrumo.application.auth.operator import configure_operator_auth
from cadrumo.application.auth.protocols import BrowserContextPort, BrowserSessionFactoryPort
from cadrumo.application.auth.sessions import (
    ViewSessionBaseline,
    ViewSessionPublication,
    ViewSessionPublicationOutcome,
    ViewSessionSeed,
    storage_state_paths,
)
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.auth_credentials import unnamed_certificate_credentials
from cadrumo.application.live.session import close_live_view_session, open_live_view_session
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.config_support import AEAT_CERTIFICATE_PROTECTED_URL
from cadrumo.core.operations import OperationEffect
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ...browser.tests.real_http_boundary import LocalHttpBoundary, opened_http_boundary, real_browser_factory
from .. import session_store
from ..authenticator import AeatAuthenticator
from ._auth_fixtures import CERTIFICATE_INPUT
from ._authenticator_support import _build_bundle

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]

_PROFILE_ID = "1f6b0000-0000-4000-8000-00000000c1c1"
_CERTIFICATE_NIF = "12345678Z"
_OTHER_NIF = "00000000T"
_SESSION_COOKIE = "AEAT_SESSION"
_COOKIE_SCENARIO = "clave-permanente-success"
_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()


class _OperationHost:
    """Record the effect reports and guard entries the supervisor would journal."""

    def __init__(self, *, interrupt_before_updated: BaseException | None = None) -> None:
        self.effects: list[OperationEffect] = []
        self.guard_entries = 0
        self.lock_state_at_unknown: AuthAcquisitionLockState | None = None
        self._interrupt_before_updated = interrupt_before_updated

    @asynccontextmanager
    async def effect_guard(self) -> AsyncGenerator[None]:
        self.guard_entries += 1
        yield

    async def report(self, effect: OperationEffect) -> None:
        if effect is OperationEffect.UPDATED and self._interrupt_before_updated is not None:
            # The write has run; the host is interrupted before journaling its outcome.
            raise self._interrupt_before_updated
        self.effects.append(effect)
        if effect is OperationEffect.UNKNOWN:
            self.lock_state_at_unknown = inspect_auth_acquisition_lock(
                load_settings(), AuthProviderKind.CERTIFICATE
            ).state


@contextmanager
def _certificate_profile(
    tmp_path: Path, operation: PinnedAuthorityOperation, *, tax_id: str = _CERTIFICATE_NIF
) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(
            cadrumo_active_profile=None,
            cadrumo_certificate_path=_build_bundle(tmp_path),
            cadrumo_certificate_password_secret=SecretStr(CERTIFICATE_INPUT),
            cadrumo_browser_close_timeout_ms=15_000,
        ),
        open_test_profile_session(_PROFILE_ID),
    ):
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": tax_id})
        configure_operator_auth("certificate", operator_scope_ports=_OPERATOR_SCOPE_PORTS, operation=operation)
        yield


def _session_path() -> Path:
    return storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state


def _stored_digest() -> str | None:
    return session_store.durable_storage_state_sha256(_session_path())


def _stored_cookie_names() -> set[str]:
    persisted = session_store.load(_session_path())
    assert persisted is not None
    cookies = persisted.storage_state.get("cookies")
    assert isinstance(cookies, list)
    return {str(cookie.get("name")) for cookie in cookies if isinstance(cookie, dict)}


def _lock_state() -> AuthAcquisitionLockState:
    return inspect_auth_acquisition_lock(load_settings(), AuthProviderKind.CERTIFICATE).state


async def _open(
    factory: BrowserSessionFactoryPort,
    host: _OperationHost,
    operation: PinnedAuthorityOperation,
) -> ViewSessionSeed:
    seed, _settings = await open_live_view_session(
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        authority_operation=operation,
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )
    return seed


async def _close(
    factory: BrowserSessionFactoryPort,
    host: _OperationHost,
    operation: PinnedAuthorityOperation,
    *,
    baseline: ViewSessionBaseline,
    view_context: BrowserContextPort,
) -> ViewSessionPublication:
    return await close_live_view_session(
        load_settings(),
        baseline=baseline,
        view_context=view_context,
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        browser_session_factory=factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        authority_operation=operation,
        effect_guard=host.effect_guard,
        on_session_write=host.report,
    )


@asynccontextmanager
async def _view_context(
    boundary: LocalHttpBoundary,
    storage_state: Mapping[str, object],
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


def _cookie_names(storage_state: Mapping[str, object]) -> set[str]:
    cookies = storage_state.get("cookies")
    assert isinstance(cookies, list)
    return {str(cookie.get("name")) for cookie in cookies if isinstance(cookie, dict)}


@pytest.mark.asyncio
async def test_a_verified_view_login_is_published_to_the_custody_every_sync_reuses(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The view seeds from custody, browses unlocked, and publishes what the next sync adopts."""
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-auth")
            seed = await _open(factory, _OperationHost(), operation)
            assert seed.baseline.storage_state_sha256 == _stored_digest()
            assert _lock_state() is AuthAcquisitionLockState.ABSENT

            host = _OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                # While the view browses, a sync can take the acquisition lock.
                with acquire_auth_acquisition_lock(
                    load_settings(), AuthProviderKind.CERTIFICATE, ttl_seconds=60, operation="sync-beside-view"
                ):
                    assert _lock_state() is AuthAcquisitionLockState.HELD
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.PUBLISHED
            assert publication.baseline.storage_state_sha256 == _stored_digest()
            assert publication.baseline.storage_state_sha256 != seed.baseline.storage_state_sha256
            assert host.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
            assert host.guard_entries == 1
            assert host.lock_state_at_unknown is AuthAcquisitionLockState.HELD
            assert _lock_state() is AuthAcquisitionLockState.ABSENT
            assert _SESSION_COOKIE in _stored_cookie_names()

            reopened = await _open(factory, _OperationHost(), operation)
            assert _SESSION_COOKIE in _cookie_names(reopened.storage_state)


@pytest.mark.asyncio
async def test_an_unchanged_capture_writes_nothing(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-unchanged")
            seed = await _open(factory, _OperationHost(), operation)
            host = _OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=False) as context:
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.UNCHANGED
            assert publication.baseline == seed.baseline
            assert host.effects == []
            assert _stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_a_session_whose_identity_is_not_the_active_profile_publishes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The provider accepts the capture, but its NIF is not the active profile NIF."""
    with _certificate_profile(tmp_path, operation, tax_id=_OTHER_NIF):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-identity")
            settings = load_settings()
            async with AeatAuthenticator(
                settings, credentials=unnamed_certificate_credentials(settings), browser_session_factory=factory
            ) as authenticator:
                await authenticator.authenticate()
            stored = session_store.load(_session_path())
            assert stored is not None
            baseline = ViewSessionBaseline(
                provider_kind=AuthProviderKind.CERTIFICATE,
                storage_state_sha256=stored.storage_state_sha256,
            )
            host = _OperationHost()
            async with _view_context(boundary, stored.storage_state, browse_to_session_cookie=True) as context:
                publication = await _close(factory, host, operation, baseline=baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert host.effects == []
            assert _stored_digest() == baseline.storage_state_sha256
            assert _SESSION_COOKIE not in _stored_cookie_names()


@pytest.mark.asyncio
async def test_a_refused_provider_probe_publishes_and_deletes_nothing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-refused")
            seed = await _open(factory, _OperationHost(), operation)
            host = _OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                boundary.configure("failure")
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.VERIFICATION_FAILED
            assert host.effects == []
            assert _stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_a_session_another_acquisition_published_meanwhile_stands(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-newer")
            seed = await _open(factory, _OperationHost(), operation)
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                # A sync resumes the stored session and publishes its refreshed capture.
                await _open(factory, _OperationHost(), operation)
                newer = _stored_digest()
                assert newer is not None
                assert newer != seed.baseline.storage_state_sha256
                host = _OperationHost()
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.KEPT_NEWER
            assert publication.baseline == seed.baseline
            assert host.effects == []
            assert _stored_digest() == newer


@pytest.mark.asyncio
async def test_a_live_acquisition_holding_the_lock_keeps_its_session(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-locked")
            seed = await _open(factory, _OperationHost(), operation)
            host = _OperationHost()
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                with acquire_auth_acquisition_lock(
                    load_settings(), AuthProviderKind.CERTIFICATE, ttl_seconds=60, operation="sync-acquiring"
                ):
                    publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.KEPT_NEWER
            assert host.effects == []
            assert _stored_digest() == seed.baseline.storage_state_sha256


@pytest.mark.asyncio
async def test_an_interruption_after_the_unknown_report_stays_unknown(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-unknown")
            seed = await _open(factory, _OperationHost(), operation)
            host = _OperationHost(interrupt_before_updated=RuntimeError("journal write interrupted"))
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                publication = await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert publication.outcome is ViewSessionPublicationOutcome.UNKNOWN
            assert publication.baseline == seed.baseline
            assert host.effects == [OperationEffect.UNKNOWN]
            assert _lock_state() is AuthAcquisitionLockState.ABSENT


@pytest.mark.asyncio
async def test_a_cancellation_after_the_unknown_report_propagates_with_unknown_standing(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _certificate_profile(tmp_path, operation):
        async with opened_http_boundary() as boundary:
            factory = real_browser_factory(boundary=boundary, profile_name="sede-view-cancelled")
            seed = await _open(factory, _OperationHost(), operation)
            host = _OperationHost(interrupt_before_updated=asyncio.CancelledError())
            async with _view_context(boundary, seed.storage_state, browse_to_session_cookie=True) as context:
                with pytest.raises(asyncio.CancelledError):
                    await _close(factory, host, operation, baseline=seed.baseline, view_context=context)

            assert host.effects == [OperationEffect.UNKNOWN]
            assert _lock_state() is AuthAcquisitionLockState.ABSENT
