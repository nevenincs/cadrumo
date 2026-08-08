"""The bulk register sweep reports one failed pair and keeps walking the rest.

Cross-pair continuation had no coverage of any kind. Per-pair absorption is
covered -- a refusal raised by one walk becomes a
:class:`~application.live.FiledDataCaptureFailureRow` -- but that proves only
that the failure was turned into a row, not that the loop around it went on to
the next pair. A sweep that stopped at the first failure would report exactly
the same row for that pair and simply omit every later one, which reads as "the
taxpayer filed nothing after this" rather than as an aborted run.

Reaching that loop offline needs the register-injection seam rather than route
interception alone. Interception makes the browser reachable with no production
change, but both bulk functions first resolve a verified session, which runs the
live-read access gate and then the central live-session writer; satisfying that
would ARM real AEAT access. Injecting an already-open register is what lets this
test never request live access in the first place.

Everything else is real: a real :class:`AeatSession`, a real headless Chromium
page, a real ``DeclaracionesRegisterSession``, the real form drive, the real
parse and the real sweep. Only the network is intercepted, and only with
synthetic fixtures -- nothing here contacts AEAT.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta

import pytest
from playwright.async_api import Route, async_playwright

from ....adapters.outbound.aeat.auth import AeatSession, CertificateSessionDetail
from ....adapters.outbound.aeat.sede import DeclaracionesRegisterSession
from ....core.config import override_settings
from ....tests import FIXTURES_DIR
from .._filed_data_capture import list_filed_data_bulk
from .._remote_state_models import BulkFiledDataListingReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_MODELO = "100"
# Both years carry a registry revision for this modelo, so both survive the
# pre-flight query plan and actually reach the register walk.
_YEAR_FROM = 2024
_YEAR_TO = 2025


def _offline_session() -> AeatSession:
    """A real session carrying no persisted browser state and reaching nothing."""
    authenticated_at = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)
    return AeatSession(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + timedelta(hours=8),
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=CertificateSessionDetail(
            certificate_thumbprint="aabbcc",
            certificate_subject="CN=test",
        ),
    )


def _fixture(stem: str) -> str:
    return (_FIXTURE_ROOT / f"{stem}.html").read_text(encoding="utf-8")


# Lifted from the fixture's raw markup, never from anything the production
# parser computes, so a comparison against them is a cross-check rather than the
# parser measured against itself.
_TOTAL_REGISTROS_RE = re.compile(r"de (\d+) en total")
_LISTITEM_RE = re.compile(r'class="[^"]*\bz-listitem\b')


def _declared_total_in(html: str) -> int:
    """Return the record total the fixture's own pager label states."""
    match = _TOTAL_REGISTROS_RE.search(html)
    assert match is not None, "fixture's pager label shape changed; it can no longer declare a total"
    return int(match.group(1))


def _rendered_rows_in(html: str) -> int:
    """Count the rendered grid rows straight out of the fixture markup."""
    return len(_LISTITEM_RE.findall(html))


def test_a_truncated_pair_is_reported_while_the_other_pair_still_yields_rows() -> None:
    """One pair refused, another pair's rows returned, every queued page consumed.

    The assertions are deliberately order-independent. The route handler cannot
    see which ``(modelo, ejercicio)`` a navigation belongs to -- the pair is
    chosen after the document loads, by driving the comboboxes -- so the pages
    are served in walk order and the property is asserted without naming which
    year got which page: some pair is refused for truncation, some OTHER pair
    returns rows, and no pair does both.

    Nothing here asserts a pair count. A count would pass just as well if the
    sweep walked one pair twice, and would need rewriting the moment the fixture
    pool changed.
    """
    pending = [
        _fixture("declaraciones-register-form-paginated-synthetic"),
        _fixture("declaraciones-register-form-complete-synthetic"),
    ]
    served: list[str] = []

    async def _serve(route: Route) -> None:
        """Fulfil the real listing URL with the next queued synthetic page."""
        if not route.request.is_navigation_request():
            await route.fulfill(status=204, body="")
            return
        body = pending.pop(0) if pending else served[-1]
        served.append(body)
        await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)

    async def _sweep() -> BulkFiledDataListingReport:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                page = await context.new_page()
                await page.route("**/*", _serve)
                register = DeclaracionesRegisterSession(_offline_session(), page, context)
                with override_settings(
                    cadrumo_browser_form_interaction_timeout_ms=3000,
                    cadrumo_browser_buscar_settle_ms=50,
                ):
                    return await list_filed_data_bulk(
                        year_from=_YEAR_FROM,
                        year_to=_YEAR_TO,
                        modelos=(_MODELO,),
                        register=register,
                    )
            finally:
                await browser.close()

    report = asyncio.run(_sweep())

    assert not pending, (
        "the sweep stopped before requesting every queued page, so it did not continue past the failed pair"
    )

    truncation_failures = [failure for failure in report.failures if failure.error_type == "SedeParseError"]
    assert truncation_failures, f"no truncation refusal was absorbed into a failure row: {report.failures}"
    # Both numbers are read straight out of the fixture's own markup rather than
    # from anything the parser computed, so the row is cross-checked against the
    # page it came from and neither number is hardcoded here.
    truncated_page = _fixture("declaraciones-register-form-paginated-synthetic")
    declared_total = _declared_total_in(truncated_page)
    rendered_rows = _rendered_rows_in(truncated_page)
    assert rendered_rows < declared_total, "fixture no longer renders fewer rows than its pager declares"
    for failure in truncation_failures:
        assert str(rendered_rows) in failure.message and str(declared_total) in failure.message, (
            f"the failure row lost the rendered-versus-declared cause: {failure.message!r}"
        )

    assert report.rows, "the untruncated pair returned no rows, so the sweep did not survive the refusal"
    refused_years = {failure.year for failure in truncation_failures}
    returned_years = {row.year for row in report.rows}
    assert not (refused_years & returned_years), (
        f"a pair both refused and returned rows: refused={refused_years} returned={returned_years}"
    )
