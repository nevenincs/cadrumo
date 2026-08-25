"""Public-provider lifecycle tests over real HTTP and Playwright resources."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

import cadrumo.adapters.outbound.aeat.auth.session_store as session_store

from ......application.auth.diagnostics import load_auth_diagnostic
from ......application.auth.providers import AuthProvider
from ......application.auth_credentials import unnamed_certificate_credentials
from ......core import AuthProviderKind
from ......core.async_cleanup import AsyncResourceCleanupError
from ......core.auth_session_keys import aeat_auth_session_storage_state_path
from ......core.config import AEAT_CERTIFICATE_PROTECTED_URL, Settings
from ......tests.secure_sql import isolated_runtime_profile
from ...browser.tests.real_http_boundary import LocalHttpBoundary, opened_http_boundary, real_browser_factory
from ..authenticator import AEAT_SESSION_IDLE_TTL
from ..authenticator_types import AeatSession
from ..clave_movil import ClaveMovilAuthProvider
from ..clave_movil_metadata import ClaveMovilSessionMetadata
from ..clave_movil_support import ClaveMovilApprovalTimeoutError, ClaveMovilFailureMode
from ..clave_permanente_metadata import ClavePermanenteSessionMetadata
from ..clave_permanente_support import ClavePermanenteFailureMode
from ..errors import AeatLoginAssertionError, AuthError
from ..provider_selection import select_provider
from ..providers import CertificateSessionDetail, ClaveMovilLoginAssertionDetail, ClaveMovilSessionDetail
from ._authenticator_support import SECRET_PASSPHRASE, _build_bundle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_IDENTITY = "12345678Z"


def _settings(tmp_path: Path, kind: AuthProviderKind) -> Settings:
    values: dict[str, object] = {
        "cadrumo_local_storage_root": tmp_path / "storage",
        "cadrumo_token_dir": tmp_path / ".tokens",
        "cadrumo_browser_close_timeout_ms": 15_000,
    }
    if kind is AuthProviderKind.CERTIFICATE:
        values.update(
            cadrumo_certificate_path=_build_bundle(tmp_path),
            cadrumo_certificate_password_secret=SecretStr(SECRET_PASSPHRASE),
        )
    elif kind is AuthProviderKind.CLAVE_MOVIL:
        values["cadrumo_clave_movil_dni_nie"] = SecretStr(_IDENTITY)
    else:
        values.update(
            cadrumo_clave_permanente_dni_nie=SecretStr(_IDENTITY),
            cadrumo_clave_permanente_password=SecretStr(SECRET_PASSPHRASE),
        )
    return Settings.model_validate(values)


def _seed_clave_state(kind: AuthProviderKind, *, bucket_id: str) -> None:
    current = datetime.now(UTC)
    storage_state: dict[str, object] = {"cookies": [], "origins": []}
    storage_sha256 = session_store.storage_state_sha256(storage_state)
    if kind is AuthProviderKind.CLAVE_MOVIL:
        suffix = "clave-movil-storage"
        metadata = ClaveMovilSessionMetadata(
            identity_nif=_IDENTITY,
            authenticated_at=current,
            idle_deadline=current + timedelta(hours=1),
            storage_state_sha256=storage_sha256,
            landing_url=AEAT_CERTIFICATE_PROTECTED_URL,
        )
    else:
        suffix = "clave-permanente-storage"
        metadata = ClavePermanenteSessionMetadata(
            identity_nif=_IDENTITY,
            authenticated_at=current,
            idle_deadline=current + timedelta(hours=1),
            storage_state_sha256=storage_sha256,
            landing_url=AEAT_CERTIFICATE_PROTECTED_URL,
        )
    session_store.save(
        aeat_auth_session_storage_state_path(bucket_id, suffix),
        storage_state=storage_state,
        metadata=metadata.model_dump(mode="json"),
    )


async def _active_provider(
    kind: AuthProviderKind,
    *,
    boundary: LocalHttpBoundary,
    tmp_path: Path,
    bucket_id: str,
) -> tuple[AuthProvider, AeatSession]:
    settings = _settings(tmp_path, kind)
    if kind is not AuthProviderKind.CERTIFICATE:
        _seed_clave_state(kind, bucket_id=bucket_id)
    provider = select_provider(
        kind,
        settings=settings,
        browser_session_factory=real_browser_factory(
            boundary=boundary,
            profile_name=f"public-{kind.value}",
        ),
        certificate_credentials=(
            unnamed_certificate_credentials(settings) if kind is AuthProviderKind.CERTIFICATE else None
        ),
    )
    return provider, await provider.authenticate()


def _wrong_provider_session(kind: AuthProviderKind, active: AeatSession) -> AeatSession:
    detail = (
        ClaveMovilSessionDetail(dni_nie=_IDENTITY)
        if kind is AuthProviderKind.CERTIFICATE
        else CertificateSessionDetail(
            certificate_thumbprint="wrong-provider-thumbprint",
            certificate_subject="CN=WRONG PROVIDER,SERIALNUMBER=12345678Z",
        )
    )
    return AeatSession(
        authenticated_at=active.authenticated_at,
        idle_deadline=active.authenticated_at + AEAT_SESSION_IDLE_TTL,
        storage_state_path=active.storage_state_path,
        identity_nif=active.identity_nif,
        provider_detail=detail,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(AuthProviderKind))
async def test_public_verify_rejects_copied_and_wrong_provider_sessions(
    tmp_path: Path,
    kind: AuthProviderKind,
) -> None:
    """Every provider binds verification to its exact retained session object."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a070"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            provider, active = await _active_provider(
                kind,
                boundary=boundary,
                tmp_path=tmp_path,
                bucket_id=bucket_id,
            )
            try:
                with pytest.raises(AeatLoginAssertionError, match="exact active"):
                    await provider.verify(active.model_copy())
                with pytest.raises(AeatLoginAssertionError, match="exact active"):
                    await provider.verify(_wrong_provider_session(kind, active))
            finally:
                await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(AuthProviderKind))
async def test_public_close_waits_for_real_inflight_verification(
    tmp_path: Path,
    kind: AuthProviderKind,
) -> None:
    """Provider close cannot tear down a real context under active navigation."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a080"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            provider, active = await _active_provider(
                kind,
                boundary=boundary,
                tmp_path=tmp_path,
                bucket_id=bucket_id,
            )
            # The completion budget is derived from the SUT's OWN configured
            # timeouts, not a magic constant: once released, the verify probe
            # navigation is bounded by the navigation timeout and close() tears
            # down the real browser under the browser-close timeout. Budgeting
            # the sum (plus margin) means a test-side timeout can only fire when
            # the authenticator breaches its own guards (a genuine hang) — never
            # because real chromium teardown was merely slow under contention,
            # which a fixed 10s budget (shorter than the 15s close budget alone)
            # flaked on.
            sut = _settings(tmp_path, kind)
            completion_budget_s = (
                sut.cadrumo_browser_navigation_timeout_ms + sut.cadrumo_browser_close_timeout_ms
            ) / 1000 + 5.0
            boundary.configure("blocking")
            verify_task = asyncio.create_task(provider.verify(active))
            await boundary.wait_until_blocked()
            close_task = asyncio.create_task(provider.close())
            await asyncio.sleep(0.1)
            assert not close_task.done()
            boundary.release_request.set()
            assertion = await asyncio.wait_for(verify_task, timeout=completion_budget_s)
            await asyncio.wait_for(close_task, timeout=completion_budget_s)

    assert assertion.is_valid is True


@pytest.mark.asyncio
async def test_retryable_cleanup_error_closes_a_real_provider_owner(tmp_path: Path) -> None:
    """The central retry surface retains and closes a real provider graph."""
    kind = AuthProviderKind.CERTIFICATE
    bucket_id = "1f6b0000-0000-4000-8000-00000000a010"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            provider, _active = await _active_provider(
                kind,
                boundary=boundary,
                tmp_path=tmp_path,
                bucket_id=bucket_id,
            )
            cleanup_error = AsyncResourceCleanupError(
                (provider,),
                (RuntimeError("prior close attempt failed"),),
                retry_task_name="test-real-provider-cleanup-retry",
                close_attempts=2,
            )

            await cleanup_error.retry_cleanup()
            await provider.close()


@pytest.mark.asyncio
async def test_clave_movil_public_authenticate_refuses_real_pending_petition_page(tmp_path: Path) -> None:
    """Fresh Cl@ve Movil fails fast on AEAT's pending-request response."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a020"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            boundary.configure("clave-movil-pending")
            settings = _settings(tmp_path, AuthProviderKind.CLAVE_MOVIL)
            provider = select_provider(
                AuthProviderKind.CLAVE_MOVIL,
                settings=settings,
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="clave-movil-pending",
                ),
            )
            try:
                with pytest.raises(ClaveMovilApprovalTimeoutError) as raised:
                    await provider.authenticate()
            finally:
                await provider.close()

    assert raised.value.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED.value
    assert raised.value.context is not None
    assert raised.value.context["diagnostic_id"]


@pytest.mark.asyncio
async def test_clave_movil_public_verify_drives_real_own_name_representation_gate(tmp_path: Path) -> None:
    """An explicit target uses the selector and only own-name representation."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a030"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            provider, active = await _active_provider(
                AuthProviderKind.CLAVE_MOVIL,
                boundary=boundary,
                tmp_path=tmp_path,
                bucket_id=bucket_id,
            )
            external = Settings.external_constants()
            target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
            boundary.configure("clave-movil-representation")
            try:
                assert isinstance(provider, ClaveMovilAuthProvider)
                assertion = await provider.verify_for_target(active, target_url=target_url)
            finally:
                await provider.close()

    assert assertion.is_valid is True
    assert isinstance(assertion.assertion_detail, ClaveMovilLoginAssertionDetail)
    assert assertion.assertion_detail.landing_url is not None
    assert assertion.assertion_detail.landing_url.startswith(target_url)


@pytest.mark.asyncio
async def test_authenticated_representation_landing_records_phone_acceptance_without_operator_report(
    tmp_path: Path,
) -> None:
    """A real browser transition after Cl@ve is the phone-state authority."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a040"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            boundary.configure("clave-movil-representation-missing")
            settings_values = _settings(tmp_path, AuthProviderKind.CLAVE_MOVIL).model_dump()
            settings_values["cadrumo_clave_prefer_non_qr"] = False
            settings = Settings.model_validate(settings_values)
            provider = select_provider(
                AuthProviderKind.CLAVE_MOVIL,
                settings=settings,
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="clave-movil-representation-diagnostic",
                ),
            )
            external = Settings.external_constants()
            target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
            try:
                with pytest.raises(ClaveMovilApprovalTimeoutError) as raised:
                    assert isinstance(provider, ClaveMovilAuthProvider)
                    await provider.authenticate_for_target(target_url=target_url)
            finally:
                await provider.close()

        assert raised.value.context is not None
        diagnostic_id = raised.value.context["diagnostic_id"]
        assert isinstance(diagnostic_id, str)
        detail = load_auth_diagnostic(diagnostic_id)

    assert detail is not None
    assert detail.phone_state == "app_prompted_and_accepted"
    assert detail.phone_state_source == "aeat_authenticated_landing"
    assert detail.phone_state_observed_at is not None
    assert detail.phone_state_reported_at is None
    assert detail.operator_report_verdict is None


@pytest.mark.asyncio
async def test_clave_permanente_public_fresh_authenticate_persists_real_browser_state(tmp_path: Path) -> None:
    """Fresh Permanente login drives real form controls and encrypted persistence."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a050"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            boundary.configure("clave-permanente-success")
            settings = _settings(tmp_path, AuthProviderKind.CLAVE_PERMANENTE)
            provider = select_provider(
                AuthProviderKind.CLAVE_PERMANENTE,
                settings=settings,
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="clave-permanente-fresh",
                ),
            )
            try:
                session = await provider.authenticate()
            finally:
                await provider.close()
        persisted = session_store.load(
            aeat_auth_session_storage_state_path(bucket_id, "clave-permanente-storage"),
        )

    assert session.provider_kind is AuthProviderKind.CLAVE_PERMANENTE
    assert persisted is not None
    cookies = persisted.storage_state.get("cookies")
    assert isinstance(cookies, list)
    assert any(isinstance(cookie, dict) and cookie.get("name") == "AEAT_SESSION" for cookie in cookies)


@pytest.mark.asyncio
async def test_clave_permanente_public_authenticate_classifies_real_invalid_credentials_page(tmp_path: Path) -> None:
    """Rendered IdP refusal maps to the closed production failure taxonomy."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000a060"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            boundary.configure("clave-permanente-invalid")
            settings = _settings(tmp_path, AuthProviderKind.CLAVE_PERMANENTE)
            provider = select_provider(
                AuthProviderKind.CLAVE_PERMANENTE,
                settings=settings,
                browser_session_factory=real_browser_factory(
                    boundary=boundary,
                    profile_name="clave-permanente-invalid",
                ),
            )
            try:
                with pytest.raises(AuthError) as raised:
                    await provider.authenticate()
            finally:
                await provider.close()

    assert raised.value.context is not None
    assert raised.value.context["failure_mode"] == ClavePermanenteFailureMode.INVALID_CREDENTIALS.value
