"""Authentication recovery through real browser transitions and encrypted state."""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.auth_provider import AuthProviderKind
from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    CLAVE_QR_PROTECTED_QUERY_URL_CANARY,
    PROTECTED_RESOURCE_FOREIGN_HOST_CANARY,
    PROTECTED_RESOURCE_PATH_FIXTURE,
    PROTECTED_RESOURCE_QUERY_PATH_CANARY,
    PROTECTED_RESOURCE_URL_FIXTURE,
    WWW6_LOGIN_URL_FIXTURE,
)
from .....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...browser.tests.real_http_boundary import opened_http_boundary, real_browser_factory
from .. import session_store
from ..clave_movil import ClaveMovilAuthProvider
from ..clave_movil_state import ClaveMovilPageState, classify_clave_movil_page
from ..provider_selection import select_provider
from .test_auth_provider_real_lifecycle import _active_provider, _seed_clave_state, _settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter, pytest.mark.usefixtures("operation")]


@pytest.mark.asyncio
@pytest.mark.parametrize("fresh", [True, False])
async def test_external_submit_and_skipped_challenge_reach_protected_resource(tmp_path: Path, fresh: bool) -> None:
    """The observed sibling submit works for both fresh entry and retained verification."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000b030"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            provider = ClaveMovilAuthProvider(
                _settings(tmp_path, AuthProviderKind.CLAVE_MOVIL),
                browser_session_factory=real_browser_factory(boundary=boundary, profile_name="recovery"),
            )
            external = Settings.external_constants()
            target = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
            try:
                if fresh:
                    boundary.configure("clave-movil-representation-external-submit")
                    session = await provider.authenticate_for_target(target_url=target)
                else:
                    _seed_clave_state(AuthProviderKind.CLAVE_MOVIL, bucket_id=bucket_id)
                    session = await provider.authenticate()
                    boundary.configure("clave-movil-representation-external-submit")
                assertion = await provider.verify_for_target(session, target_url=target)
                assert assertion.is_valid
            finally:
                await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE])
async def test_resume_recaptures_cookies_rotated_by_live_probe(tmp_path: Path, kind: AuthProviderKind) -> None:
    """The encrypted successor contains server-issued cookies, not the stale input."""
    bucket_id = "1f6b0000-0000-4000-8000-00000000b040"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id):
        async with opened_http_boundary() as boundary:
            boundary.configure("clave-permanente-success")
            provider, session = await _active_provider(kind, boundary=boundary, tmp_path=tmp_path, bucket_id=bucket_id)
            try:
                assert session.storage_state_path is not None
                persisted = session_store.load(session.storage_state_path)
                assert persisted is not None
                cookies = persisted.storage_state["cookies"]
                assert isinstance(cookies, list)
                assert any(isinstance(cookie, dict) and cookie.get("name") == "AEAT_SESSION" for cookie in cookies)
                assert persisted.metadata["storage_state_sha256"] == persisted.storage_state_sha256
            finally:
                await provider.close()
            successor = select_provider(
                kind,
                settings=_settings(tmp_path, kind),
                browser_session_factory=real_browser_factory(boundary=boundary, profile_name="successor"),
            )
            try:
                resumed = await successor.authenticate()
                assert (await successor.verify(resumed)).is_valid
            finally:
                await successor.close()


@pytest.mark.parametrize(
    ("url", "html", "expected"),
    [
        (PROTECTED_RESOURCE_FOREIGN_HOST_CANARY, "", ClaveMovilPageState.UNTRUSTED),
        (
            PROTECTED_RESOURCE_QUERY_PATH_CANARY,
            "",
            ClaveMovilPageState.UNKNOWN,
        ),
        (PROTECTED_RESOURCE_URL_FIXTURE, "", ClaveMovilPageState.AUTHENTICATED),
        (WWW6_LOGIN_URL_FIXTURE, '<input id="NIF">', ClaveMovilPageState.IDENTITY),
        (
            WWW6_LOGIN_URL_FIXTURE,
            '<span id="spanCodigoVerificacion">ABC</span>',
            ClaveMovilPageState.WAITING,
        ),
        (
            # AEAT's waiting page as served on 2026-10-03: the code moved out of #spanCodigoVerificacion.
            CLAVE_QR_PROTECTED_QUERY_URL_CANARY,
            '<div id="divEsperaActiva"><div id="divRegistradoActivado"><div class="negrita codigoVerificacion">'
            'Código</div><div class="negrita codigoVerificacion fuenteTamanyo3em">ABC</div></div>'
            '<input type="button" id="botonCancelar"></div>',
            ClaveMovilPageState.WAITING,
        ),
        (WWW6_LOGIN_URL_FIXTURE, "Petición pendiente", ClaveMovilPageState.PENDING),
    ],
)
def test_observed_state_never_uses_target_in_query_as_authentication(
    url: str,
    html: str,
    expected: ClaveMovilPageState,
) -> None:
    assert (
        classify_clave_movil_page(
            url=url,
            html=html,
            target_path=PROTECTED_RESOURCE_PATH_FIXTURE,
            settings=Settings(),
        )
        is expected
    )
