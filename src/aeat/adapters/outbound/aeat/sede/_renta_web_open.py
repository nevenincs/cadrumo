"""Read-only Renta WEB Open browser driver."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
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
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ..browser import BrowserError, default_browser_session_factory
from ._errors import SedeError, SedeFailureMode, SedeNavigationError, SedeParseError
from ._renta_web_open_safety import assert_click_target_safe, install_page_safety_net

_SPANISH_AMOUNT_RE = compile(r"[-+]?\d{1,3}(?:\.\d{3})*,\d{2}|[-+]?\d+(?:[.,]\d+)?")
logger = get_logger(__name__)


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
            raise RegistryValidationError(_registry_failure_message(exc)) from exc

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


async def _playwright_stage[T](
    operation: Awaitable[T],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
    timeout_is_shape_change: bool = False,
) -> T:
    try:
        return await operation
    except PlaywrightTimeoutError as exc:
        if timeout_is_shape_change:
            logger.error(
                "renta web open expected element missing failure_mode=%s stage=%s description=%s timeout_ms=%s",
                SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                stage,
                description,
                timeout_ms,
                exc_info=True,
            )
            raise SedeParseError(
                f"Renta WEB Open expected page element was not visible: {description}",
                failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                context={"stage": stage, "expected": description, "timeout_ms": timeout_ms},
                suggestion="Re-run the live oracle after checking whether AEAT changed the Renta WEB Open page shape.",
            ) from exc
        logger.error(
            "renta web open playwright stage timed out failure_mode=%s stage=%s description=%s timeout_ms=%s",
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            timeout_ms,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"Renta WEB Open browser stage timed out: {description}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "timeout_ms": timeout_ms},
        ) from exc
    except PlaywrightError as exc:
        logger.error(
            "renta web open playwright stage failed failure_mode=%s stage=%s description=%s exc_type=%s",
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"Renta WEB Open browser stage failed: {description}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "cause_type": type(exc).__name__},
        ) from exc


def _registry_failure_message(exc: BaseException) -> str:
    context = getattr(exc, "context", None)
    if not isinstance(context, Mapping) or not context:
        return str(exc)
    failure_mode = context.get("failure_mode")
    if failure_mode is None and "state" in context:
        failure_mode = f"site_health:{context['state']}"
    if failure_mode is None:
        return str(exc)
    return f"{exc} (failure_mode={failure_mode})"


def _normalize_summary_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


__all__ = [
    "RENTA_WEB_OPEN_APP_URL",
    "RentaWebOpenLivePayload",
    "RentaWebOpenSedeDriver",
    "collect_renta_web_open_observation",
    "extract_renta_web_open_summary_value",
]
