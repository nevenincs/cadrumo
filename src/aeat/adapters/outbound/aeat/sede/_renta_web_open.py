"""Read-only Renta WEB Open browser driver."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from re import compile
from typing import Any, Literal, cast

from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    RENTA_WEB_OPEN_APP_URL,
    RegistryValidationError,
    RemoteOperation,
    RentaWebOpenLivePayload,
    RentaWebOpenObservation,
    RentaWebOpenSyntheticProfile,
    parse_renta_web_open_live_payload,
)
from ..browser import BrowserError, default_browser_session_factory
from ._adapter_utils import registry_failure_message
from ._browser_stage import build_playwright_stage_runner
from ._errors import SedeError, SedeFailureMode, SedeNavigationError
from ._renta_web_open_safety import assert_click_target_safe, install_page_safety_net

_SPANISH_AMOUNT_RE = compile(r"[-+]?\d{1,3}(?:\.\d{3})*,\d{2}|[-+]?\d+(?:[.,]\d+)?")
logger = get_logger(__name__)
_playwright_stage = build_playwright_stage_runner(
    surface_label="Renta WEB Open",
    log_prefix="renta web open",
    shape_suggestion="Re-run the live oracle after checking whether AEAT changed the Renta WEB Open page shape.",
    logger=logger,
)


class RentaWebOpenSedeDriver:
    """Renta WEB Open driver backed by the central AEAT BrowserSession surface."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings

    @property
    def mode(self) -> Literal["live"]:
        return "live"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        live_payload = parse_renta_web_open_live_payload(payload)
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=live_payload.app_url),
            RemoteOperation(kind="browser_action", action="start-open-simulator"),
            RemoteOperation(kind="browser_action", action="fill-synthetic-profile"),
            RemoteOperation(kind="browser_action", action="accept-identification"),
        ]
        for label in sorted(expected):
            operations.append(RemoteOperation(kind="browser_action", action=f"scrape-summary-field:{label}"))
        operations.append(RemoteOperation(kind="browser_action", action="close-browser-context"))
        return tuple(operations)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> RentaWebOpenObservation:
        try:
            return asyncio.run(self.collect_observation_async(payload, expected=expected))
        except (SedeError, SiteHealthError, BrowserError) as exc:
            raise RegistryValidationError(registry_failure_message(exc)) from exc

    async def collect_observation_async(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> RentaWebOpenObservation:
        return await collect_renta_web_open_observation(payload, expected=expected, settings=self._settings)


async def collect_renta_web_open_observation(
    payload: bytes,
    *,
    expected: Mapping[str, object],
    settings: Settings | None = None,
) -> RentaWebOpenObservation:
    """Open the anonymous simulator, create a synthetic declaration, and scrape summary rows."""

    live_payload = parse_renta_web_open_live_payload(payload)
    browser_session = await default_browser_session_factory(settings or Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = cast(Any, await context.new_page())
        # SAFETY-CRITICAL: install dialog auto-dismiss + URL navigation guard
        # before any user interaction. The page-level safety net is the
        # outermost defense layer; click-time `assert_click_target_safe`
        # provides the inner ring.
        await install_page_safety_net(page)
        await _playwright_stage(
            page.set_viewport_size({"width": 1366, "height": 900}),
            stage="set-viewport",
            description="Renta WEB Open viewport",
            timeout_ms=live_payload.timeout_ms,
        )
        await browser_session.navigate(page, str(live_payload.app_url))
        await _playwright_stage(
            page.wait_for_load_state("networkidle", timeout=live_payload.timeout_ms),
            stage="wait-app-networkidle",
            description="Renta WEB Open network idle after app navigation",
            timeout_ms=live_payload.timeout_ms,
        )
        new_declaration = page.locator(".z-window-modal button").filter(has_text="Nueva declaración")
        await _click_expected(
            new_declaration,
            stage="start-open-simulator",
            description="Nueva declaración modal button",
            timeout_ms=live_payload.timeout_ms,
        )
        await _fill_identification_profile(page, live_payload.profile, timeout_ms=live_payload.timeout_ms)
        await _click_expected(
            page.get_by_role("button", name="Aceptar"),
            stage="accept-identification",
            description="Aceptar identification button",
            timeout_ms=live_payload.timeout_ms,
        )
        await _expect_visible(
            page.get_by_text("Resumen de declaraciones"),
            stage="wait-summary",
            description="Resumen de declaraciones heading",
            timeout_ms=live_payload.timeout_ms,
        )
        # When the payload declares casilla_overrides, navigate into the
        # editable form via the "Buscar casilla" dialog, fill each casilla
        # input with the requested value, then return to the Resumen so the
        # summary scrape below picks up the recomputed totals. Empty
        # overrides → driver stays on the baseline identification path.
        if live_payload.casilla_overrides:
            await _apply_casilla_overrides(
                page,
                live_payload.casilla_overrides,
                timeout_ms=live_payload.timeout_ms,
            )
            await _navigate_to_resumen(page, timeout_ms=live_payload.timeout_ms)
        body_text = await _playwright_stage(
            page.locator("body").inner_text(timeout=live_payload.timeout_ms),
            stage="scrape-summary-text",
            description="Renta WEB Open body text",
            timeout_ms=live_payload.timeout_ms,
        )
        values: dict[str, str] = {}
        for label in sorted(expected):
            observed = extract_renta_web_open_summary_value(body_text, label)
            if observed is not None:
                values[label] = observed
        # When the payload declares additional casillas to scrape (beyond the
        # summary labels), navigate to each via the Buscar dialog and read
        # the input value off the form page. The scraped value is recorded
        # under the casilla number key so the audit gate's casilla-id-keyed
        # coverage check resolves.
        for casilla_number in sorted(live_payload.scrape_casillas):
            scraped = await _scrape_casilla_form_value(
                page,
                casilla_number,
                timeout_ms=live_payload.timeout_ms,
            )
            if scraped is not None:
                values[casilla_number] = scraped
        return RentaWebOpenObservation(values=values, raw_evidence_locator=page.url)
    except (SedeError, SiteHealthError, BrowserError):
        raise
    except Exception as exc:
        logger.error(
            "renta web open live observation failed unexpectedly exc_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"Renta WEB Open live observation failed: {exc}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": "unknown", "cause_type": type(exc).__name__},
        ) from exc
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


def extract_renta_web_open_summary_value(body_text: str, label: str) -> str | None:
    """Extract one Spanish-formatted numeric value from Renta WEB Open summary text."""

    normalized_label = _normalize_summary_text(label)
    lines = [_normalize_summary_text(line) for line in body_text.splitlines()]
    for index, line in enumerate(lines):
        if not line:
            continue
        if line == normalized_label and index + 1 < len(lines):
            next_match = _SPANISH_AMOUNT_RE.search(lines[index + 1])
            if next_match is not None:
                return next_match.group(0)
        if line.startswith(normalized_label):
            match = _SPANISH_AMOUNT_RE.search(line[len(normalized_label) :])
            if match is not None:
                return match.group(0)
    return None


async def _navigate_to_casilla(page: Any, casilla_number: str, *, timeout_ms: int) -> None:
    """Open the Buscar casilla dialog, enter the casilla number, jump to the page.

    The Resumen view exposes a "Buscar casilla" button that opens a modal
    dialog with a 4-char "Número de casilla" input and an "Ir a la página"
    button. Typing a valid casilla number enables both the search button
    and the navigation button; clicking "Ir a la página" navigates the form
    to the page containing that casilla.
    """

    await _click_expected(
        page.get_by_role("button", name="Buscar casilla").first,
        stage=f"navigate-to-casilla:{casilla_number}:open-dialog",
        description="Buscar casilla button",
        timeout_ms=timeout_ms,
    )
    await _fill_expected(
        page.locator('input.estiloAlfanumerico[maxlength="4"]').first,
        casilla_number,
        stage=f"navigate-to-casilla:{casilla_number}:type-number",
        description="Buscar casilla number input",
        timeout_ms=timeout_ms,
    )
    await _click_expected(
        page.get_by_role("button", name="Ir a la página").first,
        stage=f"navigate-to-casilla:{casilla_number}:jump-to-page",
        description="Ir a la página button",
        timeout_ms=timeout_ms,
    )


async def _navigate_to_resumen(page: Any, *, timeout_ms: int) -> None:
    """Return to the Resumen view after editing form casillas."""

    await _click_expected(
        page.get_by_role("button", name="Resumen", exact=True).first,
        stage="navigate-to-resumen",
        description="Resumen button",
        timeout_ms=timeout_ms,
    )
    await _expect_visible(
        page.get_by_text("Resumen de declaraciones"),
        stage="navigate-to-resumen:wait-summary",
        description="Resumen de declaraciones heading",
        timeout_ms=timeout_ms,
    )


async def _apply_casilla_overrides(
    page: Any,
    overrides: Mapping[str, str],
    *,
    timeout_ms: int,
) -> None:
    """Apply each (casilla, value) override by navigating to the casilla and filling it.

    Uses the Buscar casilla dialog to jump to each casilla's page, then
    locates the input field associated with that casilla number and fills
    it with the requested value. The Renta WEB Open form pages label each
    editable input with a `title` attribute that includes the casilla
    number (e.g. ``title="0511 ..."``); the locator matches by title-prefix.
    """

    for casilla_number, value in overrides.items():
        await _navigate_to_casilla(page, casilla_number, timeout_ms=timeout_ms)
        await _fill_expected(
            page.locator(f'input[title^="{casilla_number}"]').first,
            value,
            stage=f"apply-casilla-override:{casilla_number}",
            description=f"casilla {casilla_number} input",
            timeout_ms=timeout_ms,
        )


async def _scrape_casilla_form_value(
    page: Any,
    casilla_number: str,
    *,
    timeout_ms: int,
) -> str | None:
    """Read the current value of one casilla's form input.

    Navigates to the casilla via the Buscar dialog, reads the input value,
    and returns the raw string. Returns None when the locator does not
    resolve (the casilla may be on a page that requires upstream inputs).
    """

    try:
        await _navigate_to_casilla(page, casilla_number, timeout_ms=timeout_ms)
    except SedeNavigationError:
        return None
    locator = page.locator(f'input[title^="{casilla_number}"]').first
    try:
        return cast(str, await locator.input_value(timeout=timeout_ms))
    except Exception:
        return None


async def _fill_identification_profile(page: Any, profile: RentaWebOpenSyntheticProfile, *, timeout_ms: int) -> None:
    await _fill_expected(
        page.locator('input[title="NIF:"]').first,
        profile.nif,
        stage="fill-synthetic-profile:nif",
        description="NIF input",
        timeout_ms=timeout_ms,
    )
    await _fill_expected(
        page.locator('input[title="Apellidos y nombre:"]').first,
        profile.name,
        stage="fill-synthetic-profile:name",
        description="Apellidos y nombre input",
        timeout_ms=timeout_ms,
    )
    await _select_combo_item(page, combo_index=0, item_text=profile.civil_status, timeout_ms=timeout_ms)
    await _fill_expected(
        page.locator("input.z-datebox-input").first,
        profile.birth_date,
        stage="fill-synthetic-profile:birth-date",
        description="birth date input",
        timeout_ms=timeout_ms,
    )
    await _click_expected(
        page.locator("label", has_text=profile.sex),
        stage="fill-synthetic-profile:sex",
        description="sex option label",
        timeout_ms=timeout_ms,
    )
    await _select_combo_item(page, combo_index=2, item_text=profile.autonomous_community, timeout_ms=timeout_ms)


async def _select_combo_item(page: Any, *, combo_index: int, item_text: str, timeout_ms: int) -> None:
    await _click_expected(
        page.locator("input.z-combobox-input").nth(combo_index),
        stage=f"fill-synthetic-profile:combo-{combo_index}",
        description=f"combo input {combo_index}",
        timeout_ms=timeout_ms,
    )
    await _click_expected(
        page.locator(".z-comboitem").filter(has_text=item_text).last,
        stage=f"fill-synthetic-profile:combo-{combo_index}-item",
        description=f"combo item {item_text}",
        timeout_ms=timeout_ms,
    )


async def _fill_expected(locator: Any, value: str, *, stage: str, description: str, timeout_ms: int) -> None:
    await _expect_visible(locator, stage=stage, description=description, timeout_ms=timeout_ms)
    await _playwright_stage(
        locator.fill(value, timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
    )


async def _click_expected(locator: Any, *, stage: str, description: str, timeout_ms: int) -> None:
    """Wait, safety-check, then click. Single click site for the driver — no bypass.

    The safety check (``assert_click_target_safe``) runs BEFORE the click
    is dispatched. If the locator's resolved text or href contains a
    forbidden token (Presentar / Firmar / Pagar / etc.), the click is
    refused and a :class:`SedeNavigationError` is raised. This is one of
    the belt-and-suspenders defenses; the others are the page-level dialog
    auto-dismiss + URL navigation guard installed in
    ``install_page_safety_net``.
    """
    await _expect_visible(locator, stage=stage, description=description, timeout_ms=timeout_ms)
    await assert_click_target_safe(locator, stage=stage, description=description, timeout_ms=timeout_ms)
    await _playwright_stage(
        locator.click(timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
    )


async def _expect_visible(locator: Any, *, stage: str, description: str, timeout_ms: int) -> None:
    await _playwright_stage(
        locator.wait_for(state="visible", timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )


def _normalize_summary_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


__all__ = [
    "RENTA_WEB_OPEN_APP_URL",
    "RentaWebOpenLivePayload",
    "RentaWebOpenSedeDriver",
    "collect_renta_web_open_observation",
    "extract_renta_web_open_summary_value",
]
