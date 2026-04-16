"""Unit tests for BrowserSession factory."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from playwright.async_api import BrowserContext

from aeat.auth import (
    CertificateBackend,
    CertificateBundle,
    LoadedCertificate,
    load_certificate,
    preload_into_browser_context,
)
from aeat.browser._site_health_probe import probe_response
from aeat.browser.evasion import EvasionStrategy
from aeat.browser.profile import Profile
from aeat.browser.session import BrowserSession
from aeat.config import PROJECT_ROOT, Settings
from aeat.errors import SiteHealthError
from aeat.status import SiteHealthState

_FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "site_health"
_PROBE_URL = "https://sede.agenciatributaria.gob.es/"
_TEST_CERT_PASSWORD = "browser-session-test-password"  # noqa: S105 - synthetic test passphrase


class DummyEvasion(EvasionStrategy):
    """A dummy evasion strategy that records when it was called."""

    def __init__(self) -> None:
        self.called = False

    async def apply(self, context: BrowserContext) -> None:
        """Record the call."""
        self.called = True


class StubContext:
    """Stub context capturing the kwargs it was created with."""

    def __init__(self, kwargs: dict) -> None:
        self.kwargs = kwargs


class StubBrowser:
    """Stub browser that yields a StubContext."""

    async def new_context(self, **kwargs) -> StubContext:
        """Return a stub context."""
        return StubContext(kwargs)


class StubChromium:
    """Stub chromium that yields a StubBrowser."""

    async def launch(self, **kwargs) -> StubBrowser:
        """Return a stub browser."""
        return StubBrowser()


class StubPlaywright:
    """Stub playwright instance for unit testing."""

    def __init__(self) -> None:
        self.chromium = StubChromium()


def _build_pkcs12_bundle(tmp_path: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "browser-test-subject"),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"browser-test-cert",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(_TEST_CERT_PASSWORD.encode("utf-8")),
    )
    bundle_path = tmp_path / "browser-test.p12"
    bundle_path.write_bytes(pfx_bytes)
    return bundle_path


def _load_test_certificate(tmp_path: Path) -> LoadedCertificate:
    bundle_path = _build_pkcs12_bundle(tmp_path)
    original = os.environ.get("AEAT_BROWSER_TEST_CERT_PASSWORD")
    os.environ["AEAT_BROWSER_TEST_CERT_PASSWORD"] = _TEST_CERT_PASSWORD
    try:
        bundle = CertificateBundle(
            path=bundle_path,
            password_env_var="AEAT_BROWSER_TEST_CERT_PASSWORD",  # noqa: S106 - env var name, not a secret
            backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        )
        return load_certificate(bundle)
    finally:
        if original is None:
            os.environ.pop("AEAT_BROWSER_TEST_CERT_PASSWORD", None)
        else:
            os.environ["AEAT_BROWSER_TEST_CERT_PASSWORD"] = original


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_session_creation(tmp_path: Path) -> None:
    """Test creating a browser context with a stub Playwright instance."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    evasion = DummyEvasion()
    pw_stub = StubPlaywright()

    session = BrowserSession(
        playwright=pw_stub,  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=evasion,
    )

    context = await session.create_context()
    assert evasion.called
    assert context.kwargs["locale"] == "es-ES"  # type: ignore
    assert context.kwargs["timezone_id"] == "Europe/Madrid"  # type: ignore
    assert str(tmp_path / "state.json") in context.kwargs["storage_state"]  # type: ignore


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_session_adds_client_certificates(tmp_path: Path) -> None:
    settings = Settings()
    profile = Profile(name="cert", storage_state_path=tmp_path / "cert-state.json")
    evasion = DummyEvasion()
    pw_stub = cast(Any, StubPlaywright())
    loaded = _load_test_certificate(tmp_path)

    session = BrowserSession(
        playwright=pw_stub,
        settings=settings,
        profile=profile,
        auth_backend=loaded,
        evasion_strategy=evasion,
    )

    context = cast(StubContext, await session.create_context())
    assert evasion.called
    assert context.kwargs["client_certificates"] == [
        {
            "origin": "https://sede.agenciatributaria.gob.es",
            "pfxPath": str(loaded.source_path),
            "passphrase": _TEST_CERT_PASSWORD,
        }
    ]
    preload_into_browser_context(loaded, context)


def _probe_or_raise(
    url: str,
    http_status: int,
    headers: dict[str, str],
    body: str,
    *,
    rate_limit_retry_after_default: int,
) -> None:
    """Thin test harness: call the helper and surface a ``SiteHealthError``.

    Mirrors the shape of ``BrowserSession.navigate`` without the
    Playwright dependency so the classification branch can be
    exercised via the real parser suite driven from on-disk HTML.
    """
    result = probe_response(
        url,
        http_status,
        headers,
        body,
        rate_limit_retry_after_default=rate_limit_retry_after_default,
    )
    if result is not None:
        raise SiteHealthError(status=result)


@pytest.mark.unit
def test_navigate_probe_raises_on_mantenimiento_fixture() -> None:
    body = (_FIXTURES_ROOT / "mantenimiento" / "interstitial.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.MANTENIMIENTO


@pytest.mark.unit
def test_navigate_probe_raises_on_waf_fixture() -> None:
    body = (_FIXTURES_ROOT / "waf_challenge" / "request_blocked.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 403, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.WAF_CHALLENGE


@pytest.mark.unit
def test_navigate_probe_raises_on_rate_limit_fixture() -> None:
    body = (_FIXTURES_ROOT / "rate_limited" / "429_retry_after.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(
            _PROBE_URL,
            429,
            {"Retry-After": "120"},
            body,
            rate_limit_retry_after_default=300,
        )
    assert excinfo.value.status.state is SiteHealthState.RATE_LIMITED
    assert excinfo.value.status.retry_after_seconds == 120


@pytest.mark.unit
def test_navigate_probe_passes_on_ok_fixture() -> None:
    body = (_FIXTURES_ROOT / "ok" / "sede_landing.html").read_text(encoding="utf-8")
    # Must not raise.
    _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
