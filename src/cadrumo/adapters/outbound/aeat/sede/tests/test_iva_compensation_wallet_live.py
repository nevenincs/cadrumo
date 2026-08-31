"""Opt-in live smoke test for the AEAT IVA compensation wallet reader.

Runs only when ``CADRUMO_LIVE_TESTS_ENABLED=1`` is set. The test acquires
an operator-approved Cl@ve Móvil session against the Pre303 presentation
surface and then drives the same read-only wallet adapter used by the
application capture workflow. It asserts structural evidence only; it
never embeds an operator's tax amounts into source or snapshots.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit

import pytest

from ......application.auth.sessions import ensure_authenticated_aeat_session
from ......core.auth_provider import AuthProviderKind
from ......core.modelo import Modelo
from ......core.period import Period
from ......core.config import Settings, load_settings
from ......core.errors.hierarchy import CadrumoError
from ......tests.live_gate import requires_live_enabled
from .._iva_compensation_wallet_parsing import is_aeat_wallet_read_url
from ..errors import SedeError
from ..iva_compensation_wallet import (
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _assert_source_url_is_a_wallet_read(source_url: str) -> None:
    """Assert the recorded URL is a wallet read, without pinning which host served it.

    AEAT load-balances an authenticated session across its numbered sede
    hosts, so the host that answers is assigned rather than chosen. The
    invariant a successful read genuinely satisfies is therefore that the
    URL is the wallet ROUTE on some host under the AEAT apex - not that it
    equals a URL built against one particular host.

    This check previously asserted whole-URL equality against a constant
    pinned to a single numbered host, which fails a successful read that
    landed anywhere else: the assertion refused correct behaviour. It had
    never been contradicted because nothing runs this test outside an
    operator-approved live session, so it was an unexamined claim rather
    than a test that broke. The replacement is deliberately no stronger
    than the invariant, since a stronger one could not be exercised here
    either and would only re-occupy the same slot.
    """
    if is_aeat_wallet_read_url(source_url):
        return
    external = Settings.external_constants()
    landed = urlsplit(source_url)
    if landed.path != external.aeat.sede_paths.iva_compensation_wallet:
        pytest.fail(f"live IVA wallet source URL is not the wallet route: {landed.path!r}")
    pytest.fail(f"live IVA wallet source URL is not under the AEAT apex: {source_url!r}")


@pytest.mark.asyncio
async def test_fetch_iva_compensation_wallet_live_returns_read_observation() -> None:
    """The wallet reader reaches AEAT and returns strict read-only evidence."""

    requires_live_enabled()
    settings = load_settings()
    try:
        auth = await ensure_authenticated_aeat_session(
            settings,
            kind=AuthProviderKind.CLAVE_MOVIL,
            operation="sede-iva-wallet-live-test",
            target_url=PRE303_PRESENTATION_SERVICE_URL,
        )
    except CadrumoError as exc:
        pytest.fail(f"Cl@ve-móvil live authentication is not available: {exc}")

    today = date.today()
    target_year = today.year
    target_period = _quarter_period(target_year, today.month)
    try:
        observation = await fetch_iva_compensation_wallet(
            auth.session,
            target_year=target_year,
            target_period=target_period,
            settings=settings,
        )
    except SedeError as exc:
        pytest.fail(f"live IVA compensation wallet read failed: {exc}")

    if observation.mode != "read":
        pytest.fail("live IVA wallet observation was not read-only")
    if observation.target_modelo != Modelo.M303:
        pytest.fail("live IVA wallet observation target modelo was not 303")
    if observation.target_year != target_year or observation.target_period != target_period:
        pytest.fail("live IVA wallet observation target period did not match requested period")
    _assert_source_url_is_a_wallet_read(str(observation.source_url))
    if observation.raw_sha256 is None:
        pytest.fail("live IVA wallet observation did not include raw evidence hash")
    if not all(row.mode == "read" for row in observation.rows):
        pytest.fail("live IVA wallet observation included a non-read row")


def _quarter_period(year: int, month: int) -> Period:
    quarter = ((month - 1) // 3) + 1
    return Period.from_year_and_code(year, f"{quarter}T")
