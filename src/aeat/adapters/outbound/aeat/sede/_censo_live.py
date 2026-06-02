"""Authenticated G313 (Mis Datos Censales) fetch driver.

Mirrors :mod:`_notifications` and :mod:`_declarations`: takes an
authenticated :class:`AeatSession`, drives Playwright to the G313
launcher, captures the page HTML, and runs the existing
:func:`._censo.parse_g313_html` parser to lift the response into a
typed :class:`CensoFactSet`.

The launcher procedure URL is the documented G313 entry point from
``external_constants.toml``. The session's storage state carries the
AEAT cookies acquired via certificate or Cl@ve Móvil, so the launcher
redirects directly to the Mis Datos Censales data page instead of
bouncing through the login surface. If the session is not valid for
the operator's NIF (e.g. certificate not registered against the censo),
the page returns AEAT's standard auth-gate error shape and the parser
returns a :class:`CensoFactSet` with no fields populated — the caller
decides whether that is a refusal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

from .....core.config import Settings
from .....core.decimal import format_decimal
from .....core.i18n import tr
from .....core.logging import get_logger
from .._playwright import PlaywrightError
from ..browser import default_browser_session_factory
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._censo import CensoFactSet, parse_g313_html
from ._errors import SedeFailureMode, SedeNavigationError

if TYPE_CHECKING:
    from ..auth._authenticator import AeatSession


BrowserSessionFactory = Callable[[Settings], Awaitable[Any]]
"""Async factory returning an object exposing ``create_context(storage_state=...)`` + ``close()``.

Real production code uses :func:`default_browser_session_factory`; tests
inject a recording double via the same protocol so the storage-state
plumbing can be exercised without a real Playwright browser."""


log = get_logger(__name__)


_EXTERNAL = Settings.external_constants()
G313_LAUNCHER_URL = f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.sede_paths.censo_g313_launcher}"
"""AEAT-published entry point for *Mis Datos Censales* (the read-only
operator-facing projection of the operator's 036 censo record)."""


async def fetch_g313_censo(
    session: AeatSession,
    *,
    settings: Settings | None = None,
) -> CensoFactSet:
    """Live-fetch the G313 page under the authenticated session.

    Args:
        session: An authenticated :class:`AeatSession` whose storage
            state carries valid AEAT cookies.
        settings: Optional :class:`Settings` override.

    Returns:
        A :class:`CensoFactSet` parsed from the live HTML. May be
        empty (every field ``None``) when AEAT publishes no censo
        for the operator's NIF — the caller (CensoSyncService) raises
        :class:`CensoNotAvailableError` on that path.

    Raises:
        SedeNavigationError: when the session has no persisted browser
            state or the navigation itself fails.
    """
    settings = settings or Settings()
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth configure` to acquire one",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    storage_state = storage_state_for_session(session)
    return await _fetch_g313_censo_with_storage_state(
        storage_state,
        settings=settings,
        browser_session_factory=default_browser_session_factory,
    )


async def _fetch_g313_censo_with_storage_state(
    storage_state: Mapping[str, object],
    *,
    settings: Settings,
    browser_session_factory: BrowserSessionFactory,
) -> CensoFactSet:
    """Storage-state-driven core of :func:`fetch_g313_censo`.

    Split out so unit tests can drive the Playwright orchestration
    with a recording double — the public :func:`fetch_g313_censo`
    derives ``storage_state`` from an :class:`AeatSession` then
    delegates here.

    Args:
        storage_state: Playwright ``storage_state`` payload carrying
            the AEAT cookies acquired via certificate or Cl@ve Móvil.
        settings: Resolved :class:`Settings` instance.
        browser_session_factory: Async factory returning a browser
            session exposing ``create_context(storage_state=...)`` and
            ``close()``. Production passes
            :func:`default_browser_session_factory`; tests inject a
            recording double via the same protocol.

    Returns:
        A :class:`CensoFactSet` parsed from the navigated G313 page.

    Raises:
        SedeNavigationError: when the goto itself fails.
    """
    browser_session = await browser_session_factory(settings)
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            try:
                await page.goto(G313_LAUNCHER_URL, wait_until=_WAIT_DOMCONTENTLOADED)
            except PlaywrightError as exc:
                raise SedeNavigationError(
                    f"goto {G313_LAUNCHER_URL!r} failed: {exc}",
                    failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                ) from exc
            html = await page.content()
            fact_set = parse_g313_html(html)
            log.info(
                "fetch_g313_censo: parsed %d fields from %s",
                _populated_count(fact_set),
                G313_LAUNCHER_URL,
            )
            return fact_set
        finally:
            try:
                await context.close()
            except Exception as exc:
                log.debug("fetch_g313_censo: context.close suppressed: %s", exc, exc_info=True)
    finally:
        await browser_session.close()


def censo_fact_set_to_mapping(fact_set: CensoFactSet) -> Mapping[str, str]:
    """Project a :class:`CensoFactSet` into the dotted-key mapping the snapshot store accepts.

    Mirrors the ``model_selectors`` declarations in the schema so
    the snapshot path keys stay aligned with the user-profile schema
    paths the comparison verb walks against.
    """
    pairs: list[tuple[str, str]] = []
    if fact_set.fiscal_address_cadastral_reference is not None:
        pairs.append(
            ("address.cadastral_reference", fact_set.fiscal_address_cadastral_reference),
        )
    if fact_set.fiscal_address_is_habitual_vivienda is not None:
        pairs.append(
            (
                "address.is_habitual_vivienda",
                "true" if fact_set.fiscal_address_is_habitual_vivienda else "false",
            ),
        )
    if fact_set.activity_start_date is not None:
        pairs.append(("censo.activity_start_date", fact_set.activity_start_date.isoformat()))
    if fact_set.activity_end_date is not None:
        pairs.append(("censo.activity_end_date", fact_set.activity_end_date.isoformat()))
    if fact_set.establecimiento_type is not None:
        pairs.append(("censo.establecimiento_type", fact_set.establecimiento_type))
    if fact_set.elected_withholding_pct is not None:
        pairs.append(("censo.elected_withholding_pct", fact_set.elected_withholding_pct))
    if fact_set.vivienda_office_total_m2 is not None:
        _m2_text = format_decimal(fact_set.vivienda_office_total_m2, normalize=True)
        pairs.append(("vivienda_office.total_m2", _m2_text if "." in _m2_text else f"{_m2_text}.00"))
    if fact_set.vivienda_office_office_m2 is not None:
        _m2_text = format_decimal(fact_set.vivienda_office_office_m2, normalize=True)
        pairs.append(("vivienda_office.office_m2", _m2_text if "." in _m2_text else f"{_m2_text}.00"))
    if fact_set.iae_epigraph is not None:
        pairs.append(("activities.iae_epigraph", fact_set.iae_epigraph))
    return dict(pairs)


def _populated_count(fact_set: CensoFactSet) -> int:
    return sum(
        1
        for value in (
            fact_set.fiscal_address_cadastral_reference,
            fact_set.fiscal_address_is_habitual_vivienda,
            fact_set.activity_start_date,
            fact_set.activity_end_date,
            fact_set.establecimiento_type,
            fact_set.elected_withholding_pct,
            fact_set.vivienda_office_total_m2,
            fact_set.vivienda_office_office_m2,
            fact_set.iae_epigraph,
        )
        if value is not None
    )


__all__ = [
    "G313_LAUNCHER_URL",
    "censo_fact_set_to_mapping",
    "fetch_g313_censo",
]
