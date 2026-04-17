"""Unit tests for BrowserSession factory."""

from pathlib import Path

import pytest
from playwright.async_api import BrowserContext

from ..config import PROJECT_ROOT, Settings
from ..errors import SiteHealthError
from ..status import SiteHealthState
from ._site_health_probe import probe_response
from .evasion import EvasionStrategy
from .profile import Profile
from .session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]

_FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "site_health"
_PROBE_URL = "https://sede.agenciatributaria.gob.es/"


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


@pytest.mark.asyncio
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
    assert "storage_state" not in context.kwargs  # type: ignore
    # No cert supplied → marker must NOT be stamped on the context.
    assert not hasattr(context, "_aeat_certificate_thumbprint")


@pytest.mark.asyncio
async def test_browser_session_uses_existing_storage_state_file(tmp_path: Path) -> None:
    """Existing storage-state JSON is passed through to new_context."""
    settings = Settings()
    storage_state_path = tmp_path / "state.json"
    storage_state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    profile = Profile(name="test", storage_state_path=storage_state_path)
    session = BrowserSession(
        playwright=StubPlaywright(),  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    context = await session.create_context()
    assert context.kwargs["storage_state"] == str(storage_state_path)  # type: ignore


@pytest.mark.asyncio
async def test_browser_session_prefers_explicit_storage_state_path(tmp_path: Path) -> None:
    """Explicit resume paths override the profile default when provided."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "profile.json")
    override_path = tmp_path / "resume.json"
    override_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    session = BrowserSession(
        playwright=StubPlaywright(),  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    context = await session.create_context(storage_state_path=override_path)
    assert context.kwargs["storage_state"] == str(override_path)  # type: ignore


@pytest.mark.asyncio
@pytest.mark.unit
async def test_browser_session_wires_certificate(tmp_path: Path) -> None:
    """Certificate propagates into new_context kwargs and thumbprint marker."""
    import os
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    from ..auth import CertificateBackend, CertificateBundle, load_certificate
    from .session import CERTIFICATE_THUMBPRINT_MARKER

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test - 12345678Z"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678Z"),
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
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"pw"),
    )
    bundle_path = tmp_path / "bundle.p12"
    bundle_path.write_bytes(pfx_bytes)
    os.environ["AEAT_BROWSER_TEST_PW"] = "pw"
    loaded = load_certificate(
        CertificateBundle(
            path=bundle_path,
            password_env_var="AEAT_BROWSER_TEST_PW",  # noqa: S106 — env var NAME
            friendly_name=None,
            backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        )
    )

    settings = Settings()
    profile = Profile(name="cert-test", storage_state_path=tmp_path / "state.json")
    session = BrowserSession(
        playwright=StubPlaywright(),  # type: ignore
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )
    context = await session.create_context(cert=loaded)

    # StubContext (returned by our fake chromium) exposes .kwargs for
    # assertions; Playwright's real BrowserContext does not.
    from typing import cast

    kwargs: dict[str, object] = cast("StubContext", context).kwargs
    assert "client_certificates" in kwargs
    cc = kwargs["client_certificates"]
    assert isinstance(cc, list) and len(cc) == 1
    assert cc[0]["pfxPath"] == str(bundle_path)
    # passphrase is materialised here only; confirm it is present so
    # Playwright can consume it, then the caller hands the list
    # straight to new_context and does not persist the dict.
    assert cc[0]["passphrase"] == "pw"  # noqa: S105 — test fixture
    marker = getattr(context, CERTIFICATE_THUMBPRINT_MARKER, None)
    assert marker == loaded.sha256_thumbprint


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


def test_navigate_probe_raises_on_mantenimiento_fixture() -> None:
    body = (_FIXTURES_ROOT / "mantenimiento" / "interstitial.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.MANTENIMIENTO


def test_navigate_probe_raises_on_waf_fixture() -> None:
    body = (_FIXTURES_ROOT / "waf_challenge" / "request_blocked.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError) as excinfo:
        _probe_or_raise(_PROBE_URL, 403, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.WAF_CHALLENGE


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


def test_navigate_probe_passes_on_ok_fixture() -> None:
    body = (_FIXTURES_ROOT / "ok" / "sede_landing.html").read_text(encoding="utf-8")
    # Must not raise.
    _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
