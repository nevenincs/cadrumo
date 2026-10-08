"""Acquire the subsidiary census consultations through their guarded controls."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from .....application.user_profile.censal_observation import CensalConsultation
from .....core.config import Settings
from .....core.remote_authority import is_current_aeat_host
from .....domain.calculations.registry.errors import RegistryValidationError
from ._adapter_utils import assert_query_browser_action_for, assert_read_http_for
from .censal_tables import census_key, parse_censal_table
from .censal_tax_status import parse_censal_tax_status
from .errors import SedeFailureMode, SedeNavigationError

if TYPE_CHECKING:
    from playwright.async_api import Page, Route

    from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy

_PATHS = Settings.external_constants().aeat.sede_paths
CENSAL_READ_POST_PATHS = (
    _PATHS.censal_actividades_entry,
    _PATHS.censal_actividades,
    _PATHS.censal_locales,
    _PATHS.censal_situacion_tributaria,
    _PATHS.censal_obligaciones,
)
_DOCUMENT_PATHS = frozenset((_PATHS.censal_datos, *CENSAL_READ_POST_PATHS))


def _refusal(reason: str) -> SedeNavigationError:
    return SedeNavigationError(
        f"Census consultation refused: {reason}",
        failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
    )


def assert_censal_consultation_request(policy: RemoteStateGuardPolicy, method: str, url: str) -> None:
    """Refuse an unexpected document target before its request leaves the browser."""
    if urlsplit(url).path not in _DOCUMENT_PATHS:
        raise _refusal("unexpected document route")
    assert_read_http_for(policy, method, url)


@asynccontextmanager
async def _consultation_requests(page: Page, policy: RemoteStateGuardPolicy) -> AsyncIterator[None]:
    violations: list[dict[str, str]] = []

    async def guard(route: Route) -> None:
        request = route.request
        try:
            if request.is_navigation_request():
                assert_censal_consultation_request(policy, request.method, request.url)
            else:
                assert_read_http_for(policy, request.method, request.url)
        except (SedeNavigationError, RegistryValidationError):
            parts = urlsplit(request.url)
            # Third-party analytics are blocked but are not census evidence.
            # A blocked document or AEAT resource can affect the read itself.
            if request.is_navigation_request() or is_current_aeat_host(parts.hostname or ""):
                violations.append({"method": request.method, "host": parts.netloc, "path": parts.path})
            await route.abort("blockedbyclient")
        else:
            await route.fallback()

    await page.context.route("**/*", guard)
    try:
        yield
    finally:
        await page.context.unroute("**/*", guard)
        if violations:
            raise SedeNavigationError(
                "Census consultation refused: a page attempted an undeclared request",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                context={"requests": violations},
            )


async def _open_consultation(
    page: Page,
    *,
    label: str,
    action: str,
    path: str,
    policy: RemoteStateGuardPolicy,
    timeout_ms: int,
) -> Page:
    # The two form handoffs share mutable hidden state. A fresh landing before
    # each consultation was verified live; reusing the mutated form can expire.
    await page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
    assert_censal_consultation_request(policy, "GET", page.url)
    if urlsplit(page.url).path != _PATHS.censal_datos:
        raise _refusal("census landing changed before consultation")
    control = page.get_by_text(label, exact=True)
    if await control.count() != 1:
        raise _refusal("consultation control is missing or ambiguous")
    assert_query_browser_action_for(policy, action)
    async with page.expect_popup(timeout=timeout_ms) as opened:
        await control.click(timeout=timeout_ms)
    popup = await opened.value
    try:
        await popup.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        assert_censal_consultation_request(policy, "GET", popup.url)
        if urlsplit(popup.url).path != path:
            raise _refusal("consultation landed on a different service")
    except BaseException:
        await popup.close()
        raise
    return popup


async def _premises(
    landing: Page,
    activities: Page,
    *,
    observation: CensalConsultation,
    policy: RemoteStateGuardPolicy,
    timeout_ms: int,
) -> tuple[CensalConsultation, ...]:
    count = await activities.get_by_role("link", name="Locales", exact=True).count()
    parent_indices = tuple(
        index
        for index, row in enumerate(row for section in observation.sections for row in section.rows)
        if any(census_key(cell.column or "") == "locales" and cell.text for cell in row.cells)
    )
    if len(parent_indices) != count:
        raise _refusal("premises controls do not match activity records")
    result: list[CensalConsultation] = []
    for index in range(count):
        current = (
            activities
            if index == 0
            else await _open_consultation(
                landing,
                label="Mis Actividades Económicas",
                action="censal-consult-actividades",
                path=_PATHS.censal_actividades,
                policy=policy,
                timeout_ms=timeout_ms,
            )
        )
        try:
            if (
                index
                and parse_censal_table(await current.content(), kind="actividades", source_url=current.url).sections
                != observation.sections
            ):
                raise _refusal("activities changed while reading their premises")
            assert_query_browser_action_for(policy, "censal-consult-locales")
            async with current.expect_navigation(wait_until="domcontentloaded", timeout=timeout_ms):
                await current.get_by_role("link", name="Locales", exact=True).nth(index).click(timeout=timeout_ms)
            assert_censal_consultation_request(policy, "GET", current.url)
            if urlsplit(current.url).path != _PATHS.censal_locales:
                raise _refusal("premises consultation landed on a different service")
            result.append(
                parse_censal_table(await current.content(), kind="locales", source_url=current.url).model_copy(
                    update={"activity_row_index": parent_indices[index]}
                )
            )
        finally:
            if current is not activities:
                await current.close()
    return tuple(result)


async def capture_censal_consultations(
    page: Page, *, policy: RemoteStateGuardPolicy, settings: Settings
) -> tuple[CensalConsultation, ...]:
    """Return every required consultation or fail the pull without partial success."""
    timeout_ms = settings.cadrumo_browser_navigation_timeout_ms
    specifications: tuple[tuple[Literal["actividades", "obligaciones", "situacion_tributaria"], str, str, str], ...] = (
        ("actividades", "Mis Actividades Económicas", "censal-consult-actividades", _PATHS.censal_actividades),
        (
            "situacion_tributaria",
            "Mi Situación Tributaria",
            "censal-consult-situacion-tributaria",
            _PATHS.censal_situacion_tributaria,
        ),
        ("obligaciones", "Mis Obligaciones", "censal-consult-obligaciones", _PATHS.censal_obligaciones),
    )
    result: list[CensalConsultation] = []
    async with _consultation_requests(page, policy):
        for kind, label, action, path in specifications:
            popup = await _open_consultation(
                page, label=label, action=action, path=path, policy=policy, timeout_ms=timeout_ms
            )
            try:
                html = await popup.content()
                result.append(
                    parse_censal_tax_status(html, source_url=popup.url)
                    if kind == "situacion_tributaria"
                    else parse_censal_table(html, kind=kind, source_url=popup.url)
                )
                if kind == "actividades":
                    result.extend(
                        await _premises(page, popup, observation=result[-1], policy=policy, timeout_ms=timeout_ms)
                    )
            finally:
                await popup.close()
    return tuple(result)
