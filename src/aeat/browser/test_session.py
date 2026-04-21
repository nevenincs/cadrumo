"""Unit tests for BrowserSession factory."""

from pathlib import Path
from typing import cast

import pytest
from playwright.async_api import BrowserContext, Playwright

from ..config import PROJECT_ROOT, Settings
from ..errors import SiteHealthError
from ..status import SiteHealthState
from ._site_health_probe import probe_response
from .evasion import EvasionStrategy
from .profile import Profile
from .session import BrowserError, BrowserSession

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
        self.close_calls = 0

    async def close(self) -> None:
        """Record context close calls without touching browser ownership."""
        self.close_calls += 1


class StubBrowser:
    """Stub browser that yields a StubContext."""

    def __init__(self, chromium: "StubChromium") -> None:
        self._chromium = chromium
        self.close_calls = 0
        self.close_failures_remaining = 0
        self._counted_closed = False

    async def new_context(self, **kwargs) -> StubContext:
        """Return a stub context."""
        return StubContext(kwargs)

    async def close(self) -> None:
        """Close the stub browser and decrement the live-process count."""
        if self.close_failures_remaining > 0:
            self.close_failures_remaining -= 1
            self.close_calls += 1
            raise RuntimeError("boom from close")
        if not self._counted_closed:
            self._chromium.live_browser_count -= 1
            self._chromium.closed_browser_count += 1
            self._counted_closed = True
        self.close_calls += 1


class StubChromium:
    """Stub chromium that yields a StubBrowser."""

    def __init__(self) -> None:
        self.live_browser_count = 0
        self.launch_calls = 0
        self.closed_browser_count = 0
        self.launched_browsers: list[StubBrowser] = []
        self.next_close_failures = 0

    async def launch(self, **kwargs) -> StubBrowser:
        """Return a stub browser."""
        del kwargs
        self.launch_calls += 1
        self.live_browser_count += 1
        browser = StubBrowser(self)
        browser.close_failures_remaining = self.next_close_failures
        self.next_close_failures = 0
        self.launched_browsers.append(browser)
        return browser


class StubPlaywright:
    """Stub playwright instance for unit testing."""

    def __init__(self) -> None:
        self.chromium = StubChromium()


class FailingNewContextBrowser(StubBrowser):
    """Stub browser whose ``new_context`` path fails after launch."""

    async def new_context(self, **kwargs) -> StubContext:
        del kwargs
        raise RuntimeError("boom from new_context")


class FailingNewContextChromium(StubChromium):
    """Chromium double that returns a failing browser."""

    async def launch(self, **kwargs) -> StubBrowser:
        del kwargs
        self.launch_calls += 1
        self.live_browser_count += 1
        browser = FailingNewContextBrowser(self)
        self.launched_browsers.append(browser)
        return browser


class FailingNewContextPlaywright(StubPlaywright):
    """Playwright double whose browser fails during context creation."""

    def __init__(self) -> None:
        self.chromium = FailingNewContextChromium()


class FailingClosePlaywright(StubPlaywright):
    """Playwright double whose first browser close attempt fails."""

    def __init__(self) -> None:
        super().__init__()
        self.chromium.next_close_failures = 1


@pytest.mark.asyncio
async def test_browser_session_creation(tmp_path: Path) -> None:
    """Test creating a browser context with a stub Playwright instance."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    evasion = DummyEvasion()
    pw_stub = StubPlaywright()

    session = BrowserSession(
        playwright=cast(Playwright, pw_stub),
        settings=settings,
        profile=profile,
        evasion_strategy=evasion,
    )

    context = await session.create_context()
    assert evasion.called
    assert context.kwargs["locale"] == "es-ES"  # type: ignore
    assert context.kwargs["timezone_id"] == "Europe/Madrid"  # type: ignore
    assert "storage_state" not in context.kwargs  # type: ignore
    assert not hasattr(context, "_aeat_certificate_thumbprint")


@pytest.mark.asyncio
async def test_browser_session_uses_existing_storage_state_file(tmp_path: Path) -> None:
    """Existing storage-state JSON is passed through to new_context."""
    settings = Settings()
    storage_state_path = tmp_path / "state.json"
    storage_state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    profile = Profile(name="test", storage_state_path=storage_state_path)
    session = BrowserSession(
        playwright=cast(Playwright, StubPlaywright()),
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
        playwright=cast(Playwright, StubPlaywright()),
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

    from ..auth import (
        CertificateBackend,
        CertificateBundle,
        CertificateContextProvisioner,
        load_certificate,
    )
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
        playwright=cast(Playwright, StubPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )
    context = await session.create_context(
        provisioner=CertificateContextProvisioner(
            loaded,
            origin=settings.aeat_certificate_verify_url,
        )
    )

    kwargs: dict[str, object] = cast(StubContext, context).kwargs
    assert "client_certificates" in kwargs
    cc = kwargs["client_certificates"]
    assert isinstance(cc, list) and len(cc) == 1
    assert cc[0]["pfxPath"] == str(bundle_path)
    assert cc[0]["passphrase"] == "pw"  # noqa: S105 — test fixture
    marker = getattr(context, CERTIFICATE_THUMBPRINT_MARKER, None)
    assert marker == loaded.sha256_thumbprint


@pytest.mark.asyncio
async def test_browser_session_close_is_idempotent(tmp_path: Path) -> None:
    """Closing a session repeatedly must not resurrect browser processes."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    pw_stub = StubPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, pw_stub),
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    context = await session.create_context()
    await context.close()
    await session.close()
    await session.close()

    assert pw_stub.chromium.launch_calls == 1
    assert pw_stub.chromium.live_browser_count == 0
    assert pw_stub.chromium.launched_browsers[0].close_calls == 1


@pytest.mark.asyncio
async def test_browser_session_rejects_second_live_context_until_close(tmp_path: Path) -> None:
    """A session owns one live browser at a time until ``close()`` runs."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    pw_stub = StubPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, pw_stub),
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    context = await session.create_context()
    await context.close()
    with pytest.raises(BrowserError, match="call close\\(\\) before create_context\\(\\) again"):
        await session.create_context()

    await session.close()
    context2 = await session.create_context()
    await context2.close()
    await session.close()

    assert pw_stub.chromium.launch_calls == 2
    assert pw_stub.chromium.live_browser_count == 0


@pytest.mark.asyncio
async def test_browser_session_closes_browser_when_new_context_fails(tmp_path: Path) -> None:
    """Partial launch failures must not leak a retained browser."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    pw_stub = FailingNewContextPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, pw_stub),
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    with pytest.raises(BrowserError, match="boom from new_context"):
        await session.create_context()

    assert pw_stub.chromium.launch_calls == 1
    assert pw_stub.chromium.live_browser_count == 0
    assert pw_stub.chromium.launched_browsers[0].close_calls == 1


@pytest.mark.asyncio
async def test_browser_session_close_failure_surfaces_and_allows_retry(tmp_path: Path) -> None:
    """Close failures must be explicit and leave cleanup retryable."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    pw_stub = FailingClosePlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, pw_stub),
        settings=settings,
        profile=profile,
        evasion_strategy=DummyEvasion(),
    )

    context = await session.create_context()
    await context.close()
    with pytest.raises(BrowserError, match="Failed to close retained browser"):
        await session.close()

    assert pw_stub.chromium.live_browser_count == 1
    assert pw_stub.chromium.launched_browsers[0].close_calls == 1

    await session.close()
    context2 = await session.create_context()
    await context2.close()
    await session.close()

    assert pw_stub.chromium.live_browser_count == 0
    assert pw_stub.chromium.closed_browser_count == 2


@pytest.mark.asyncio
async def test_browser_session_process_count_stays_flat_across_repeated_cycles(tmp_path: Path) -> None:
    """Repeated construct/create/close cycles must not accumulate browsers."""
    settings = Settings()
    pw_stub = StubPlaywright()
    live_counts: list[int] = []

    for idx in range(5):
        profile = Profile(name=f"test-{idx}", storage_state_path=tmp_path / f"state-{idx}.json")
        session = BrowserSession(
            playwright=cast(Playwright, pw_stub),
            settings=settings,
            profile=profile,
            evasion_strategy=DummyEvasion(),
        )
        context = await session.create_context()
        await context.close()
        await session.close()
        live_counts.append(pw_stub.chromium.live_browser_count)

    assert live_counts == [0, 0, 0, 0, 0]
    assert pw_stub.chromium.launch_calls == 5


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
    _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
