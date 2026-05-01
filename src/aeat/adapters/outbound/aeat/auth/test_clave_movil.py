"""Protocol-level Cl@ve Movil tests for ``aeat.adapters.outbound.aeat.auth._clave_movil.ClaveMovilAuthProvider``.

These tests use hand-written browser-session stand-ins and do not prove
real AEAT authentication or operator Cl@ve approval.

No mocks, patches, or cassettes are used. The tests drive the provider
against hand-written ``BrowserSessionLike`` stand-ins that record the
navigation + form interactions. The stand-ins honour the same Protocol
the real :class:`aeat.adapters.outbound.aeat.browser.BrowserSession` presents.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import pytest

from .....core.config import Settings
from ._clave_movil import (
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
    _classify_identity,
    _ClaveMovilSidecar,
)
from ._providers import AuthProviderKind, ClaveMovilSessionDetail

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


# ── Browser-session stand-ins ────────────────────────────────────────────────


class _FakePage:
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
        self.gotos: list[str] = []
        self.url: str = ""
        self.closed = False

    async def goto(self, url: str, *, timeout: float | None = None) -> Any:
        del timeout
        self.gotos.append(url)
        # Simulate AEAT's selector dispatch. An authenticated resume
        # navigation to SelectorAccesos.html bounces straight through to
        # the protected target path. Fresh-login navigations land on the
        # selector page itself (then our provider clicks through).
        if self._authenticated and "SelectorAccesos.html" in url:
            self.url = f"https://www6.agenciatributaria.gob.es{self._target_path}"
        else:
            self.url = url

        class _FakeResponse:
            status = 200

        return _FakeResponse()

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)
        # First click advances the selector to the QR page; subsequent clicks
        # are for the non-QR fallback (continue, continuar).
        if selector == 'button[name="autoriza-P"]':
            self.url = "https://www2.agenciatributaria.gob.es/wlpl/MOVI-P24H/ObtenerClaveMovilQR"
        elif selector == 'a[href*="ObtenerClaveMovil?qAA=2"]':
            self.url = "https://www2.agenciatributaria.gob.es/wlpl/BUCV-JDIT/AutenticaDniNieContrasteh"
        elif selector == "#botonContinuar":
            self.url = f"https://www6.agenciatributaria.gob.es{self._target_path}"

    async def fill(self, selector: str, value: str) -> None:
        self.fills.append((selector, value))

    async def wait_for_selector(self, selector: str, *, timeout: float | None = None) -> None:
        del selector, timeout

    async def text_content(self, selector: str) -> str | None:
        if selector == "#spanCodigoVerificacion":
            self.url = f"https://www6.agenciatributaria.gob.es{self._target_path}"
            return self._verification_code
        return None

    async def content(self) -> str:
        return "<html></html>"

    async def wait_for_url(self, matcher: Any, *, timeout: float | None = None) -> None:
        del timeout
        # Simulate a phone approval that auto-redirects to the target.
        self.url = f"https://www6.agenciatributaria.gob.es{self._target_path}"
        if callable(matcher) and not matcher(self.url):
            raise TimeoutError("matcher rejected simulated URL")

    async def close(self) -> None:
        self.closed = True


class _FakeContext:
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
        self.pages: list[_FakePage] = []
        self.closed = False
        self._storage_state: dict[str, object] = {
            "cookies": [{"name": "AEAT_SESSION"}],
            "origins": [],
        }

    async def new_page(self) -> _FakePage:
        page = _FakePage(
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


class _FakeBrowserSession:
    """Stand-in for :class:`aeat.adapters.outbound.aeat.browser.BrowserSession`.

    Only the surface the Cl@ve provider uses —
    ``create_context(...)`` + ``close()`` — is implemented.
    """

    def __init__(self, *, target_path: str, verification_code: str = "YLL") -> None:
        self._target_path = target_path
        self._verification_code = verification_code
        self.contexts: list[_FakeContext] = []
        self.closed = False

    async def create_context(
        self,
        *,
        provisioner: Any | None = None,
        storage_state_path: Path | None = None,
    ) -> _FakeContext:
        del provisioner
        # Resume paths construct contexts with a storage-state path; those
        # get the authenticated simulation. Fresh-login contexts don't.
        authenticated = storage_state_path is not None
        context = _FakeContext(
            target_path=self._target_path,
            verification_code=self._verification_code,
            authenticated=authenticated,
        )
        self.contexts.append(context)
        return context

    async def close(self) -> None:
        self.closed = True


def _settings_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    from pydantic_settings import SettingsConfigDict

    for name in Settings.env_var_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # Pydantic-settings reads env/.env by default; a developer who ran
    # `aeat auth configure` would then leak their real DNI/NIE into
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
        with pytest.raises(ClaveMovilConfigurationError):
            _classify_identity("B12345674")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ClaveMovilConfigurationError):
            _classify_identity("")


# ── describe() ──────────────────────────────────────────────────────────────


class TestDescribe:
    def test_describe_unconfigured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _settings_for(tmp_path, monkeypatch)
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False
        assert "AEAT_CLAVE_MOVIL_DNI_NIE" in (description.health_summary or "")

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
    def test_qr_flow_writes_sidecar_and_storage_state(
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
        fake_session = _FakeBrowserSession(target_path=target_path, verification_code="YLL")

        async def run() -> None:
            session = await provider.authenticate(browser_session=fake_session)
            assert session.provider_kind == AuthProviderKind.CLAVE_MOVIL
            assert session.identity_nif == "12345678Z"
            assert session.storage_state_path is not None
            assert session.storage_state_path.exists()
            sidecar_path = session.storage_state_path.with_suffix(".meta.json")
            assert sidecar_path.exists()
            sidecar = _ClaveMovilSidecar.model_validate_json(sidecar_path.read_text(encoding="utf-8"))
            assert sidecar.identity_nif == "12345678Z"
            assert sidecar.used_non_qr_fallback is False
            assert sidecar.verification_code == "YLL"
            # Storage-state sha256 agrees with the actual bytes on disk.
            digest = hashlib.sha256(session.storage_state_path.read_bytes()).hexdigest()
            assert sidecar.storage_state_sha256 == digest
            # Page observed the expected click sequence.
            assert fake_session.contexts, "a context must have been created"
            page = fake_session.contexts[0].pages[0]
            assert page.gotos[0].startswith(
                "https://sede.agenciatributaria.gob.es/static_files/common/html/selector_acceso/"
            )
            assert 'button[name="autoriza-P"]' in page.clicks
            # No form fill (QR flow skips the non-QR form entirely)
            assert page.fills == []
            # provider_detail is Cl@ve-shaped
            assert isinstance(session.provider_detail, ClaveMovilSessionDetail)
            assert session.provider_detail.dni_nie == "12345678Z"

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
        fake_session = _FakeBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            session = await provider.authenticate(browser_session=fake_session)
            detail = session.provider_detail
            assert isinstance(detail, ClaveMovilSessionDetail)
            assert detail.used_non_qr_fallback is True
            page = fake_session.contexts[0].pages[0]
            assert ("#NIF", "12345678Z") in page.fills
            assert ("#FECHA", "2030-01-01") in page.fills
            assert page.clicks.count('button[name="autoriza-P"]') == 1
            assert "#botonContinuar" in page.clicks

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
        fake_session = _FakeBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError):
                await provider.authenticate(browser_session=fake_session)

        asyncio.run(run())

    def test_missing_identity_raises_configuration_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch)
        provider = ClaveMovilAuthProvider(settings)
        fake_session = _FakeBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError):
                await provider.authenticate(browser_session=fake_session)

        asyncio.run(run())


class TestPostAuthLanding:
    def test_representation_dispatcher_is_not_auto_submitted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from ._authenticator import AeatLoginAssertionError

        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _FakePage(target_path=settings.aeat_sede_expedientes_path)
        page.url = "https://www6.agenciatributaria.gob.es/wlpl/OVCT-CXEW/DialogoRepresentacion"

        async def run() -> None:
            with pytest.raises(AeatLoginAssertionError, match="will not submit representation forms"):
                await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=100)

        asyncio.run(run())
        assert page.clicks == []


# ── authenticate() — resume path ─────────────────────────────────────────────


class TestProbePersistedSession:
    """`probe_persisted_session` never touches the fresh-login path."""

    def test_probe_without_sidecar_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        fake_session = _FakeBrowserSession(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            from ._authenticator import AeatLoginAssertionError

            with pytest.raises(AeatLoginAssertionError, match="no persisted"):
                await provider.probe_persisted_session(browser_session=fake_session)

        asyncio.run(run())

    def test_probe_uses_existing_sidecar_without_invalidating_on_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings = _settings_for(tmp_path, monkeypatch, AEAT_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        target_path = settings.aeat_sede_expedientes_path
        # Seed a session via a fresh login.
        fake_session_login = _FakeBrowserSession(target_path=target_path)

        async def seed() -> None:
            await provider.authenticate(browser_session=fake_session_login)
            await provider.close()

        asyncio.run(seed())

        storage_path = settings.aeat_token_dir / f"{settings.aeat_default_profile_name}-clave-movil-storage.json"
        sidecar_path = storage_path.with_suffix(".meta.json")
        assert storage_path.exists() and sidecar_path.exists()

        # Probe against a fresh provider instance; session files must survive.
        probe_provider = ClaveMovilAuthProvider(settings)
        fake_session_probe = _FakeBrowserSession(target_path=target_path)

        async def probe() -> None:
            session, assertion = await probe_provider.probe_persisted_session(browser_session=fake_session_probe)
            assert session.identity_nif == "12345678Z"
            assert assertion.target_url
            await probe_provider.close()

        asyncio.run(probe())
        # Files must still exist after a successful probe.
        assert storage_path.exists()
        assert sidecar_path.exists()


class TestResume:
    def test_resume_from_fresh_sidecar(
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
        fake_session_a = _FakeBrowserSession(target_path=target_path)

        async def run_first() -> None:
            await provider.authenticate(browser_session=fake_session_a)
            await provider.close()

        asyncio.run(run_first())

        # Fresh provider instance picks up the on-disk session.
        resumed_provider = ClaveMovilAuthProvider(settings)
        fake_session_b = _FakeBrowserSession(target_path=target_path)

        async def run_resume() -> None:
            session = await resumed_provider.authenticate(browser_session=fake_session_b)
            assert session.identity_nif == "12345678Z"
            # Verify() is called by the resume path; assertion should be valid.
            assert fake_session_b.contexts, "resume must have opened a new context"
            await resumed_provider.close()

        asyncio.run(run_resume())
