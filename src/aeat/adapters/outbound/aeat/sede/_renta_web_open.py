"""Read-only Renta WEB Open browser driver."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from re import compile
from typing import Any, Literal, cast

from .....core.config import Settings
from .....domain.calculations.registry import (
    RENTA_WEB_OPEN_APP_URL,
    RegistryValidationError,
    RentaWebOpenLivePayload,
    RentaWebOpenObservation,
    RentaWebOpenSyntheticProfile,
    parse_renta_web_open_live_payload,
)
from .....domain.calculations.registry._remote_state_guard import RemoteOperation
from ..browser import default_browser_session_factory
from ._errors import SedeNavigationError

_SPANISH_AMOUNT_RE = compile(r"[-+]?\d{1,3}(?:\.\d{3})*,\d{2}|[-+]?\d+(?:[.,]\d+)?")


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
        except SedeNavigationError as exc:
            raise RegistryValidationError(str(exc)) from exc

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
        await page.set_viewport_size({"width": 1366, "height": 900})
        await browser_session.navigate(page, str(live_payload.app_url))
        await page.wait_for_load_state("networkidle", timeout=live_payload.timeout_ms)
        await page.locator(".z-window-modal button").filter(has_text="Nueva declaración").click(
            timeout=live_payload.timeout_ms
        )
        await _fill_identification_profile(page, live_payload.profile, timeout_ms=live_payload.timeout_ms)
        await page.get_by_role("button", name="Aceptar").click(timeout=live_payload.timeout_ms)
        await page.get_by_text("Resumen de declaraciones").wait_for(timeout=live_payload.timeout_ms)
        body_text = await page.locator("body").inner_text(timeout=live_payload.timeout_ms)
        values: dict[str, str] = {}
        for label in sorted(expected):
            observed = extract_renta_web_open_summary_value(body_text, label)
            if observed is not None:
                values[label] = observed
        return RentaWebOpenObservation(values=values, raw_evidence_locator=page.url)
    except Exception as exc:
        raise SedeNavigationError(f"Renta WEB Open live observation failed: {exc}") from exc
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
    await page.locator('input[title="NIF:"]').first.fill(profile.nif, timeout=timeout_ms)
    await page.locator('input[title="Apellidos y nombre:"]').first.fill(profile.name, timeout=timeout_ms)
    await _select_combo_item(page, combo_index=0, item_text=profile.civil_status, timeout_ms=timeout_ms)
    await page.locator("input.z-datebox-input").first.fill(profile.birth_date, timeout=timeout_ms)
    await page.locator("label", has_text=profile.sex).click(timeout=timeout_ms)
    await _select_combo_item(page, combo_index=2, item_text=profile.autonomous_community, timeout_ms=timeout_ms)


async def _select_combo_item(page: Any, *, combo_index: int, item_text: str, timeout_ms: int) -> None:
    await page.locator("input.z-combobox-input").nth(combo_index).click(timeout=timeout_ms)
    await page.locator(".z-comboitem").filter(has_text=item_text).last.click(timeout=timeout_ms)


def _normalize_summary_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


__all__ = [
    "RENTA_WEB_OPEN_APP_URL",
    "RentaWebOpenLivePayload",
    "RentaWebOpenSedeDriver",
    "collect_renta_web_open_observation",
    "extract_renta_web_open_summary_value",
]
