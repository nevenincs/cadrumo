"""Single live round-trip for the Tier-1 remote fetchers.

This is the one live test introduced by issue #239. It gates on
``AEAT_LIVE_TESTS_ENABLED`` via :func:`aeat.cli._live.requires_live_enabled`
and performs the following real end-to-end exercise against Kent's
authenticated AEAT session:

1. Acquire an :class:`aeat.auth.AeatSession` through the real
   :class:`AeatAuthenticator` (backed by Kent's certificate plus, on
   fresh sessions, a real Cl@ve-movil 2FA push to Kent's phone —
   the sanctioned human touchpoint). Subsequent runs inside the
   18-minute ``AEAT_SESSION_IDLE_TTL`` resume from the persisted
   storage state without re-prompting.
2. Spin up a live :class:`aeat.status.StatusReader` against the
   authenticated context. The reader already ships a
   Protocol-compatible ``fetch_filing_detail`` surface; a tiny inline
   adapter projects each :class:`aeat.history.FiledModelo` into the
   new :class:`aeat.remote.RemoteFiling` boundary record.
3. Drive :func:`aeat.remote.fetch_modelo_303` against the live AEAT
   session for a known ``(modelo=303, period)`` pair sourced from
   ``AEAT_LIVE_REMOTE_FILING_PERIOD`` in ``env/.env``.
4. Assert the resulting :class:`FilingDetail303` round-trips cleanly
   through ``model_validate(instance.model_dump())``.

No mocks, patches, fakes, or stubs are used; every collaborator is
either a real production object or a small Protocol-conforming Python
class declared inline. The test MUST NOT call any write path; the
Layer 3 grep guard continues to pass after this file lands.
"""

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from ..cli._live import requires_live_enabled
from ..config import Settings
from ..formulas import FiscalPeriod, Quarter
from ..history import FiledModelo
from ..remote import RemoteFiling, fetch_modelo_303
from ..remote.filings._adapters import remote_filing_from_history

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


_QUARTER_BY_TOKEN: dict[str, Quarter] = {
    "1T": Quarter.Q1,
    "2T": Quarter.Q2,
    "3T": Quarter.Q3,
    "4T": Quarter.Q4,
}


def _parse_fiscal_period_from_env() -> FiscalPeriod:
    """Parse ``AEAT_LIVE_REMOTE_FILING_PERIOD`` into a :class:`FiscalPeriod`.

    Accepts either ``"2025-1T"`` (quarterly) or ``"2025"`` (annual).
    Skips the test cleanly when the env var is unset so CI stays
    deterministic across Kent's active filing periods.
    """
    raw = os.environ.get("AEAT_LIVE_REMOTE_FILING_PERIOD", "").strip()
    if not raw:
        pytest.skip("AEAT_LIVE_REMOTE_FILING_PERIOD is unset; set it in env/.env to run this live test")
    if "-" in raw:
        year_str, quarter_token = raw.split("-", maxsplit=1)
        try:
            year = int(year_str)
        except ValueError:
            pytest.fail(f"invalid year in AEAT_LIVE_REMOTE_FILING_PERIOD={raw!r}")
        quarter = _QUARTER_BY_TOKEN.get(quarter_token.upper())
        if quarter is None:
            pytest.fail(f"unrecognised quarter token in AEAT_LIVE_REMOTE_FILING_PERIOD={raw!r}")
        return FiscalPeriod(year=year, quarter=quarter)
    try:
        return FiscalPeriod(year=int(raw))
    except ValueError:
        pytest.fail(f"invalid annual year in AEAT_LIVE_REMOTE_FILING_PERIOD={raw!r}")


class _StatusReaderRemoteFetcher:
    """Project a live :class:`StatusReader` into a :class:`RemoteFilingFetcher`.

    The adapter is declared inline so the live test neither modifies
    nor imports from :class:`aeat.status._reader` internals; it only
    consumes the public ``fetch_filing_detail`` method the reader
    already exposes.
    """

    def __init__(self, reader: Any) -> None:
        self._reader = reader

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        filed: tuple[FiledModelo, ...] = await self._reader.fetch_filing_detail(
            modelo,
            period,
            use_cache=use_cache,
        )
        return tuple(remote_filing_from_history(record) for record in filed)


@pytest.mark.asyncio
async def test_live_round_trip_modelo_303() -> None:
    """End-to-end round-trip of one Modelo 303 filing through the remote surface."""
    requires_live_enabled()

    period = _parse_fiscal_period_from_env()

    settings = Settings()
    if settings.aeat_certificate_path is None or settings.aeat_certificate_password_secret is None:
        pytest.skip("AEAT certificate env vars are not fully configured")

    # Bridge the passphrase into the process env for the cert loader
    # (same pattern the other live auth tests use).
    os.environ.setdefault(
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        settings.aeat_certificate_password_secret.get_secret_value(),
    )

    # Local imports keep the module-level import cost low when the
    # test is skipped and keep the Playwright dependency optional at
    # collection time.
    from playwright.async_api import async_playwright

    from ..auth import AeatAuthenticator, AeatSession, BrowserSessionFactory
    from ..browser.profile import Profile
    from ..browser.session import BrowserSession
    from ..status import CertificateBackend as StatusCertBackend
    from ..status import StatusCache, StatusReader

    class _PreloadedCertBackend:
        """Minimal :class:`StatusCertBackend`-conforming adapter.

        The live StatusReader only calls ``preload_into_browser_context``;
        the adapter delegates to the cert-bundle-aware public helper in
        :mod:`aeat.auth.certificate` so no private module import is
        required from this test file.
        """

        def __init__(self, cert: Any) -> None:
            self._cert = cert

        async def preload_into_browser_context(self, context: Any) -> None:
            from ..auth.certificate import preload_into_browser_context

            preload_into_browser_context(self._cert, context)

    async with async_playwright() as playwright:
        profile = Profile(
            name="live-remote-fetch",
            storage_state_path=settings.aeat_token_dir / "live_remote_fetch_state.json",
        )
        browser_session = BrowserSession(
            playwright=playwright,
            settings=settings,
            profile=profile,
        )

        async def factory(_settings: Any) -> Any:
            return browser_session

        typed_factory = cast(BrowserSessionFactory, factory)

        async with AeatAuthenticator(settings, browser_session_factory=typed_factory) as auth:
            aeat_session: AeatSession = await auth.authenticate()
            assert aeat_session.is_stale() is False
            assert aeat_session.certificate_nif

            cert = auth.load_certificate()
            cert_backend = cast(StatusCertBackend, _PreloadedCertBackend(cert))

            cache = StatusCache(settings.aeat_status_cache_dir, settings.aeat_status_cache_ttl_s)
            async with StatusReader(
                browser_session=browser_session,
                cert_backend=cert_backend,
                cache=cache,
                settings=settings,
                tax_id=aeat_session.certificate_nif,
            ) as reader:
                remote_fetcher = _StatusReaderRemoteFetcher(reader)
                details = await fetch_modelo_303(remote_fetcher, period=period)

            if not details:
                pytest.skip(
                    f"AEAT returned no Modelo 303 filing for {period}; pick a known-good period in env/.env",
                )

            detail = details[0]
            # Round-trip through model_dump + model_validate so the
            # test exercises both the serialiser and the strict
            # validator. A single tripped invariant surfaces here as
            # a hard failure rather than a silent drift.
            dumped = detail.model_dump()
            reconstructed = type(detail).model_validate(dumped)
            assert reconstructed == detail
            assert reconstructed.filing.modelo == "303"
            assert reconstructed.filing.mode == "read"
