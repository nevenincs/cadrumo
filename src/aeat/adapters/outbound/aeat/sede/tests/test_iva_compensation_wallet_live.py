"""Opt-in live smoke test for the AEAT IVA compensation wallet reader.

Runs only when ``AEAT_LIVE_TESTS_ENABLED=1`` is set. The test acquires
an operator-approved Cl@ve Móvil session against the Pre303 presentation
surface and then drives the same read-only wallet adapter used by the
application capture workflow. It asserts structural evidence only; it
never embeds an operator's tax amounts into source or snapshots.
"""

from __future__ import annotations

from datetime import date

import pytest

from ......application.auth import AuthProviderKind, ensure_authenticated_aeat_session
from ......core import Modelo, Period
from ......core.config import load_settings
from ......core.errors import AeatError
from ......tests.live_gate import requires_live_enabled
from .....persistence.storage import get_master_key_provider
from .._errors import SedeError
from .._iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_fetch_iva_compensation_wallet_live_returns_read_observation() -> None:
    """The wallet reader reaches AEAT and returns strict read-only evidence."""

    requires_live_enabled()
    settings = load_settings()
    try:
        with get_master_key_provider():
            auth = await ensure_authenticated_aeat_session(
                settings,
                kind=AuthProviderKind.CLAVE_MOVIL,
                operation="sede-iva-wallet-live-test",
                target_url=PRE303_PRESENTATION_SERVICE_URL,
            )
    except AeatError as exc:
        pytest.fail(f"Cl@ve-móvil live authentication is not available: {exc}")

    today = date.today()
    target_year = today.year
    target_period = _quarter_period(target_year, today.month)
    try:
        with get_master_key_provider():
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
    if str(observation.source_url) != IVA_COMPENSATION_WALLET_URL:
        pytest.fail("live IVA wallet observation source URL did not match configured wallet URL")
    if observation.raw_sha256 is None:
        pytest.fail("live IVA wallet observation did not include raw evidence hash")
    if not all(row.mode == "read" for row in observation.rows):
        pytest.fail("live IVA wallet observation included a non-read row")


def _quarter_period(year: int, month: int) -> Period:
    quarter = ((month - 1) // 3) + 1
    return Period.from_year_and_code(year, f"{quarter}T")
