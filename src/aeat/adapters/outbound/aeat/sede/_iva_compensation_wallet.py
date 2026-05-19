"""Read-only AEAT IVA compensation wallet reader.

The wallet is external AEAT account state. This module only captures
and parses evidence from the authenticated Sede surface; calculation
selection happens later in the application reconciliation layer.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final

from bs4 import BeautifulSoup
from pydantic import AnyUrl

from .....core.config import Settings
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._adapter_utils import normalize_response_text
from ._auth_state import storage_state_for_session
from ._errors import SedeNavigationError, SedeParseError
from ._schema import IvaCompensationWalletObservation, IvaCompensationWalletRow

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_WALLET_URL = f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-iva-compensation-wallet-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=("www1.agenciatributaria.gob.es",),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)

_HEADER_TOKENS: Final[tuple[str, ...]] = (
    "ejercicio",
    "periodo",
    "gener",
    "aplic",
    "pend",
)


async def fetch_iva_compensation_wallet(
    session: AeatSession,
    *,
    target_year: int,
    target_period: str,
    taxpayer_nif: str | None = None,
    settings: Settings | None = None,
) -> IvaCompensationWalletObservation:
    """Fetch and parse AEAT's read-only IVA compensation wallet."""

    _assert_read_http("GET", _WALLET_URL)
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession has no persisted auth session; run `aeat config auth status` first")
    browser_session = await default_browser_session_factory(settings)
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            try:
                await page.goto(_WALLET_URL, wait_until="domcontentloaded")
            except PlaywrightError as exc:
                raise SedeNavigationError(f"goto {_WALLET_URL!r} failed: {exc}") from exc
            html = await page.content()
            return parse_iva_compensation_wallet_html(
                html,
                taxpayer_nif=taxpayer_nif or session.identity_nif,
                authenticated_identity=session.identity_nif,
                target_year=target_year,
                target_period=target_period,
                source_url=_WALLET_URL,
                captured_at=datetime.now(UTC),
            )
        finally:
            try:
                await context.close()
            except Exception as exc:  # noqa: BLE001 - cleanup should not mask capture outcome
                log.debug("fetch_iva_compensation_wallet: context.close suppressed: %s", exc, exc_info=True)
    finally:
        await browser_session.close()


def parse_iva_compensation_wallet_html(
    html: str,
    *,
    taxpayer_nif: str,
    authenticated_identity: str,
    target_year: int,
    target_period: str,
    source_url: str,
    captured_at: datetime,
) -> IvaCompensationWalletObservation:
    """Parse wallet rows from a captured AEAT wallet HTML page."""

    soup = BeautifulSoup(html, "html.parser")
    rows: list[IvaCompensationWalletRow] = []
    for table in soup.find_all("table"):
        header = _normalised_text(table.get_text(" "))
        if not all(token in header for token in _HEADER_TOKENS):
            continue
        for tr in table.find_all("tr"):
            cells = [_normalised_text(cell.get_text(" ")) for cell in tr.find_all(["td", "th"])]
            if len(cells) < 5 or _looks_like_header(cells):
                continue
            try:
                rows.append(_wallet_row_from_cells(cells))
            except SedeParseError:
                raise
            except Exception as exc:  # noqa: BLE001 - parser reports row context
                raise SedeParseError(f"could not parse IVA compensation wallet row {cells!r}: {exc}") from exc

    total_pending = sum((row.pending_amount for row in rows), Decimal("0"))
    return IvaCompensationWalletObservation(
        taxpayer_nif=taxpayer_nif,
        authenticated_identity=authenticated_identity,
        target_year=target_year,
        target_period=target_period,
        rows=tuple(rows),
        total_pending=total_pending,
        source_url=source_url,
        captured_at=captured_at,
        raw_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
    )


def _wallet_row_from_cells(cells: list[str]) -> IvaCompensationWalletRow:
    year = _parse_year(cells[0])
    period = cells[1].strip().upper()
    if not period:
        raise SedeParseError("IVA wallet period cell is empty")
    return IvaCompensationWalletRow(
        generation_year=year,
        generation_period=period,
        generated_amount=_parse_spanish_decimal(cells[2]),
        applied_amount=_parse_spanish_decimal(cells[3]),
        pending_amount=_parse_spanish_decimal(cells[4]),
        raw_label=" | ".join(cells[:5]),
    )


def _parse_year(value: str) -> int:
    match = re.search(r"\b(20[0-9]{2})\b", value)
    if match is None:
        raise SedeParseError(f"IVA wallet generation year could not be parsed from {value!r}")
    return int(match.group(1))


def _parse_spanish_decimal(value: str) -> Decimal:
    cleaned = value.replace("\xa0", " ").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned:
        raise SedeParseError("IVA wallet amount cell is empty")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise SedeParseError(f"IVA wallet amount could not be parsed from {value!r}") from exc
    if amount < Decimal("0"):
        raise SedeParseError(f"IVA wallet amount must be non-negative: {value!r}")
    return amount


def _normalised_text(value: str) -> str:
    return normalize_response_text(value).casefold()


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(cells)
    return "ejercicio" in joined and "period" in joined


def _assert_read_http(method: str, url: str) -> None:
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


__all__ = [
    "fetch_iva_compensation_wallet",
    "parse_iva_compensation_wallet_html",
]
