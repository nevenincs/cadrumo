"""Protocol-level tests for the Cl@ve Movil authentication provider.

Exercises :class:`aeat.adapters.outbound.aeat.auth._clave_movil.ClaveMovilAuthProvider`
against hand-written ``BrowserSessionLike`` stand-ins that record the
navigation and form interactions performed by the provider. The
stand-ins satisfy the same Protocol the production
:class:`aeat.adapters.outbound.aeat.browser.BrowserSession` presents, so the
provider's choreography (selector clicks, form fills, post-auth
landing assertions) is verified without a real browser.

These tests do not prove real AEAT authentication or operator-side
Cl@ve state; the live handshake is covered by gated probes elsewhere.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .....core.config import Settings
from ....persistence.storage import EphemeralMasterKeyProvider
from ....persistence.storage.sql.engine import dispose_engine
from . import _session_store
from ._clave_movil import (
    ClaveMovilApprovalTimeoutError,
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
    ClaveMovilFailureMode,
    _classify_identity,
    _ClaveMovilSessionMetadata,
    _extract_verification_code_from_html,
)
from ._providers import AuthProviderKind, ClaveMovilSessionDetail

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

if TYPE_CHECKING:
    from ._authenticator import BrowserResponseLike

_EXTERNAL = Settings.external_constants()
_DOMAINS = _EXTERNAL.aeat.domains
_CLAVE_SURFACE = _EXTERNAL.aeat.clave_movil
_PRE303_SURFACE = _EXTERNAL.aeat.pre303


def _aeat_url(origin: str, path: str) -> str:
    return f"{origin}{path}"


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dispose_engine()
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


# ── Browser-session stand-ins ────────────────────────────────────────────────


class _RecordingPage:
    def __init__(
        self,
        *,
        target_path: str,
        verification_code: str = "YLL",
        authenticated: bool = False,
    ) -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self._authenticated = authenticated
        self.clicks: list[str] = []
        self.fills: list[tuple[str, str]] = []
        self.types: list[tuple[str, str]] = []
        self.gotos: list[str] = []
        self.url: str = ""
        self.closed = False

    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        # Simulate AEAT's selector dispatch. An authenticated resume
        # navigation to the AEAT selector bounces straight through to
        # the protected target path. Fresh-login navigations land on the
        # selector page itself (then our provider clicks through).
        if self._authenticated and _CLAVE_SURFACE.selector_access_path_marker in url:
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)
        else:
            self.url = url

        class _RecordingResponse:
            status = 200

        return _RecordingResponse()

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)
        # First click advances the selector to the QR page; subsequent clicks
        # are for the non-QR fallback (continue, continuar).
        if selector == _CLAVE_SURFACE.authorize_button_selector:
            self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_qr_path)
        elif selector == _CLAVE_SURFACE.non_qr_link_selector:
            self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)
        elif selector in (_CLAVE_SURFACE.continue_button_selector, _PRE303_SURFACE.representation_submit_selector):
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)

    async def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    async def type(self, selector: str, value: str, *, delay: float | None = None) -> None:
        del delay
        self.types.append((selector, value))

    async def wait_for_selector(self, selector: str, *, timeout: float | None = None) -> None:
        del selector, timeout

    async def text_content(self, selector: str) -> str | None:
        if selector == _CLAVE_SURFACE.verification_code_selector:
            self.url = _aeat_url(_DOMAINS.www6, self._target_path)
            return self._verification_code
        return None

    async def content(self) -> str:
        return "<html></html>"

    async def wait_for_url(self, matcher: str | Callable[[str], bool], *, timeout: float | None = None) -> None:
        del timeout
        # Simulate AEAT browser completion that redirects to the target.
        self.url = _aeat_url(_DOMAINS.www6, self._target_path)
        if not isinstance(matcher, str) and not matcher(self.url):
            raise TimeoutError("matcher rejected simulated URL")

    async def close(self) -> None:
        self.closed = True


class _SelectorDispatchPage(_RecordingPage):
    async def goto(self, url: str, *, timeout: float | None = None) -> BrowserResponseLike | None:
        del timeout
        self.gotos.append(url)
        self.url = url

        class _RecordingResponse:
            status = 200

        return _RecordingResponse()

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)
        if selector == _CLAVE_SURFACE.authorize_button_selector:
            self.url = _aeat_url(_DOMAINS.www1, self._target_path)


class _PendingPetitionPage(_RecordingPage):
    async def content(self) -> str:
        return (
            "<html><body>No ha sido posible generar una nueva petición de autenticación "
            "con Cl@ve Móvil. Rechace la petición pendiente en la APP Cl@ve.</body></html>"
        )


class _NoPushWaitStatePage(_RecordingPage):
    async def content(self) -> str:
        return "<html><body>Servicio no disponible temporalmente</body></html>"


class _CancelResponse:
    def __init__(self, *, status: int = 200) -> None:
        self.status = status
        self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.cancelar_clave_movil_path)


class _CancelableClavePage(_RecordingPage):
    def __init__(self, *, target_path: str, status: int = 200) -> None:
        super().__init__(target_path=target_path)
        self.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)
        self.cancel_response = _CancelResponse(status=status)
        self.evaluate_calls = 0
        self.wait_for_response_calls = 0

    async def evaluate(self, script: str) -> bool:
        del script
        self.evaluate_calls += 1
        return True

    async def wait_for_response(self, matcher: Callable[[object], bool], *, timeout: float | None = None) -> object:
        del timeout
        self.wait_for_response_calls += 1
        if matcher(self.cancel_response):
            return self.cancel_response
        raise TimeoutError("cancel response matcher did not match")


class _RecordingContext:
    def __init__(
        self,
        *,
        target_path: str,
        verification_code: str = "YLL",
        authenticated: bool = False,
    ) -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self._authenticated = authenticated
        self.pages: list[_RecordingPage] = []
        self.closed = False
        self._storage_state: dict[str, object] = {
            "cookies": [{"name": "AEAT_SESSION"}],
            "origins": [],
        }

    async def new_page(self) -> _RecordingPage:
        page = _RecordingPage(
            target_path=self._target_path,
            verification_code=self._verification_code,
            authenticated=self._authenticated,
        )
        self.pages.append(page)
        return page

    async def storage_state(self) -> dict[str, object]:
        return self._storage_state

    async def close(self) -> None:
        self.closed = True


class _SelectorDispatchContext(_RecordingContext):
    async def new_page(self) -> _SelectorDispatchPage:
        page = _SelectorDispatchPage(target_path=self._target_path)
        self.pages.append(page)
        return page


class _RecordingBrowserSession:
    """Stand-in for :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`.

    Implements only the surface the Cl@ve Movil provider uses:
    :meth:`create_context` and :meth:`close`. Resume contexts (those
    constructed with a ``storage_state_path``) are simulated as
    already-authenticated; fresh-login contexts land on the selector
    page so the provider can drive the click-through.
    """

    def __init__(self, *, target_path: str, verification_code: str = "YLL") -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self.contexts: list[_RecordingContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _RecordingContext:
        del provisioner
        # Resume paths construct contexts with a storage-state path; those
        # get the authenticated simulation. Fresh-login contexts don't.
        authenticated = storage_state_path is not None or storage_state is not None
        context = _RecordingContext(
            target_path=self._target_path,
            verification_code=self._verification_code,
            authenticated=authenticated,
        )
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        self.closed = True


class _SelectorDispatchBrowserSession(_RecordingBrowserSession):
    async def create_context(
        self,
        *,
        provisioner: object | None = None,
        storage_state_path: Path | None = None,
        storage_state: Mapping[str, object] | None = None,
    ) -> _SelectorDispatchContext:
        del provisioner, storage_state_path, storage_state
        context = _SelectorDispatchContext(target_path=self._target_path)
        self.contexts.append(context)
        return context


def _settings_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    from pydantic_settings import SettingsConfigDict

    for name in Settings.env_var_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path))
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # Pydantic-settings reads env/.env by default; a developer who ran
    # `aeat config auth configure` would then leak their real DNI/NIE into
    # the test suite. Point the test Settings at a non-existent file.
    class _IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8", env_ignore_empty=True)

    return _IsolatedSettings()


# ── identity classification ──────────────────────────────────────────────────


class TestIdentityClassification:
    def test_classifies_dni(self) -> None:
        assert _classify_identity("12345678Z") == "DNI"

    def test_classifies_nie(self) -> None:
        assert _classify_identity("X1234567L") == "NIE"

    def test_rejects_cif(self) -> None:
        with pytest.raises(ClaveMovilConfigurationError, match=r"NIF|NIE|identity|CIF"):
            _classify_identity("B12345674")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ClaveMovilConfigurationError, match=r"NIF|NIE|identity|empty"):
            _classify_identity("")


# ── describe() ──────────────────────────────────────────────────────────────


class TestDescribe:
    def test_describe_unconfigured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings_for(tmp_path, monkeypatch)
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False
        # Round-5 B2: refusal text is user prose, never the raw
        # env-var name; severity is ``info`` for an undeclared state,
        # not the loudest ``error`` token.
        assert "AEAT_CLAVE_MOVIL_DNI_NIE" not in (description.health_summary or "")
        assert description.health_severity == "info"
        assert "DNI" in (description.health_summary or "") or "NIE" in (description.health_summary or "")

    def test_describe_configured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is True
        assert description.identity_nif == "12345678Z"
        assert description.kind == AuthProviderKind.CLAVE_MOVIL

    def test_describe_invalid_identity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="BAD")
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is False
        assert "not a valid DNI" in (description.health_summary or "")


# ── authenticate() — fresh login ─────────────────────────────────────────────


class TestAuthenticateFresh:
    def test_qr_flow_writes_encrypted_metadata_and_storage_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z",
        )
        provider = ClaveMovilAuthProvider(settings)
        target_path = settings.aeat_sede_expedientes_path
        browser_session = _RecordingBrowserSession(target_path=target_path, verification_code="YLL")

        async def run() -> None:
            session = await provider.authenticate(browser_session=browser_session)
            assert session.provider_kind == AuthProviderKind.CLAVE_MOVIL
            assert session.identity_nif == "12345678Z"
            assert session.storage_state_path is not None
            assert not session.storage_state_path.exists()
            assert not session.storage_state_path.with_suffix(".meta.json").exists()
            persisted = _session_store.load(session.storage_state_path)
            assert persisted is not None
            metadata = _ClaveMovilSessionMetadata.model_validate_json(json.dumps(persisted.metadata, default=str))
            assert metadata.identity_nif == "12345678Z"
            assert metadata.used_non_qr_fallback is False
            assert metadata.verification_code == "YLL"
            assert metadata.storage_state_sha256 == persisted.storage_state_sha256
            # Page observed the expected click sequence.
            assert browser_session.contexts, "a context must have been created"
            page = browser_session.contexts[0].pages[0]
            assert page.gotos[0].startswith(
                _CLAVE_SURFACE.selector_access_url_template.split("{target}", 1)[0]
            )
            assert _CLAVE_SURFACE.authorize_button_selector in page.clicks
            # No form fill (QR flow skips the non-QR form entirely)
            assert page.fills == []
            # provider_detail is Cl@ve-shaped
            assert isinstance(session.provider_detail, ClaveMovilSessionDetail)
            assert session.provider_detail.dni_nie == "12345678Z"
            assert session.provider_detail.landing_url == _aeat_url(_DOMAINS.www6, target_path)

        asyncio.run(run())

    def test_non_qr_fallback_fills_dni_form(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z",
            AEAT_CLAVE_MOVIL_DNI_FECHA="2030-01-01",
            AEAT_CLAVE_PREFER_NON_QR="true",
        )
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            session = await provider.authenticate(browser_session=browser_session)
            detail = session.provider_detail
            assert isinstance(detail, ClaveMovilSessionDetail)
            assert detail.used_non_qr_fallback is True
            page = browser_session.contexts[0].pages[0]
            assert ("#NIF", "12345678Z") in page.types
            assert ("#FECHA", "2030-01-01") in page.types
            assert page.clicks.count(_CLAVE_SURFACE.authorize_button_selector) == 1
            assert _CLAVE_SURFACE.continue_button_selector in page.clicks

        asyncio.run(run())

    def test_non_qr_fallback_fills_nie_support_form(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="Y0000000Z",
            AEAT_CLAVE_MOVIL_NIE_SOPORTE="E00000000",
            AEAT_CLAVE_PREFER_NON_QR="true",
        )
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            session = await provider.authenticate(browser_session=browser_session)
            detail = session.provider_detail
            assert isinstance(detail, ClaveMovilSessionDetail)
            assert detail.used_non_qr_fallback is True
            page = browser_session.contexts[0].pages[0]
            assert ("#NIF", "Y0000000Z") in page.types
            assert ("#SOPORTE", "E00000000") in page.types
            assert page.clicks.count(_CLAVE_SURFACE.authorize_button_selector) == 1
            assert _CLAVE_SURFACE.continue_button_selector in page.clicks

        asyncio.run(run())

    def test_non_qr_fallback_rejects_missing_nie_support(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="Y0000000Z",
            AEAT_CLAVE_PREFER_NON_QR="true",
        )
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError, match=r"AEAT_CLAVE_MOVIL_NIE_SOPORTE|non-QR|NIE"):
                await provider.authenticate(browser_session=browser_session)

        asyncio.run(run())

    def test_non_qr_fallback_rejects_missing_fecha(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z",
            AEAT_CLAVE_PREFER_NON_QR="true",
        )
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError, match=r"AEAT_CLAVE_MOVIL_DNI_FECHA|non-QR|fallback"):
                await provider.authenticate(browser_session=browser_session)

        asyncio.run(run())

    def test_missing_identity_raises_configuration_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch)
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError, match=r"identity|NIF|NIE|configuration"):
                await provider.authenticate(browser_session=browser_session)

        asyncio.run(run())


class TestPostAuthLanding:
    def test_verify_clicks_selector_for_explicit_target_probe(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ._authenticator import AeatSession

        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
        target_path = provider._target_path_from_url(target_url)
        context = _SelectorDispatchContext(target_path=target_path)
        provider._context = context
        now = datetime.now(UTC)
        session = AeatSession(
            provider_kind=AuthProviderKind.CLAVE_MOVIL,
            authenticated_at=now,
            idle_deadline=now + timedelta(minutes=18),
            storage_state_path=None,
            identity_nif="12345678Z",
            provider_detail=ClaveMovilSessionDetail(
                dni_nie="12345678Z",
                used_non_qr_fallback=True,
                verification_code="YLL",
                landing_url=None,
            ),
        )

        async def run() -> None:
            assertion = await provider.verify(session, target_url=target_url)
            assert assertion.is_valid is True

        asyncio.run(run())

        page = context.pages[0]
        assert external.aeat.clave_movil.selector_access_path_marker in page.gotos[0]
        assert external.aeat.clave_movil.authorize_button_selector in page.clicks

    def test_explicit_verification_target_uses_selector_dispatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
        target_path = provider._target_path_from_url(target_url)

        probe_url = provider._probe_url_for_verification(
            explicit_target_url=target_url,
            resolved_target_url=target_url,
            target_path=target_path,
        )

        assert external.aeat.clave_movil.selector_access_path_marker in probe_url
        assert probe_url != target_url

    def test_implicit_verification_target_keeps_recorded_landing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        landing_url = f"{external.aeat.domains.www6}{external.aeat.sede_paths.expedientes_resumen}"
        target_path = provider._target_path_from_url(landing_url)

        probe_url = provider._probe_url_for_verification(
            explicit_target_url=None,
            resolved_target_url=landing_url,
            target_path=target_path,
        )

        assert probe_url == landing_url

    def test_authenticated_landing_accepts_pre303_post_auth_redirect(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()

        accepted = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}",
            target_path=external.aeat.pre303.presentation_service_path,
        )
        auth_gate = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.sede}{external.aeat.sede_paths.auth_gate_4033}",
            target_path=external.aeat.pre303.presentation_service_path,
        )
        selector = provider._is_authenticated_aeat_landing(
            landing_url=external.aeat.clave_movil.selector_access_url_template.format(
                target=external.aeat.pre303.presentation_service_path
            ),
            target_path=external.aeat.pre303.presentation_service_path,
        )
        other_app = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.www1}{external.aeat.sede_paths.iva_compensation_wallet}",
            target_path=external.aeat.pre303.presentation_service_path,
        )

        assert accepted is True
        assert auth_gate is False
        assert selector is False
        assert other_app is False

    def test_representation_dispatcher_continues_only_own_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _RecordingPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path)

        async def run() -> None:
            await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=1_000)

        asyncio.run(run())
        assert page.clicks == [
            _PRE303_SURFACE.representation_own_name_label_selector,
            _PRE303_SURFACE.representation_submit_selector,
        ]


class TestPendingPetitionRefusal:
    def test_pending_petition_page_fails_fast_with_actionable_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _PendingPetitionPage(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"Cl@ve|pending|prior|petition") as excinfo:
                await provider._raise_if_pending_request_error(page)
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert excinfo.value.context is not None
            assert excinfo.value.context["failure_mode"] == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert "detected_markers" in excinfo.value.context
            assert "diagnostic_id" in excinfo.value.context
            assert excinfo.value.suggestion is not None

        asyncio.run(run())

    def test_post_auth_wait_detects_pending_petition_refusal_during_poll(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _PendingPetitionPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"Cl@ve|pending|prior|refused") as excinfo:
                await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=100)
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert excinfo.value.context is not None
            assert excinfo.value.context["reason"] == "aeat-refused-new-clave-movil-petition"

        asyncio.run(run())

    def test_pending_request_cancellation_waits_for_aeat_cancel_response(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _CancelableClavePage(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            await provider._cancel_pending_auth_request(page)

        asyncio.run(run())

        assert page.evaluate_calls == 1
        assert page.wait_for_response_calls == 1

    def test_pending_request_cancel_confirmation_rejects_failed_response(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _CancelableClavePage(target_path=settings.aeat_sede_expedientes_path, status=500)

        async def run() -> bool:
            return await provider._wait_for_cancel_confirmation(page)

        assert asyncio.run(run()) is False


class TestClaveWaitState:
    def test_extracts_verification_code_from_rendered_non_qr_html(self) -> None:
        html = """
        <div class="negrita codigoVerificacion">Código de verificación</div>
        <div class="negrita codigoVerificacion fuenteTamanyo3em">IL9</div>
        <form><input id="inputDNIReadonly" value="00000000T"></form>
        """

        assert _extract_verification_code_from_html(html) == "IL9"

    def test_login_refuses_to_wait_without_observed_confirmation_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _NoPushWaitStatePage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"confirmation waiting state") as excinfo:
                await provider._assert_push_wait_state(
                    page,
                    target_path=settings.aeat_sede_expedientes_path,
                    verification_code=None,
                    used_non_qr_fallback=True,
                )
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PUSH_WAIT_STATE_NOT_REACHED
            assert excinfo.value.context is not None
            assert excinfo.value.context["reason"] == "aeat-clave-movil-wait-state-not-reached"
            assert excinfo.value.context["verification_code_present"] is False
            assert "diagnostic_id" in excinfo.value.context

        asyncio.run(run())

    def test_login_accepts_observed_verification_code_as_wait_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _NoPushWaitStatePage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)

        async def run() -> None:
            await provider._assert_push_wait_state(
                page,
                target_path=settings.aeat_sede_expedientes_path,
                verification_code="YLL",
                used_non_qr_fallback=True,
            )

        asyncio.run(run())


# ── authenticate() — resume path ─────────────────────────────────────────────


class TestProbePersistedSession:
    """:meth:`ClaveMovilAuthProvider.probe_persisted_session` never touches the fresh-login path."""

    def test_probe_without_persisted_session_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        browser_session = _RecordingBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            from ._authenticator import AeatLoginAssertionError

            with pytest.raises(AeatLoginAssertionError, match="no persisted"):
                await provider.probe_persisted_session(browser_session=browser_session)

        asyncio.run(run())

    def test_probe_uses_existing_encrypted_session_without_invalidating_on_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        target_path = settings.aeat_sede_expedientes_path
        # Seed a session via a fresh login.
        browser_session_login = _RecordingBrowserSession(target_path=target_path)

        async def seed() -> None:
            await provider.authenticate(browser_session=browser_session_login)
            await provider.close()

        asyncio.run(seed())

        from aeat.application.workflow._models import require_active_bucket_id

        storage_path = settings.aeat_token_dir / f"{require_active_bucket_id()}-clave-movil-storage.json"
        assert _session_store.exists(storage_path)
        assert not storage_path.exists()
        assert not storage_path.with_suffix(".meta.json").exists()

        # Probe against a fresh provider instance; encrypted session must survive.
        probe_provider = ClaveMovilAuthProvider(settings)
        browser_session_probe = _RecordingBrowserSession(target_path=target_path)

        async def probe() -> None:
            session, assertion = await probe_provider.probe_persisted_session(browser_session=browser_session_probe)
            assert session.identity_nif == "12345678Z"
            assert assertion.target_url
            await probe_provider.close()

        asyncio.run(probe())
        assert _session_store.exists(storage_path)
        assert not storage_path.exists()
        assert not storage_path.with_suffix(".meta.json").exists()


class TestResume:
    def test_resume_from_fresh_encrypted_session(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(
            tmp_path,
            monkeypatch,
            AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z",
        )
        provider = ClaveMovilAuthProvider(settings)
        target_path = settings.aeat_sede_expedientes_path
        browser_session_a = _RecordingBrowserSession(target_path=target_path)

        async def run_first() -> None:
            await provider.authenticate(browser_session=browser_session_a)
            await provider.close()

        asyncio.run(run_first())

        # Fresh provider instance picks up the on-disk session.
        resumed_provider = ClaveMovilAuthProvider(settings)
        browser_session_b = _RecordingBrowserSession(target_path=target_path)

        async def run_resume() -> None:
            session = await resumed_provider.authenticate(browser_session=browser_session_b)
            assert session.identity_nif == "12345678Z"
            # Verify() is called by the resume path; assertion should be valid.
            assert browser_session_b.contexts, "resume must have opened a new context"
            page = browser_session_b.contexts[0].pages[0]
            assert page.gotos == [_aeat_url(_DOMAINS.www6, target_path)]
            await resumed_provider.close()

        asyncio.run(run_resume())
