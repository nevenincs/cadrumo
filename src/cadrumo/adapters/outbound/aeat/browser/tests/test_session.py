"""BrowserSession lifecycle, provisioner, and site-health contracts.

These tests exercise the concrete
:class:`~adapters.outbound.aeat.browser.BrowserSession` factory rather than a
parallel session abstraction. They assert one-live-context ownership,
idempotent and retryable browser cleanup, explicit
:class:`~adapters.outbound.aeat.browser.BrowserFailureMode` classification,
storage-state forwarding from :class:`~adapters.outbound.aeat.browser.Profile`,
certificate provisioning through
:class:`~adapters.outbound.aeat.auth.CertificateContextProvisioner`, and the
fixture-backed
:func:`~adapters.outbound.aeat.browser._site_health_probe.probe_response`
branch used by :meth:`~adapters.outbound.aeat.browser.BrowserSession.navigate`.

See Also:
    :mod:`~adapters.outbound.aeat.browser.session`
        Production Playwright session manager that owns Chromium lifecycle and
        health-probed navigation.
    :mod:`~adapters.outbound.aeat.browser._factory`
        Browser factory and page context manager that delegate to the session
        teardown contract.
    :class:`~adapters.outbound.aeat.auth.BrowserSessionLike`
        Auth-provider protocol that mirrors context creation while allowing
        lightweight tests to omit concrete browser ownership.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, cast, override

import pytest
from playwright.async_api import BrowserContext, Page, Playwright
from pydantic import SecretStr

from ......application.auth_credentials import ActiveCertificateCredentials
from ......core.config import Settings
from ......core.errors import SiteHealthError
from ......tests import FIXTURES_DIR
from ......tests.secure_sql import isolated_runtime_profile
from ...auth import (
    AEAT_SESSION_IDLE_TTL,
    AeatAuthenticator,
    AeatLoginAssertionError,
    AeatSession,
    BrowserContextLike,
    BrowserSessionLike,
)
from ...auth._providers import CertificateSessionDetail, ClaveMovilSessionDetail
from ...auth.tests._authenticator_support import SECRET_PASSPHRASE, _build_bundle
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
async def test_authenticator_retains_browser_when_context_failure_cleanup_needs_retry(tmp_path: Path) -> None:
    """Fresh auth retains its concrete browser owner until teardown succeeds."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="auth-browser-close-retry"):
        settings = Settings(cadrumo_browser_close_timeout_ms=1_000)
        profile = Profile(name="auth", storage_state_path=tmp_path / "auth-state.json")
        playwright_adapter = RecordingPlaywright()
        playwright_adapter.chromium.next_close_failures = 2
        browser_session = BrowserSession(
            playwright=cast(Playwright, playwright_adapter),
            settings=settings,
            profile=profile,
            evasion_strategy=FailingEvasion(),
        )

        async def browser_factory(factory_settings: Settings) -> BrowserSessionLike:
            assert factory_settings is settings
            return browser_session

        bundle_path = _build_bundle(tmp_path)
        authenticator = AeatAuthenticator(
            settings,
            credentials=ActiveCertificateCredentials(
                certificate_path=bundle_path,
                password=SecretStr(SECRET_PASSPHRASE),
                friendly_name=None,
            ),
            browser_session_factory=browser_factory,
        )

        with pytest.raises(BrowserError, match="boom from evasion"):
            await authenticator.authenticate()

        retained_browser = playwright_adapter.chromium.launched_browsers[0]
        assert retained_browser.close_calls == 2
        assert playwright_adapter.chromium.live_browser_count == 1
        assert authenticator._browser_session is browser_session

        await authenticator.close()

        assert retained_browser.close_calls == 3
        assert playwright_adapter.chromium.live_browser_count == 0
        assert authenticator._browser_session is None


@pytest.mark.asyncio
async def test_authenticator_verify_rejects_non_active_or_non_certificate_session_before_navigation(
    tmp_path: Path,
) -> None:
    """Only the exact active certificate session may use an owned context."""
    settings = Settings()
    profile = Profile(name="verify", storage_state_path=tmp_path / "verify-state.json")
    browser_session = BrowserSession(
        playwright=cast(Playwright, RecordingPlaywright()),
        settings=settings,
        profile=profile,
        evasion_strategy=_RecordingEvasion(),
    )
    context = await browser_session.create_context()
    bundle_path = _build_bundle(tmp_path)
    authenticator = AeatAuthenticator(
        settings,
        credentials=ActiveCertificateCredentials(
            certificate_path=bundle_path,
            password=SecretStr(SECRET_PASSPHRASE),
            friendly_name=None,
        ),
    )
    current = datetime.now(UTC)
    active = AeatSession(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        storage_state_path=profile.storage_state_path,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="active-thumbprint",
            certificate_subject="CN=ACTIVE,SERIALNUMBER=12345678Z",
        ),
    )
    authenticator._browser_session = browser_session
    authenticator._context = cast(BrowserContextLike, context)
    authenticator._active_session = active

    with pytest.raises(AeatLoginAssertionError, match="exact active certificate-bound session"):
        await authenticator.verify(active.model_copy())

    wrong_provider = AeatSession(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        storage_state_path=profile.storage_state_path,
        identity_nif="12345678Z",
        provider_detail=ClaveMovilSessionDetail(dni_nie="12345678Z"),
    )
    authenticator._active_session = wrong_provider
    with pytest.raises(AeatLoginAssertionError, match="exact active certificate-bound session"):
        await authenticator.verify(wrong_provider)

    await authenticator.close()


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
