"""Unit tests for BrowserSession factory."""

from pathlib import Path
from typing import ClassVar, cast, override

import pytest
from playwright.async_api import BrowserContext, Page, Playwright

from ......core.config import Settings
from ......core.errors import SiteHealthError
from ......tests import FIXTURES_DIR
from .._site_health import SiteHealthState
from .._site_health_probe import probe_response
from ..evasion import EvasionStrategy
from ..profile import Profile
from ..session import BrowserError, BrowserFailureMode, BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FIXTURES_ROOT = FIXTURES_DIR / "site_health"
_PROBE_URL = f"{Settings.external_constants().aeat.domains.sede}/"


class _RecordingEvasion(EvasionStrategy):
    """A recording evasion strategy used to assert invocation."""

    def __init__(self) -> None:
        self.called = False

    @override
    async def apply(self, context: BrowserContext) -> None:
        """Record the call."""
        self.called = True


class RecordingContext:
    """Concrete context capturing the kwargs it was created with."""

    def __init__(self, kwargs: dict[str, object]) -> None:
        self.kwargs = kwargs
        self.close_calls = 0

    async def close(self) -> None:
        """Record context close calls without touching browser ownership."""
        self.close_calls += 1


class RecordingBrowser:
    """Concrete browser that yields a :class:`RecordingContext`."""

    def __init__(self, chromium: "RecordingChromium") -> None:
        self._chromium = chromium
        self.close_calls = 0
        self.close_failures_remaining = 0
        self._counted_closed = False

    async def new_context(self, **kwargs) -> RecordingContext:
        """Return a recording context."""
        return RecordingContext(kwargs)

    async def close(self) -> None:
        """Close the browser and decrement the live-process count."""
        if self.close_failures_remaining > 0:
            self.close_failures_remaining -= 1
            self.close_calls += 1
            raise RuntimeError("boom from close")
        if not self._counted_closed:
            self._chromium.live_browser_count -= 1
            self._chromium.closed_browser_count += 1
            self._counted_closed = True
        self.close_calls += 1


class RecordingChromium:
    """Concrete chromium adapter that yields a :class:`RecordingBrowser`."""

    def __init__(self) -> None:
        self.live_browser_count = 0
        self.launch_calls = 0
        self.closed_browser_count = 0
        self.launched_browsers: list[RecordingBrowser] = []
        self.next_close_failures = 0

    async def launch(self, **kwargs) -> RecordingBrowser:
        """Return a recording browser."""
        del kwargs
        self.launch_calls += 1
        self.live_browser_count += 1
        browser = RecordingBrowser(self)
        browser.close_failures_remaining = self.next_close_failures
        self.next_close_failures = 0
        self.launched_browsers.append(browser)
        return browser


class RecordingPlaywright:
    """Concrete Playwright adapter for unit testing."""

    def __init__(self) -> None:
        self.chromium = RecordingChromium()


class FailingLaunchChromium(RecordingChromium):
    """Chromium adapter that fails before a browser exists."""

    @override
    async def launch(self, **kwargs) -> RecordingBrowser:
        """Raise from the launch boundary."""
        del kwargs
        self.launch_calls += 1
        raise RuntimeError("boom from launch")


class FailingLaunchPlaywright(RecordingPlaywright):
    """Playwright adapter whose launch path fails."""

    def __init__(self) -> None:
        self.chromium = FailingLaunchChromium()


class FailingNewContextBrowser(RecordingBrowser):
    """Browser whose ``new_context`` path fails after launch."""

    @override
    async def new_context(self, **kwargs) -> RecordingContext:
        del kwargs
        raise RuntimeError("boom from new_context")


class FailingNewContextChromium(RecordingChromium):
    """Chromium double that returns a failing browser."""

    @override
    async def launch(self, **kwargs) -> RecordingBrowser:
        del kwargs
        self.launch_calls += 1
        self.live_browser_count += 1
        browser = FailingNewContextBrowser(self)
        self.launched_browsers.append(browser)
        return browser


class FailingNewContextPlaywright(RecordingPlaywright):
    """Playwright double whose browser fails during context creation."""

    def __init__(self) -> None:
        self.chromium = FailingNewContextChromium()


class FailingClosePlaywright(RecordingPlaywright):
    """Playwright double whose first browser close attempt fails."""

    def __init__(self) -> None:
        super().__init__()
        self.chromium.next_close_failures = 1


class FailingEvasion(EvasionStrategy):
    """Evasion strategy that fails after context creation."""

    @override
    async def apply(self, context: BrowserContext) -> None:
        """Raise from the evasion boundary."""
        del context
        raise RuntimeError("boom from evasion")


class ContentFailingResponse:
    """Concrete response shape needed by BrowserSession.navigate."""

    status = 200
    headers: ClassVar[dict[str, str]] = {}


class ContentFailingPage:
    """Concrete page adapter whose content read fails after navigation."""

    async def goto(self, url: str) -> ContentFailingResponse:
        """Return a response so the content-read stage is reached."""
        del url
        return ContentFailingResponse()

    async def content(self) -> str:
        """Raise from the page content boundary."""
        raise RuntimeError("boom from content")


@pytest.mark.asyncio
async def test_browser_session_creation(tmp_path: Path) -> None:
    """Test creating a browser context with a concrete Playwright adapter."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    evasion = _RecordingEvasion()
    playwright_adapter = RecordingPlaywright()

    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=evasion,
    )

    context = cast(RecordingContext, await session.create_context())
    assert evasion.called
    assert context.kwargs["locale"] == "es-ES"
    assert context.kwargs["timezone_id"] == "Europe/Madrid"
    assert "storage_state" not in context.kwargs
    assert not hasattr(context, "_aeat_certificate_thumbprint")


@pytest.mark.asyncio
async def test_browser_session_launch_failure_reports_failure_mode(tmp_path: Path) -> None:
    """Launch failures should carry the central failure-mode context."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = FailingLaunchPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    with pytest.raises(BrowserError, match="boom from launch") as excinfo:
        await session.create_context()

    assert excinfo.value.failure_mode == BrowserFailureMode.BROWSER_LAUNCH_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.BROWSER_LAUNCH_FAILED
    assert excinfo.value.context["profile"] == "test"
    assert playwright_adapter.chromium.launch_calls == 1
    assert playwright_adapter.chromium.live_browser_count == 0


@pytest.mark.asyncio
async def test_browser_session_uses_existing_storage_state_file(tmp_path: Path) -> None:
    """Existing storage-state JSON is passed through to new_context."""
    settings = Settings()
    storage_state_path = tmp_path / "state.json"
    storage_state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    profile = Profile(name="test", storage_state_path=storage_state_path)
    session = BrowserSession(
        playwright=cast(Playwright, RecordingPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    context = cast(RecordingContext, await session.create_context())
    assert context.kwargs["storage_state"] == str(storage_state_path)


@pytest.mark.asyncio
async def test_browser_session_prefers_explicit_storage_state_path(tmp_path: Path) -> None:
    """Explicit resume paths override the profile default when provided."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "profile.json")
    override_path = tmp_path / "resume.json"
    override_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    session = BrowserSession(
        playwright=cast(Playwright, RecordingPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    context = cast(RecordingContext, await session.create_context(storage_state_path=override_path))
    assert context.kwargs["storage_state"] == str(override_path)


@pytest.mark.asyncio
async def test_browser_session_wires_certificate(tmp_path: Path) -> None:
    """Certificate propagates into new_context kwargs and thumbprint marker."""
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID
    from pydantic import SecretStr

    from ......core.config import CertificateBackend
    from ...auth import (
        CERTIFICATE_CONTEXT_MARKER,
        CertificateBundle,
        CertificateContextProvisioner,
        load_certificate,
    )

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test - 12345678Z"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678Z"),
        ],
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
    secret = SecretStr("pw")
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(secret.get_secret_value().encode("utf-8")),
    )
    bundle_path = tmp_path / "bundle.p12"
    bundle_path.write_bytes(pfx_bytes)

    loaded = load_certificate(
        CertificateBundle(
            path=bundle_path,
            password=secret,
            friendly_name=None,
            backend=CertificateBackend.PLAYWRIGHT_CONTEXT,
        ),
    )

    settings = Settings()
    profile = Profile(name="cert-test", storage_state_path=tmp_path / "state.json")
    session = BrowserSession(
        playwright=cast(Playwright, RecordingPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )
    context = await session.create_context(
        provisioner=CertificateContextProvisioner(
            loaded,
            origin=settings.aeat_certificate_verify_url,
        ),
    )

    kwargs: dict[str, object] = cast(RecordingContext, context).kwargs
    assert "client_certificates" in kwargs
    cc = kwargs["client_certificates"]
    assert isinstance(cc, list) and len(cc) == 1
    client_certificates = cast(list[dict[str, str]], cc)
    assert client_certificates[0]["pfxPath"] == str(bundle_path)
    assert client_certificates[0]["passphrase"] == secret.get_secret_value()
    marker = getattr(context, CERTIFICATE_CONTEXT_MARKER, None)
    assert marker == loaded.sha256_thumbprint


@pytest.mark.asyncio
async def test_browser_session_close_is_idempotent(tmp_path: Path) -> None:
    """Closing a session repeatedly must not resurrect browser processes."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = RecordingPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    context = await session.create_context()
    await context.close()
    await session.close()
    await session.close()

    assert playwright_adapter.chromium.launch_calls == 1
    assert playwright_adapter.chromium.live_browser_count == 0
    assert playwright_adapter.chromium.launched_browsers[0].close_calls == 1


@pytest.mark.asyncio
async def test_browser_session_rejects_second_live_context_until_close(tmp_path: Path) -> None:
    """A session owns one live browser at a time until ``close()`` runs."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = RecordingPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    context = await session.create_context()
    await context.close()
    with pytest.raises(BrowserError, match="call close\\(\\) before create_context\\(\\) again") as excinfo:
        await session.create_context()

    assert excinfo.value.failure_mode == BrowserFailureMode.SESSION_BUSY
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.SESSION_BUSY

    await session.close()
    context2 = await session.create_context()
    await context2.close()
    await session.close()

    assert playwright_adapter.chromium.launch_calls == 2
    assert playwright_adapter.chromium.live_browser_count == 0


@pytest.mark.asyncio
async def test_browser_session_closes_browser_when_new_context_fails(tmp_path: Path) -> None:
    """Partial launch failures must not leak a retained browser."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = FailingNewContextPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    with pytest.raises(BrowserError, match="boom from new_context") as excinfo:
        await session.create_context()

    assert excinfo.value.failure_mode == BrowserFailureMode.CONTEXT_CREATE_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.CONTEXT_CREATE_FAILED
    assert playwright_adapter.chromium.launch_calls == 1
    assert playwright_adapter.chromium.live_browser_count == 0
    assert playwright_adapter.chromium.launched_browsers[0].close_calls == 1


@pytest.mark.asyncio
async def test_browser_session_closes_browser_when_evasion_fails(tmp_path: Path) -> None:
    """Evasion failures should be explicit and should not leak a browser."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = RecordingPlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=FailingEvasion(),
    )

    with pytest.raises(BrowserError, match="boom from evasion") as excinfo:
        await session.create_context()

    assert excinfo.value.failure_mode == BrowserFailureMode.EVASION_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.EVASION_FAILED
    assert playwright_adapter.chromium.live_browser_count == 0
    assert playwright_adapter.chromium.launched_browsers[0].close_calls == 1


@pytest.mark.asyncio
async def test_browser_session_close_failure_surfaces_and_allows_retry(tmp_path: Path) -> None:
    """Close failures must be explicit and leave cleanup retryable."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    playwright_adapter = FailingClosePlaywright()
    session = BrowserSession(
        playwright=cast(Playwright, playwright_adapter),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    context = await session.create_context()
    await context.close()
    with pytest.raises(BrowserError, match="Failed to close retained browser") as excinfo:
        await session.close()

    assert excinfo.value.failure_mode == BrowserFailureMode.BROWSER_CLOSE_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.BROWSER_CLOSE_FAILED
    assert playwright_adapter.chromium.live_browser_count == 1
    assert playwright_adapter.chromium.launched_browsers[0].close_calls == 1

    await session.close()
    context2 = await session.create_context()
    await context2.close()
    await session.close()

    assert playwright_adapter.chromium.live_browser_count == 0
    assert playwright_adapter.chromium.closed_browser_count == 2


@pytest.mark.asyncio
async def test_browser_session_process_count_stays_flat_across_repeated_cycles(tmp_path: Path) -> None:
    """Repeated construct/create/close cycles must not accumulate browsers."""
    settings = Settings()
    playwright_adapter = RecordingPlaywright()
    live_counts: list[int] = []

    for idx in range(5):
        profile = Profile(name=f"test-{idx}", storage_state_path=tmp_path / f"state-{idx}.json")
        session = BrowserSession(
            playwright=cast(Playwright, playwright_adapter),
            settings=settings,
            profile=profile,
            evasion_strategy=_RecordingEvasion(),
        )
        context = await session.create_context()
        await context.close()
        await session.close()
        live_counts.append(playwright_adapter.chromium.live_browser_count)

    assert live_counts == [0, 0, 0, 0, 0]
    assert playwright_adapter.chromium.launch_calls == 5


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
    with pytest.raises(SiteHealthError, match=r"(?i)mantenimiento") as excinfo:
        _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.MANTENIMIENTO
    assert excinfo.value.context is not None
    assert excinfo.value.context["url"] == _PROBE_URL
    assert excinfo.value.context["http_status"] == 200
    assert "detected_markers" in excinfo.value.context


@pytest.mark.asyncio
async def test_browser_session_navigate_content_failure_reports_failure_mode(tmp_path: Path) -> None:
    """Content-read failures after navigation should not collapse into a generic exception."""
    settings = Settings()
    profile = Profile(name="test", storage_state_path=tmp_path / "state.json")
    session = BrowserSession(
        playwright=cast(Playwright, RecordingPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )

    with pytest.raises(BrowserError, match="boom from content") as excinfo:
        await session.navigate(cast(Page, ContentFailingPage()), _PROBE_URL)

    assert excinfo.value.failure_mode == BrowserFailureMode.PAGE_CONTENT_FAILED
    assert excinfo.value.context is not None
    assert excinfo.value.context["failure_mode"] == BrowserFailureMode.PAGE_CONTENT_FAILED
    assert excinfo.value.context["http_status"] == 200


def test_navigate_probe_raises_on_waf_fixture() -> None:
    body = (_FIXTURES_ROOT / "waf_challenge" / "request_blocked.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError, match=r"(?i)waf[ _]?challenge") as excinfo:
        _probe_or_raise(_PROBE_URL, 403, {}, body, rate_limit_retry_after_default=300)
    assert excinfo.value.status.state is SiteHealthState.WAF_CHALLENGE


def test_navigate_probe_raises_on_rate_limit_fixture() -> None:
    body = (_FIXTURES_ROOT / "rate_limited" / "429_retry_after.html").read_text(encoding="utf-8")
    with pytest.raises(SiteHealthError, match=r"(?i)rate[ _]?limited") as excinfo:
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
    assert body, "ok fixture body must be non-empty for the probe test to be meaningful"
    result = _probe_or_raise(_PROBE_URL, 200, {}, body, rate_limit_retry_after_default=300)
    assert result is None


def test_build_context_kwargs_boundary_rationale_comment_present() -> None:
    # ``_build_context_kwargs`` returns ``dict[str, Any]`` because the dict
    # is spread into ``browser.new_context(**kwargs)`` whose Playwright stubs
    # accept heterogeneous keyword arguments (storage_state, proxy,
    # viewport, locale, ...).  The ``"irreducible"`` boundary rationale
    # comment must remain in session.py to document why Any is unavoidable
    # at this third-party API boundary.
    import pathlib

    session_path = pathlib.Path(__file__).parent.parent / "session.py"
    assert session_path.exists(), f"session.py not found at {session_path}"
    source = session_path.read_text(encoding="utf-8")
    assert "irreducible" in source, (
        "Boundary rationale comment containing 'irreducible' is missing from "
        "browser/session.py. The ``dict[str, Any]`` return annotation on "
        "_build_context_kwargs must document that Any is the correct type at "
        "the Playwright new_context() boundary."
    )
    assert "_build_context_kwargs" in source, (
        "_build_context_kwargs function must be present in browser/session.py; "
        "the boundary rationale test references this function by name."
    )
