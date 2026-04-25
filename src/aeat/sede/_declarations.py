"""Read-only walker over AEAT's *Consultar declaraciones presentadas* surface.

The expediente-tree walker (`_walker.walk_expedientes_tree`) walks
``Mis Expedientes`` (``/wlpl/TEWV-CORE/ResumenVlt``) which is a
*procedures* surface — sanciones, recursos, gestión recaudación —
not the canonical filings register. To read Kent's actual filing
history (every quarterly Modelo 130 / 303, annual Modelo 100 / 390,
retentions, informativas) we drive the
``Consultar declaraciones presentadas`` form at
``/wlpl/SCEJ-MANT/CONSUL/index.zul``.

Captured live (2026-04-25, NIE Y4113523X): the form is built on the
ZK framework. Input ids (``c5uX10``, ``jQSGd0``, ...) are
auto-generated and reshuffle on every page load — selectors must
bind on label text, not on ids. The submit action is a real
``Buscar`` button issuing a ZK AJAX RPC; URL parameters alone do
not drive results.

The walker drives the form for one ``(modelo, ejercicio)`` query at
a time. Multi-modelo / multi-year sweeps loop the helper at the
caller.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Literal

from playwright.async_api import Page, async_playwright
from pydantic import BaseModel, ConfigDict, Field

from ..browser import Profile
from ..browser.session import BrowserSession
from ..config import Settings
from ..logging import get_logger
from ._errors import SedeNavigationError, SedeParseError

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)


_LISTING_URL = "https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"
_NAVIGATION_TIMEOUT_MS = 30_000
_FORM_INTERACTION_TIMEOUT_MS = 10_000
_BUSCAR_SETTLE_MS = 3_000

_STRICT_FROZEN: Final[ConfigDict] = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
)


class Declaration(BaseModel):
    """One row from *Consultar declaraciones presentadas*.

    Attributes:
        modelo: AEAT modelo code (``"100"``, ``"130"``, ``"303"``, ...).
        ejercicio: Tax year (``2024``).
        period: Period token as printed on the row (``"0A"`` for
            annual, ``"1T"``-``"4T"`` for quarterly, ``"01"``-``"12"``
            for monthly modelos).
        expediente_id: AEAT expediente identifier — same shape used
            by the per-modelo capture flow.
        estado: Row state (``"ALTA"``, ``"BAJA"``, ...).
        tipo_solicitud: Optional "Tipo de solicitud" cell (free-text;
            empty for routine filings).
        observaciones: Optional observations cell.
        presented_at: Timestamp of the filing's submission as printed
            in the row (Europe/Madrid, parsed naive then UTC-tagged).
        justificante_link_text: ``"Ver"`` when AEAT exposes the
            justificante PDF directly, ``None`` otherwise.
        archive_link_text: Same for the archived presentation file.
        mode: Structural read-only marker.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    expediente_id: str = Field(min_length=12, max_length=32)
    estado: str = Field(min_length=1, max_length=16)
    tipo_solicitud: str | None = Field(default=None, max_length=128)
    observaciones: str | None = Field(default=None, max_length=512)
    presented_at: datetime
    justificante_link_text: str | None = Field(default=None, max_length=32)
    archive_link_text: str | None = Field(default=None, max_length=32)
    mode: Literal["read"] = "read"


async def walk_declarations_register(
    session: AeatSession,
    *,
    modelo: str,
    ejercicio: int,
    settings: Settings | None = None,
) -> tuple[Declaration, ...]:
    """Drive the *Consultar declaraciones presentadas* form for one query.

    Args:
        session: Authenticated AEAT session whose
            ``storage_state_path`` carries valid cookies.
        modelo: Modelo code to query (``"100"``, ``"130"``, ...). The
            form's modelo combobox is matched on the leading
            ``"<modelo> -"`` text.
        ejercicio: Tax year to query (``2024``).
        settings: Optional :class:`Settings` override.

    Returns:
        Tuple of :class:`Declaration` records, one per filing row.
        Empty when AEAT returns "No se han encontrado resultados".

    Raises:
        SedeNavigationError: When the form fails to load, the
            modelo / ejercicio cannot be selected, or Buscar does not
            settle within the timeout.
        SedeParseError: When the result table cannot be parsed.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession.storage_state_path is None; run `aeat auth login` first")

    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=session.storage_state_path,
    )
    async with async_playwright() as pw:
        browser_session = BrowserSession(pw, settings, profile)
        context = await browser_session.create_context(
            storage_state_path=session.storage_state_path,
        )
        try:
            page = await context.new_page()
            await _drive_search(page, modelo=modelo, ejercicio=ejercicio)
            return _parse_listbox(await page.content(), modelo=modelo, ejercicio=ejercicio)
        finally:
            await context.close()


async def _drive_search(
    page: Page,
    *,
    modelo: str,
    ejercicio: int,
) -> None:
    """Fill the form and click Buscar. No-op return on success."""
    try:
        await page.goto(
            _LISTING_URL,
            wait_until="networkidle",
            timeout=_NAVIGATION_TIMEOUT_MS,
        )
    except Exception as exc:
        raise SedeNavigationError(f"goto {_LISTING_URL!r} failed: {exc}") from exc
    await page.wait_for_timeout(1500)

    await _select_combobox_value(
        page,
        label_text="Modelo (*)",
        option_match=f"{modelo} -",
    )
    await _select_combobox_value(
        page,
        label_text="Ejercicio (*)",
        option_match=str(ejercicio),
    )

    try:
        await (
            page.locator("button.z-button")
            .filter(has_text="Buscar")
            .click(
                timeout=_FORM_INTERACTION_TIMEOUT_MS,
            )
        )
    except Exception as exc:
        raise SedeNavigationError(f"clicking Buscar failed: {exc}") from exc
    await page.wait_for_timeout(_BUSCAR_SETTLE_MS)


async def _select_combobox_value(
    page: Page,
    *,
    label_text: str,
    option_match: str,
) -> None:
    """Open the combobox after ``label_text`` and pick an option matching ``option_match``."""
    label = page.get_by_text(label_text, exact=True).first
    button = label.locator('xpath=following::a[contains(@class,"z-combobox-button")][1]')
    try:
        await button.click(timeout=_FORM_INTERACTION_TIMEOUT_MS)
    except Exception as exc:
        raise SedeNavigationError(f"opening combobox after label {label_text!r} failed: {exc}") from exc
    await page.wait_for_timeout(400)

    target = page.locator(".z-comboitem-text").filter(has_text=option_match).first
    try:
        await target.click(timeout=_FORM_INTERACTION_TIMEOUT_MS)
    except Exception as exc:
        raise SedeNavigationError(f"selecting option {option_match!r} for {label_text!r} failed: {exc}") from exc
    await page.wait_for_timeout(300)


_NO_RESULTS_TEXT = "No se han encontrado resultados para la consulta realizada."


def _parse_listbox(
    html: str,
    *,
    modelo: str,
    ejercicio: int,
) -> tuple[Declaration, ...]:
    """Parse the post-Buscar listbox into typed Declaration records.

    The listbox columns (in order, captured live):

    0. Desistir          (action button — ignored)
    1. Tipo de solicitud (free text)
    2. Observaciones     (free text)
    3. Expediente
    4. Periodo
    5. Estado
    6. Fecha y Hora de presentación
    7. Obtención de Justificante (anchor / "Ver")
    8. Descarga fichero presentado (anchor / "Ver")
    """
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        raise SedeParseError(f"failed to parse declaraciones HTML: {exc}") from exc

    listbox = soup.find(
        class_=lambda c: c and "z-listbox" in (c if isinstance(c, list) else [c]),
    )
    if listbox is None:
        raise SedeParseError("declaraciones response missing .z-listbox container")

    items = listbox.find_all(
        class_=lambda c: c and "z-listitem" in (c if isinstance(c, list) else [c]),
    )

    rows: list[Declaration] = []
    for item in items:
        cells = item.find_all(
            class_=lambda c: c and "z-listcell" in (c if isinstance(c, list) else [c]),
        )
        cell_texts = [cell.get_text(" ", strip=True) for cell in cells]

        if len(cell_texts) == 1 and cell_texts[0] == _NO_RESULTS_TEXT:
            return ()

        if len(cell_texts) < 7:
            # Defensive: skip malformed rows; AEAT layout changes
            # would manifest here. The grep guard at the
            # subpackage level catches forbidden mutation verbs
            # so this is structural-shape only.
            continue

        try:
            presented_at = _parse_presented_at(cell_texts[6])
        except ValueError as exc:
            raise SedeParseError(f"failed to parse presented_at {cell_texts[6]!r}: {exc}") from exc

        rows.append(
            Declaration(
                modelo=modelo,
                ejercicio=ejercicio,
                period=cell_texts[4],
                expediente_id=cell_texts[3],
                estado=cell_texts[5],
                tipo_solicitud=cell_texts[1] or None,
                observaciones=cell_texts[2] or None,
                presented_at=presented_at,
                justificante_link_text=cell_texts[7] or None,
                archive_link_text=cell_texts[8] if len(cell_texts) > 8 else None,
            )
        )
    return tuple(rows)


_PRESENTED_AT_RE = re.compile(
    r"^(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})$",
)


def _parse_presented_at(value: str) -> datetime:
    """Parse ``"01/02/2024 19:15:34"`` → UTC-tagged datetime.

    AEAT prints the timestamp in Europe/Madrid local time. The
    sede walker stores naive datetimes as the wall-clock observed
    on the row and tags them UTC for type discipline; downstream
    callers that need strict timezone alignment should convert via
    Europe/Madrid → UTC outside this module.
    """
    match = _PRESENTED_AT_RE.match(value)
    if match is None:
        raise ValueError(f"unexpected presented_at shape: {value!r}")
    return datetime(
        year=int(match["year"]),
        month=int(match["month"]),
        day=int(match["day"]),
        hour=int(match["hour"]),
        minute=int(match["minute"]),
        second=int(match["second"]),
        tzinfo=UTC,
    )


__all__ = [
    "Declaration",
    "walk_declarations_register",
]
