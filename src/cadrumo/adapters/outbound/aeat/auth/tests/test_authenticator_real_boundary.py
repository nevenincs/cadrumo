"""Real HTTP and Playwright coverage for certificate authentication proof."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from ......application.auth_credentials import ActiveCertificateCredentials, unnamed_certificate_credentials
from ......core.auth_session_keys import aeat_auth_session_storage_state_path
from ......core.config import AEAT_CERTIFICATE_PROTECTED_URL, Settings
from ......core.errors import AeatLoginAssertionError
from ......tests.secure_sql import isolated_runtime_profile
from ...browser import DefaultBrowserSession
from ...browser.tests.real_http_boundary import opened_http_boundary, real_browser_factory
from ...tests import wait_for_process_exit
from ..authenticator import AEAT_SESSION_IDLE_TTL, AeatAuthenticator
from ..authenticator_persistence import PersistedSessionMetadata
from ..authenticator_types import AeatSession
from ..certificate import extract_nif_from_subject
from ..providers import CertificateSessionDetail
from ._authenticator_support import SECRET_PASSPHRASE, _build_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "1f6b0000-0000-4000-8000-00000000b0b0"


def _certificate_session() -> AeatSession:
    current = datetime.now(UTC)
    return AeatSession(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="real-boundary-thumbprint",
            certificate_subject="CN=REAL BOUNDARY,SERIALNUMBER=12345678Z",
        ),
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        cadrumo_certificate_path=_build_bundle(tmp_path),
        cadrumo_certificate_password_secret=SecretStr(SECRET_PASSPHRASE),
        cadrumo_token_dir=tmp_path / ".tokens",
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_browser_close_timeout_ms=15_000,
    )


def _seed_certificate_state(
    *,
    settings: Settings,
    storage_state_path: Path,
    expired: bool = False,
) -> None:
    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )
    certificate = authenticator.load_certificate()
    current = datetime.now(UTC)
    storage_state: dict[str, object] = {"cookies": [], "origins": []}
    metadata = PersistedSessionMetadata(
        certificate_thumbprint=certificate.sha256_thumbprint,
        certificate_subject=certificate.subject,
        certificate_nif=extract_nif_from_subject(certificate),
        authenticated_at=current,
        idle_deadline=(current - timedelta(seconds=1)) if expired else (current + timedelta(hours=1)),
        storage_state_sha256=session_store.storage_state_sha256(storage_state),
    )
    session_store.save(
        storage_state_path,
        storage_state=storage_state,
        metadata=metadata.model_dump(mode="json"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_valid", "expected_status", "expected_final_url"),
    [
        (
            "success",
            True,
            200,
            AEAT_CERTIFICATE_PROTECTED_URL,
        ),
        (
            "failure",
            False,
            503,
            AEAT_CERTIFICATE_PROTECTED_URL,
        ),
        ("wrong-host", False, 200, None),
        ("wrong-path", False, 200, None),
    ],
)
async def test_exact_protected_resource_matrix_uses_real_http_and_playwright(
    tmp_path: Path,
    scenario: str,
    expected_valid: bool,
    expected_status: int,
    expected_final_url: str | None,
) -> None:
    """The production probe fails closed on real responses and redirects."""
    async with opened_http_boundary() as boundary:
        boundary.configure(scenario)
        browser = await real_browser_factory(
            boundary=boundary,
            profile_name=f"proof-{scenario}",
        )(Settings())
        context = await browser.create_context()
        authenticator = AeatAuthenticator(
            Settings(),
            credentials=ActiveCertificateCredentials(
                certificate_path=None,
                password=None,
                friendly_name=None,
            ),
        )
        try:
            assertion = await authenticator._run_login_probe(context, _certificate_session())
        finally:
            await context.close()
            await browser.close()

    assert assertion.is_valid is expected_valid
    assert assertion.status_code == expected_status
    assert assertion.target_url == AEAT_CERTIFICATE_PROTECTED_URL
    if expected_final_url is None:
        assert assertion.final_url != AEAT_CERTIFICATE_PROTECTED_URL
    else:
        assert assertion.final_url == expected_final_url


@pytest.mark.asyncio
async def test_navigation_failure_redacts_redirect_payload_from_assertion_and_log(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """A real interrupted redirect never serialises its sensitive query value."""
    async with opened_http_boundary() as boundary:
        boundary.configure("sensitive-error")
        browser = await real_browser_factory(
            boundary=boundary,
            profile_name="redaction",
        )(Settings())
        context = await browser.create_context()
        authenticator = AeatAuthenticator(
            Settings(),
            credentials=ActiveCertificateCredentials(
                certificate_path=None,
                password=None,
                friendly_name=None,
            ),
        )
        caplog.set_level(logging.DEBUG, logger=AeatAuthenticator.__module__)
        try:
            assertion = await authenticator._run_login_probe(context, _certificate_session())
        finally:
            await context.close()
            await browser.close()

    assert assertion.is_valid is False
    assert assertion.error_message in {"Error", "protected_resource_mismatch"}
    assert boundary.sensitive_token not in assertion.model_dump_json()
    assert boundary.sensitive_token not in "\n".join(record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_authenticate_replaces_stale_encrypted_state_through_real_browser(tmp_path: Path) -> None:
    """The public path rejects stale state and completes one fresh browser proof."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        settings = _settings(tmp_path)
        storage_state_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "storage")
        _seed_certificate_state(settings=settings, storage_state_path=storage_state_path, expired=True)
        async with opened_http_boundary() as boundary:
            authenticator = AeatAuthenticator(
                settings,
                credentials=unnamed_certificate_credentials(settings),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="stale-fallback",
                ),
            )
            async with authenticator:
                session = await authenticator.authenticate()

        persisted = session_store.load(storage_state_path)
        assert persisted is not None
        assert session.identity_nif == extract_nif_from_subject(authenticator.load_certificate())
        assert persisted.metadata["certificate_thumbprint"] == session.certificate_thumbprint
        assert persisted.metadata["idle_deadline"] != persisted.metadata["authenticated_at"]


@pytest.mark.asyncio
async def test_failed_live_resume_is_deleted_before_single_fresh_fallback(tmp_path: Path) -> None:
    """One failed real resume probe is invalidated before fresh authentication."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        settings = _settings(tmp_path)
        storage_state_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "storage")
        _seed_certificate_state(settings=settings, storage_state_path=storage_state_path)
        async with opened_http_boundary() as boundary:
            boundary.configure("first-failure-then-success")
            authenticator = AeatAuthenticator(
                settings,
                credentials=unnamed_certificate_credentials(settings),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="resume-fallback",
                ),
            )
            async with authenticator:
                session = await authenticator.authenticate()

        persisted = session_store.load(storage_state_path)
        assert boundary.navigation_count == 2
        assert persisted is not None
        persisted_authenticated_at = datetime.fromisoformat(
            str(persisted.metadata["authenticated_at"]).replace("Z", "+00:00")
        )
        assert persisted_authenticated_at == session.authenticated_at


@pytest.mark.asyncio
async def test_reauthenticate_succeeds_then_propagates_a_real_probe_failure(tmp_path: Path) -> None:
    """Public reauthentication delegates once and leaves no failed persisted proof."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        settings = _settings(tmp_path)
        storage_state_path = aeat_auth_session_storage_state_path(_BUCKET_ID, "storage")
        async with opened_http_boundary() as boundary:
            authenticator = AeatAuthenticator(
                settings,
                credentials=unnamed_certificate_credentials(settings),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="reauthenticate",
                ),
            )
            async with authenticator:
                first = await authenticator.authenticate()
                refreshed = await authenticator.reauthenticate(first)
                assert refreshed is not first
                assert refreshed.authenticated_at >= first.authenticated_at
                boundary.configure("failure")
                with pytest.raises(AeatLoginAssertionError, match=r"authentication|verification"):
                    await authenticator.reauthenticate(refreshed)

        assert not session_store.exists(storage_state_path)


@pytest.mark.asyncio
async def test_authenticator_context_exit_reaps_real_browser_under_body_cancellation(tmp_path: Path) -> None:
    """A cancelled context body cannot interrupt authenticator-owned teardown."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        settings = _settings(tmp_path)
        async with opened_http_boundary() as boundary:
            authenticator = AeatAuthenticator(
                settings,
                credentials=unnamed_certificate_credentials(settings),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="cancelled-authenticator",
                ),
            )
            authenticated = asyncio.Event()
            hold_body = asyncio.Event()
            driver_pid = 0

            async def cancelled_owner() -> None:
                nonlocal driver_pid
                async with authenticator:
                    await authenticator.authenticate()
                    browser = authenticator._browser_session
                    assert isinstance(browser, DefaultBrowserSession)
                    driver_pid = browser._playwright._impl_obj._connection._transport._proc.pid
                    authenticated.set()
                    await hold_body.wait()

            owner_task = asyncio.create_task(cancelled_owner())
            await authenticated.wait()
            owner_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await owner_task

        assert driver_pid > 0
        await wait_for_process_exit(driver_pid, after="authenticator cancellation")


@pytest.mark.asyncio
async def test_authenticate_cancellation_retains_real_provider_owners_until_close(tmp_path: Path) -> None:
    """Cancellation during a blocked proof leaves every live handle close-reachable."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        settings = _settings(tmp_path)
        async with opened_http_boundary() as boundary:
            boundary.configure("blocking")
            authenticator = AeatAuthenticator(
                settings,
                credentials=unnamed_certificate_credentials(settings),
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="cancelled-proof",
                ),
            )
            driver_pid = 0
            async with authenticator:
                authenticate_task = asyncio.create_task(authenticator.authenticate())
                await boundary.wait_until_blocked()
                browser = authenticator._browser_session
                assert isinstance(browser, DefaultBrowserSession)
                assert authenticator._context is not None
                driver_pid = browser._playwright._impl_obj._connection._transport._proc.pid

                authenticate_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await authenticate_task
                assert authenticator._browser_session is browser
                assert authenticator._context is not None

        assert driver_pid > 0
        await wait_for_process_exit(driver_pid, after="authenticator cancellation")
