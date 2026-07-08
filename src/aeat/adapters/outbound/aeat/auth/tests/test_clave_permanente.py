"""Protocol-level tests for the Cl@ve Permanente authentication provider.

Exercises :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
against hand-written ``BrowserSessionLike`` stand-ins that record the
navigation and form interactions performed by the provider. The stand-ins
satisfy the same Protocol the production
:class:`~adapters.outbound.aeat.browser.BrowserSession` presents, so the
provider's choreography (selector navigation, credential form fill, post-auth
landing wait) is verified without a real browser.

These tests do not prove real AEAT authentication; the live handshake is
covered by the gated probe in ``test_clave_permanente_live.py``.

See Also:
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
        Provider whose selector, credential, persistence, resume, and verify
        contracts are exercised here.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`
        Public session detail asserted after fresh-login and resume paths.
    :class:`~adapters.outbound.aeat.auth._clave_permanente_metadata.ClavePermanenteSessionMetadata`
        Encrypted provider metadata persisted beside browser storage state.
    :mod:`~adapters.outbound.aeat.auth.tests._clave_permanente_support`
        Recording browser/page harness shared by these protocol tests.
    :mod:`~adapters.outbound.aeat.auth.tests.test_clave_permanente_live`
        Live Playwright probe covering the real AEAT Cl@ve Permanente surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ......tests.secure_sql import isolated_runtime_profile
from .. import _session_store
from .._clave_permanente import ClavePermanenteAuthProvider
from .._clave_permanente_metadata import ClavePermanenteSessionMetadata
from .._clave_permanente_support import ClavePermanenteFailureMode
from .._errors import AeatLoginAssertionError, AuthConfigurationError, AuthError
from .._providers import AuthProviderKind, ClavePermanenteSessionDetail
from ._clave_permanente_support import (
    _CLAVE_SURFACE,
    _DOMAINS,
    _aeat_url,
    _ElevationRequiredBrowserSession,
    _InitialNavigationTimeoutBrowserSession,
    _InvalidCredentialsBrowserSession,
    _RecordingBrowserSession,
    _run,
    _settings_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="clave-permanente-test"):
        yield


# ── enum + catalogue enrollment ──────────────────────────────────────────────


def test_auth_provider_kind_has_clave_permanente_member() -> None:
    assert AuthProviderKind.CLAVE_PERMANENTE == "clave_permanente"


def test_select_provider_dispatches_clave_permanente(tmp_path: Path) -> None:
    from .. import select_provider

    settings = _settings_for(
        tmp_path,
        AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
        AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
    )
    provider = select_provider(AuthProviderKind.CLAVE_PERMANENTE, settings=settings)
    assert isinstance(provider, ClavePermanenteAuthProvider)
    assert provider.kind == AuthProviderKind.CLAVE_PERMANENTE


# ── identity + password preconditions ───────────────────────────────────────


class TestPreconditions:
    def test_missing_identity_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2")
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match="AEAT_CLAVE_PERMANENTE_DNI_NIE"):
                await provider.authenticate()

        _run(run())

    def test_missing_password_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z")
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match="AEAT_CLAVE_PERMANENTE_PASSWORD"):
                await provider.authenticate()

        _run(run())

    def test_malformed_identity_raises_configuration_error(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="NOT-A-VALID-ID",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(AuthConfigurationError, match=r"NIF|NIE|identity"):
                await provider.authenticate()

        _run(run())


# ── describe() ───────────────────────────────────────────────────────────────


class TestDescribe:
    def test_describe_unconfigured(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False
        assert description.health_severity == "info"
        # Round-5 B2-style parity: never leak the raw env-var name.
        assert "AEAT_CLAVE_PERMANENTE" not in (description.health_summary or "")

    def test_describe_missing_password_only(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z")
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False

    def test_describe_configured(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is True
        assert description.identity_nif == "12345678Z"
        assert description.kind == AuthProviderKind.CLAVE_PERMANENTE

    def test_describe_invalid_identity(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="BAD",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is False
        assert description.health_severity == "warning"


# ── authenticate() — fresh login ─────────────────────────────────────────────


class TestAuthenticateFresh:
    def test_fresh_login_writes_encrypted_metadata_and_storage_state(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        target_path = settings.aeat_sede_expedientes_path
        browser_session = _RecordingBrowserSession(target_path=target_path)

        async def run() -> None:
            session = await provider.authenticate(browser_session=browser_session)
            assert session.provider_kind == AuthProviderKind.CLAVE_PERMANENTE
            assert session.identity_nif == "12345678Z"
            assert session.storage_state_path is not None
            persisted = _session_store.load(session.storage_state_path)
            assert persisted is not None
            metadata = ClavePermanenteSessionMetadata.model_validate_json(
                json.dumps(persisted.metadata, default=str),
            )
            assert metadata.identity_nif == "12345678Z"
            assert metadata.storage_state_sha256 == persisted.storage_state_sha256
            # Page observed the expected fill + submit sequence.
            assert browser_session.contexts, "a context must have been created"
            page = browser_session.contexts[0].pages[0]
            assert page.gotos[0].startswith(
                _CLAVE_SURFACE.selector_access_url_template.split("{target}", 1)[0],
            )
            assert (_CLAVE_SURFACE.username_input_selector, "12345678Z") in page.fills
            assert (_CLAVE_SURFACE.password_input_selector, "hunter2") in page.fills
            assert _CLAVE_SURFACE.submit_button_selector in page.clicks
            assert isinstance(session.provider_detail, ClavePermanenteSessionDetail)
            assert session.provider_detail.dni_nie == "12345678Z"
            assert session.provider_detail.landing_url == _aeat_url(_DOMAINS.www6, target_path)

        _run(run())

    def test_password_never_appears_in_persisted_metadata(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="super-secret-password",
        )
        provider = ClavePermanenteAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            session = await provider.authenticate(browser_session=browser_session)
            assert session.storage_state_path is not None
            persisted = _session_store.load(session.storage_state_path)
            assert persisted is not None
            metadata_json = json.dumps(persisted.metadata, default=str)
            assert "super-secret-password" not in metadata_json

        _run(run())

    def test_initial_selector_navigation_timeout_is_reported(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        browser_session = _InitialNavigationTimeoutBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(AuthError, match=r"initial navigation|selector") as excinfo:
                await provider.authenticate(browser_session=browser_session)
            assert excinfo.value.context is not None
            assert excinfo.value.context["failure_mode"] == ClavePermanenteFailureMode.INITIAL_NAVIGATION_TIMEOUT

        _run(run())
        assert browser_session.contexts
        assert browser_session.contexts[0].pages[0].gotos

    def test_invalid_credentials_marker_raises_typed_error(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="wrong-password",
        )
        provider = ClavePermanenteAuthProvider(settings)
        browser_session = _InvalidCredentialsBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(AuthError, match="rejected") as excinfo:
                await provider.authenticate(browser_session=browser_session)
            assert excinfo.value.context is not None
            assert excinfo.value.context["failure_mode"] == ClavePermanenteFailureMode.INVALID_CREDENTIALS

        _run(run())

    def test_elevation_required_marker_raises_typed_error_with_suggestion(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)
        browser_session = _ElevationRequiredBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(AuthError, match="elevation") as excinfo:
                await provider.authenticate(browser_session=browser_session)
            assert excinfo.value.context is not None
            assert excinfo.value.context["failure_mode"] == ClavePermanenteFailureMode.ELEVATION_REQUIRED
            assert excinfo.value.suggestion is not None
            assert "clave_movil" in excinfo.value.suggestion or "certificate" in excinfo.value.suggestion

        _run(run())


# ── authenticate() — resume ──────────────────────────────────────────────────


class TestAuthenticateResume:
    def test_resume_reuses_persisted_session_after_live_probe(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        target_path = settings.aeat_sede_expedientes_path

        async def run() -> None:
            fresh_provider = ClavePermanenteAuthProvider(settings)
            fresh_browser_session = _RecordingBrowserSession(target_path=target_path)
            fresh_session = await fresh_provider.authenticate(browser_session=fresh_browser_session)
            await fresh_provider.close()

            resume_provider = ClavePermanenteAuthProvider(settings)
            resume_browser_session = _RecordingBrowserSession(target_path=target_path)
            resumed_session = await resume_provider.authenticate(browser_session=resume_browser_session)
            assert resumed_session.identity_nif == fresh_session.identity_nif
            assert resumed_session.storage_state_path == fresh_session.storage_state_path
            await resume_provider.close()

        _run(run())

    def test_resume_falls_back_to_fresh_login_on_expired_idle_deadline(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        target_path = settings.aeat_sede_expedientes_path

        async def run() -> None:
            from datetime import UTC, datetime, timedelta

            fresh_provider = ClavePermanenteAuthProvider(settings)
            fresh_browser_session = _RecordingBrowserSession(target_path=target_path)
            fresh_session = await fresh_provider.authenticate(browser_session=fresh_browser_session)
            await fresh_provider.close()
            assert fresh_session.storage_state_path is not None

            persisted = _session_store.load(fresh_session.storage_state_path)
            assert persisted is not None
            metadata = ClavePermanenteSessionMetadata.model_validate_json(
                json.dumps(persisted.metadata, default=str),
            )
            expired_metadata = metadata.model_copy(
                update={"idle_deadline": datetime.now(UTC) - timedelta(minutes=1)},
            )
            _session_store.save(
                fresh_session.storage_state_path,
                storage_state=persisted.storage_state,
                metadata=expired_metadata.model_dump(mode="json"),
            )

            resume_provider = ClavePermanenteAuthProvider(settings)
            resume_browser_session = _RecordingBrowserSession(target_path=target_path)
            resumed_session = await resume_provider.authenticate(browser_session=resume_browser_session)
            # A second fresh login ran because the persisted metadata was expired.
            assert resume_browser_session.contexts
            assert resumed_session.identity_nif == "12345678Z"
            await resume_provider.close()

        _run(run())


# ── verify() ─────────────────────────────────────────────────────────────────


class TestVerify:
    def test_verify_without_active_context_raises(self, tmp_path: Path) -> None:
        settings = _settings_for(
            tmp_path,
            AEAT_CLAVE_PERMANENTE_DNI_NIE="12345678Z",
            AEAT_CLAVE_PERMANENTE_PASSWORD="hunter2",
        )
        provider = ClavePermanenteAuthProvider(settings)

        async def run() -> None:
            from ......core.time import now
            from .._authenticator_types import AeatSession

            attempted_at = now()
            session_without_context = AeatSession(
                provider_kind=AuthProviderKind.CLAVE_PERMANENTE,
                authenticated_at=attempted_at,
                idle_deadline=attempted_at,
                storage_state_path=None,
                identity_nif="12345678Z",
                provider_detail=ClavePermanenteSessionDetail(dni_nie="12345678Z"),
            )
            with pytest.raises(AeatLoginAssertionError, match="active browser context"):
                await provider.verify(session_without_context)

        _run(run())
