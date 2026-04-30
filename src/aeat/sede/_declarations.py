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

import contextlib
import hashlib
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Literal
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ..browser import Profile
from ..browser.session import BrowserSession
from ..config import Settings
from ..logging import get_logger
from ._errors import JustificanteFetchError, SedeNavigationError, SedeParseError
from ._schema import JustificanteRef, SedeCapture

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)


_SEDE_BASE = "https://www6.agenciatributaria.gob.es"
_LISTING_URL = f"{_SEDE_BASE}/wlpl/SCEJ-MANT/CONSUL/index.zul"
_COTEJO_VIEW = f"{_SEDE_BASE}/wlpl/KATA-APLI/cotejo/CotejoIdSv"
_COTEJO_DOC = f"{_SEDE_BASE}/wlpl/KATA-APLI/cotejo/CotejoDocIdSv"
_COTEJO_PATH_PREFIX = "/wlpl/KATA-APLI/cotejo/CotejoIdSv"
_NAVIGATION_TIMEOUT_MS = 30_000
_FORM_INTERACTION_TIMEOUT_MS = 10_000
_BUSCAR_SETTLE_MS = 3_000
_VER_CLICK_TIMEOUT_MS = 15_000

# AEAT CSV shape: 8-24 uppercase alphanumeric characters. Mirror
# of ``_CSV_LABEL_RE`` in :mod:`aeat.justificante._extract`. Used
# to shape-validate the CSV extracted from a cotejo URL so a
# malformed AEAT response cannot land arbitrary text in the
# downstream :class:`JustificanteRef.pdf_url`.
_CSV_SHAPE_RE = re.compile(r"^[A-Z0-9]{8,24}$")

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


@asynccontextmanager
async def shared_playwright(
    session: AeatSession,
) -> AsyncIterator[Playwright]:
    """Yield a long-lived Playwright instance for bulk register loops.

    `walk_declarations_register` and `capture_declaration` each spin
    up their own Playwright + BrowserSession when called standalone,
    which is fine for one-shot use. Bulk callers
    (e.g. ``aeat sede capture-corpus``) pay ~1s per iteration on
    Playwright startup; wrapping the loop in this helper amortises
    that cost across the entire run.

    Usage:

    .. code-block:: python

        async with shared_playwright(session) as pw:
            for modelo in modelos:
                rows = await walk_declarations_register(
                    session, modelo=modelo, ejercicio=ejercicio,
                    playwright=pw,
                )
                for declaration in rows:
                    capture = await capture_declaration(
                        session, declaration, playwright=pw,
                    )

    Args:
        session: Authenticated AEAT session. Validated upfront so
            the loop fails fast rather than per-iteration.

    Yields:
        A live :class:`Playwright` instance. Cleaned up automatically
        on exit.

    Raises:
        SedeNavigationError: When ``session.storage_state_path`` is
            ``None``.
    """
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession.storage_state_path is None; run `aeat auth login` first",
        )
    async with async_playwright() as pw:
        yield pw


@asynccontextmanager
async def _open_register_page(
    session: AeatSession,
    *,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
) -> AsyncIterator[tuple[Page, BrowserContext]]:
    """Yield a Playwright ``(page, context)`` bound to the AEAT session.

    Both :func:`walk_declarations_register` and :func:`capture_declaration`
    need the same bringup: validate ``session.storage_state_path``,
    build a :class:`Profile`, spin up Playwright, and create a
    context preloaded with the session cookies. Centralising the
    scaffolding keeps the two callers structurally identical and
    fixes a latent leak where the walker did not close the
    underlying :class:`BrowserSession` after use.

    Args:
        session: Authenticated AEAT session.
        settings: Optional :class:`Settings` override.
        playwright: Optional pre-started :class:`Playwright` instance
            (typically produced by :func:`shared_playwright`). When
            provided, the helper reuses it instead of starting its
            own — saves ~1s per iteration in bulk loops. Caller owns
            the lifetime; this helper does not stop a passed-in
            instance.

    Yields:
        A ``(page, context)`` pair. The page is a fresh
        :class:`Page` inside the storage-state-loaded context.

    Raises:
        SedeNavigationError: When ``session.storage_state_path`` is
            ``None``.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession.storage_state_path is None; run `aeat auth login` first",
        )
    profile = Profile(
        name=settings.aeat_default_profile_name,
        storage_state_path=session.storage_state_path,
    )
    if playwright is not None:
        async with _opened_browser_session(playwright, settings, profile, session) as (page, context):
            yield page, context
        return
    async with async_playwright() as pw, _opened_browser_session(pw, settings, profile, session) as (page, context):
        yield page, context


@asynccontextmanager
async def _opened_browser_session(
    pw: Playwright,
    settings: Settings,
    profile: Profile,
    session: AeatSession,
) -> AsyncIterator[tuple[Page, BrowserContext]]:
    """Inner helper: create + tear down a BrowserSession + context."""
    browser_session = BrowserSession(pw, settings, profile)
    context = await browser_session.create_context(
        storage_state_path=session.storage_state_path,
    )
    try:
        page = await context.new_page()
        yield page, context
    finally:
        with contextlib.suppress(Exception):
            await context.close()
        with contextlib.suppress(Exception):
            await browser_session.close()


async def walk_declarations_register(
    session: AeatSession,
    *,
    modelo: str,
    ejercicio: int,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
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
        playwright: Optional pre-started Playwright instance
            (typically from :func:`shared_playwright`). Reused
            across the call to amortise the ~1s startup cost in
            bulk loops. When ``None``, a fresh instance is started
            and torn down per call.

    Returns:
        Tuple of :class:`Declaration` records, one per filing row.
        Empty when AEAT returns "No se han encontrado resultados".

    Raises:
        SedeNavigationError: When the form fails to load, the
            modelo / ejercicio cannot be selected, or Buscar does not
            settle within the timeout.
        SedeParseError: When the result table cannot be parsed.
    """
    async with _open_register_page(session, settings=settings, playwright=playwright) as (
        page,
        _context,
    ):
        await _drive_search(page, modelo=modelo, ejercicio=ejercicio)
        return _parse_listbox(await page.content(), modelo=modelo, ejercicio=ejercicio)


async def _drive_search(
    page: Page,
    *,
    modelo: str,
    ejercicio: int,
) -> None:
    """Fill the form and click Buscar. No-op return on success.

    Raises :class:`SedeNavigationError` early when AEAT redirects to
    the login wall instead of the form (session expired) so callers
    get an actionable error rather than an opaque combobox click
    timeout.
    """
    try:
        await page.goto(
            _LISTING_URL,
            wait_until="networkidle",
            timeout=_NAVIGATION_TIMEOUT_MS,
        )
    except Exception as exc:
        raise SedeNavigationError(f"goto {_LISTING_URL!r} failed: {exc}") from exc
    await page.wait_for_timeout(1500)

    final_url = page.url
    if "/wlpl/SCEJ-MANT/CONSUL" not in final_url:
        raise SedeNavigationError(
            f"declaraciones register did not load (final URL: {final_url!r}); "
            "session likely expired — run `aeat auth login` and retry",
        )
    # Defensive: even when the URL matches, AEAT sometimes serves a
    # blank shell with no Modelo label until the JS finishes booting.
    try:
        await page.get_by_text("Modelo (*)", exact=True).first.wait_for(
            state="visible",
            timeout=_FORM_INTERACTION_TIMEOUT_MS,
        )
    except Exception as exc:
        raise SedeNavigationError(
            "declaraciones register form did not render the 'Modelo (*)' "
            f"label within {_FORM_INTERACTION_TIMEOUT_MS}ms; "
            "session likely expired or AEAT served a maintenance page",
        ) from exc

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
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        raise SedeParseError(f"failed to parse declaraciones HTML: {exc}") from exc

    listbox = soup.find(class_=_class_contains("z-listbox"))
    if listbox is None:
        raise SedeParseError("declaraciones response missing .z-listbox container")

    items = listbox.find_all(
        class_=_class_contains("z-listitem"),
    )

    rows: list[Declaration] = []
    for item in items:
        cells = item.find_all(
            class_=_class_contains("z-listcell"),
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


def _class_contains(token: str) -> Callable[[str | None], bool]:
    """Return a BeautifulSoup class matcher for a CSS class token."""

    def _matches(value: str | None) -> bool:
        if value is None:
            return False
        return token in value.split()

    return _matches


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


async def capture_declaration(
    session: AeatSession,
    declaration: Declaration,
    *,
    settings: Settings | None = None,
    playwright: Playwright | None = None,
) -> SedeCapture:
    """Fetch the raw justificante PDF behind a :class:`Declaration`.

    Drives the declaraciones register the same way
    :func:`walk_declarations_register` does, locates the row whose
    ``expediente_id`` matches ``declaration.expediente_id``, clicks
    that row's *Obtención de Justificante* button, captures the
    CSV from the resulting cotejo URL, and downloads the PDF via
    :class:`APIRequestContext` (so Chrome's PDF viewer never
    intercepts the response).

    Args:
        session: Authenticated AEAT session.
        declaration: The Declaration row to capture, typically
            obtained from :func:`walk_declarations_register`.
        settings: Optional :class:`Settings` override.
        playwright: Optional pre-started Playwright instance
            (typically from :func:`shared_playwright`). Reused
            across the call to amortise the ~1s startup cost in
            bulk loops. When ``None``, a fresh instance is started
            and torn down per call.

    Returns:
        A :class:`SedeCapture` whose ``ref`` carries the resolved
        CSV / cotejo URL / PDF URL and whose ``pdf_bytes`` carries
        the raw response body.

    Raises:
        SedeNavigationError: When the form drive or row click fails.
        SedeParseError: When the cotejo URL cannot be parsed for
            its CSV.
        JustificanteFetchError: When the PDF GET returns non-2xx,
            an empty body, or a non-PDF content type.
    """
    async with _open_register_page(session, settings=settings, playwright=playwright) as (
        page,
        context,
    ):
        await _drive_search(
            page,
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
        )

        row_locator = _row_locator_for_expediente(
            page,
            expediente_id=declaration.expediente_id,
        )
        ver_button = row_locator.locator(
            '.z-listcell:has-text("Ver") .z-button',
        ).first

        try:
            async with context.expect_page(
                timeout=_VER_CLICK_TIMEOUT_MS,
            ) as new_page_info:
                await ver_button.click(timeout=_FORM_INTERACTION_TIMEOUT_MS)
            cotejo_page = await new_page_info.value
        except Exception as exc:
            raise SedeNavigationError(
                f"clicking Ver for {declaration.expediente_id!r} failed: {exc}",
            ) from exc

        try:
            await cotejo_page.wait_for_load_state(
                "domcontentloaded",
                timeout=_NAVIGATION_TIMEOUT_MS,
            )
        except Exception as exc:
            raise SedeNavigationError(
                f"cotejo page did not settle for {declaration.expediente_id!r}: {exc}",
            ) from exc

        cotejo_url = cotejo_page.url
        if _COTEJO_PATH_PREFIX not in cotejo_url:
            raise SedeNavigationError(
                f"Ver button for {declaration.expediente_id!r} did not land on a "
                f"cotejo URL (final URL: {cotejo_url!r}); "
                "session likely expired mid-walk — run `aeat auth login` and retry",
            )

        csv = _extract_csv_from_url(cotejo_url)

        ref = JustificanteRef(
            csv=csv,
            expediente_id=declaration.expediente_id,
            cotejo_url=AnyHttpUrl(f"{_COTEJO_VIEW}?CSV={csv}"),
            pdf_url=AnyHttpUrl(f"{_COTEJO_DOC}?CSV={csv}"),
        )

        pdf_response = await context.request.get(str(ref.pdf_url))
        if not (200 <= pdf_response.status < 300):
            raise JustificanteFetchError(
                f"pdf fetch for CSV={csv!r} returned HTTP {pdf_response.status}",
            )
        content_type = pdf_response.headers.get("content-type", "")
        body = await pdf_response.body()
        if not body:
            raise JustificanteFetchError(f"empty PDF body for CSV={csv!r}")
        if "pdf" not in content_type.lower():
            raise JustificanteFetchError(
                f"unexpected content-type {content_type!r} for CSV={csv!r}",
            )

        from ._schema import Expediente

        sha256 = hashlib.sha256(body).hexdigest()
        return SedeCapture(
            expediente=Expediente(
                expediente_id=declaration.expediente_id,
                modelo=declaration.modelo,
                ejercicio=declaration.ejercicio,
                category_path=("Declaraciones presentadas",),
                detail_url=AnyHttpUrl(
                    f"{_LISTING_URL}?MODELO={declaration.modelo}&EJERCICIO={declaration.ejercicio}",
                ),
            ),
            ref=ref,
            pdf_bytes=body,
            pdf_sha256=sha256,
            captured_at=datetime.now(UTC),
        )


def _row_locator_for_expediente(page: Page, *, expediente_id: str):
    """Return a Playwright locator pointing at the listitem whose
    ``Expediente`` cell text equals ``expediente_id``.
    """
    return page.locator(".z-listitem").filter(
        has=page.locator(".z-listcell").filter(has_text=expediente_id),
    )


def _extract_csv_from_url(url: str) -> str:
    """Extract the ``CSV`` query parameter from a cotejo URL.

    Args:
        url: Final URL after the Ver-button click landed on
            ``/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV=<csv>``.

    Returns:
        The CSV identifier, validated against the canonical AEAT
        8-24 uppercase-alphanumeric shape.

    Raises:
        SedeParseError: When the URL does not carry a ``CSV``
            query parameter, or when the value does not match
            the canonical AEAT CSV shape.
    """
    parsed = urlsplit(url)
    qs = parse_qs(parsed.query)
    csv_values = qs.get("CSV", [])
    if not csv_values:
        raise SedeParseError(f"cotejo URL missing CSV query: {url!r}")
    if len(csv_values) > 1:
        # AEAT never repeats the CSV parameter; multiple values
        # indicate a malformed response or an attacker-crafted URL
        # smuggling extra state past the parser. Refuse rather
        # than silently picking the first value.
        raise SedeParseError(
            f"cotejo URL has {len(csv_values)} CSV values; AEAT only emits one: {url!r}",
        )
    csv = csv_values[0]
    if not _CSV_SHAPE_RE.match(csv):
        raise SedeParseError(
            f"cotejo URL CSV {csv!r} does not match AEAT shape (expected 8-24 uppercase alphanumeric chars)",
        )
    return csv


__all__ = [
    "Declaration",
    "capture_declaration",
    "shared_playwright",
    "walk_declarations_register",
]
