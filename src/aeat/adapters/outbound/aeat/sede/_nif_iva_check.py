"""Read-only AEAT NIF-IVA / VIES proxy browser driver.

Drives the public AEAT-hosted form servlet that proxies non-Spanish EU
VAT-identifier validity queries to the European Commission's VIES
service. The driver navigates from the sede gestiones page (which
issues the session cookies the form servlet requires) to the form
servlet itself, fills the country-code + VAT-number form per declared
NIF, scrapes the rendered validity verdict, and returns one
observation per declared NIF.

The contract mirrors :mod:`_renta_web_open`: a sibling sede adapter
exposing an async ``collect`` coroutine plus a synchronous wrapper
that the registry oracle can call. Browser-session lifecycle and
error mapping are fully implemented; the form-specific Playwright
selectors are explicit ``raise NotImplementedError`` stubs that must
be replaced once the form HTML has been captured live (the servlet
returns an error page when reached without sede session cookies, so
the selectors cannot be scraped statically).

The driver is intentionally read-only: the form mutates no AEAT-side
state under any NIF, requires no clave-móvil session, and writes
nothing to the autonomo's filing history. The remote-state guard
host-pinning suffix (``agenciatributaria.gob.es``) covers both the
sede entry subdomain and the www1 form-servlet subdomain.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.logging import get_logger
from .....domain.calculations.registry._aeat_nif_iva_oracle import (
    AEAT_NIF_IVA_ENTRY_URL,
    AEAT_NIF_IVA_VERIFICATION_URL,
)
from .....domain.calculations.registry._errors import RegistryValidationError
from .....domain.calculations.registry._remote_state_guard import RemoteOperation
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ..browser import BrowserError, default_browser_session_factory
from ._errors import SedeError, SedeFailureMode, SedeNavigationError, SedeParseError

logger = get_logger(__name__)

# Default timeout per Playwright stage (milliseconds). Each navigation +
# form-fill + result-scrape stage gets this budget; the live driver runs
# under the remote-state guard's pre-flighted operation list and the
# total wall-clock budget is governed by the caller.
DEFAULT_NIF_IVA_TIMEOUT_MS: int = 30_000


class NifIvaCheckObservation(BaseModel):
    """One observation emitted per declared NIF after live navigation.

    ``verdict`` is the AEAT/VIES-rendered validity for that NIF:
    ``valid``, ``invalid``, or ``unknown`` when the response is
    structurally unanswerable (network error mid-query, etc.).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    nif: str = Field(min_length=1, max_length=32)
    verdict: Literal["valid", "invalid", "unknown"]
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class NifIvaCheckResult(BaseModel):
    """Aggregate live-driver result across every declared NIF."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observations: tuple[NifIvaCheckObservation, ...] = ()


class NifIvaCheckSedeDriver:
    """Live AEAT NIF-IVA driver backed by the central BrowserSession surface.

    The driver follows the sequence the oracle's ``planned_operations``
    enumerates: GET sede entry, GET form servlet, open the form,
    per-NIF check, discard the session.

    Selector-bearing helpers (``_open_nif_iva_form``,
    ``_check_single_nif``, ``_extract_verdict``) raise
    ``NotImplementedError`` until the form HTML has been captured live
    and the actual selectors are filled in. The lifecycle, navigation,
    error mapping, and per-NIF iteration are complete.
    """

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
        del payload
        if not expected:
            raise RegistryValidationError("NifIvaCheckSedeDriver.planned_operations requires at least one expected NIF")
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_ENTRY_URL),
            RemoteOperation(kind="http", method="GET", url=AEAT_NIF_IVA_VERIFICATION_URL),
            RemoteOperation(kind="browser_action", action="open-nif-iva-form"),
        ]
        for nif in sorted(str(key) for key in expected):
            operations.append(RemoteOperation(kind="browser_action", action=f"check-nif-{nif}"))
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    def collect(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_NIF_IVA_TIMEOUT_MS,
    ) -> NifIvaCheckResult:
        try:
            return asyncio.run(self.collect_async(payload, expected=expected, timeout_ms=timeout_ms))
        except (SedeError, SiteHealthError, BrowserError) as exc:
            raise RegistryValidationError(_registry_failure_message(exc)) from exc

    async def collect_async(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_NIF_IVA_TIMEOUT_MS,
    ) -> NifIvaCheckResult:
        return await collect_nif_iva_check_observations(
            payload,
            expected=expected,
            settings=self._settings,
            timeout_ms=timeout_ms,
        )


async def collect_nif_iva_check_observations(
    payload: bytes,
    *,
    expected: Mapping[str, object],
    settings: Settings | None = None,
    timeout_ms: int = DEFAULT_NIF_IVA_TIMEOUT_MS,
) -> NifIvaCheckResult:
    """Open the NIF-IVA form, query each declared NIF, scrape the verdicts.

    The function navigates the AEAT sede gestiones entry, follows
    through to the form servlet (which the entry's session cookies
    authorise), iterates the declared NIFs alphabetically, and returns
    one observation per NIF.
    """

    del payload
    if not expected:
        raise RegistryValidationError("collect_nif_iva_check_observations requires at least one expected NIF")
    nifs = tuple(sorted(str(key) for key in expected))

    browser_session = await default_browser_session_factory(settings or Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
        page = cast(Any, await context.new_page())
        await _playwright_stage(
            page.set_viewport_size({"width": 1366, "height": 900}),
            stage="set-viewport",
            description="NIF-IVA viewport",
            timeout_ms=timeout_ms,
        )

        # Sede entry: acquire the session cookies the form servlet requires.
        await browser_session.navigate(page, str(AEAT_NIF_IVA_ENTRY_URL))
        await _playwright_stage(
            page.wait_for_load_state("networkidle", timeout=timeout_ms),
            stage="wait-entry-networkidle",
            description="NIF-IVA sede entry network idle",
            timeout_ms=timeout_ms,
        )

        # Form servlet: now reachable with sede cookies set.
        await browser_session.navigate(page, str(AEAT_NIF_IVA_VERIFICATION_URL))
        await _playwright_stage(
            page.wait_for_load_state("networkidle", timeout=timeout_ms),
            stage="wait-form-networkidle",
            description="NIF-IVA form servlet network idle",
            timeout_ms=timeout_ms,
        )
        await _open_nif_iva_form(page, timeout_ms=timeout_ms)

        observations: list[NifIvaCheckObservation] = []
        for nif in nifs:
            verdict = await _check_single_nif(page, nif=nif, timeout_ms=timeout_ms)
            observations.append(NifIvaCheckObservation(nif=nif, verdict=verdict, raw_evidence_locator=page.url))

        return NifIvaCheckResult(observations=tuple(observations))
    except (SedeError, SiteHealthError, BrowserError):
        raise
    except Exception as exc:
        logger.error(
            "nif iva check live observation failed unexpectedly exc_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"NIF-IVA live observation failed: {exc}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": "unknown", "cause_type": type(exc).__name__},
        ) from exc
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


async def _open_nif_iva_form(page: Any, *, timeout_ms: int) -> None:
    """Wait for the form to become interactive (country dropdown + VAT input visible).

    The form's actual selectors are unknown until the servlet's HTML
    is captured live (the servlet redirects to a sede error page when
    reached without sede session cookies, so static scraping fails).
    Replace this stub once the selectors land.
    """

    del page, timeout_ms
    raise NotImplementedError(
        "NIF-IVA form selectors not yet captured. Live-navigate to "
        f"{AEAT_NIF_IVA_VERIFICATION_URL} (after acquiring session cookies via "
        f"{AEAT_NIF_IVA_ENTRY_URL}) and capture the country-code dropdown / "
        "VAT-number input / submit button selectors. Replace this stub with "
        "page.locator(...) wait_for visible calls keyed off those selectors."
    )


async def _check_single_nif(
    page: Any,
    *,
    nif: str,
    timeout_ms: int,
) -> Literal["valid", "invalid", "unknown"]:
    """Submit one NIF query and scrape the rendered verdict.

    Same selector-capture caveat as ``_open_nif_iva_form``.
    """

    del page, nif, timeout_ms
    raise NotImplementedError(
        "NIF-IVA per-NIF query selectors not yet captured. Once the form HTML "
        "has been captured live, this stub must (1) parse the country code "
        "prefix from the NIF (first two letters per VIES convention), (2) "
        "select that country in the form's country dropdown, (3) fill the "
        "remaining VAT-number digits in the form's VAT-number input, (4) click "
        "submit, (5) wait for the response panel to render, (6) parse the "
        "rendered verdict ('válido' / 'no válido' / unknown) and return the "
        "matching Literal value."
    )


def extract_verdict_from_response_text(body_text: str) -> Literal["valid", "invalid", "unknown"]:
    """Parse the AEAT-rendered verdict from response body text.

    The actual response shape (Spanish phrases, surrounding chrome) is
    not yet captured. This pure function is implementable once a real
    response sample is in hand; until then it returns ``unknown`` for
    every input as a fail-safe.
    """

    del body_text
    return "unknown"


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
                "nif iva expected element missing failure_mode=%s stage=%s description=%s timeout_ms=%s",
                SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                stage,
                description,
                timeout_ms,
                exc_info=True,
            )
            raise SedeParseError(
                f"NIF-IVA expected page element was not visible: {description}",
                failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                context={"stage": stage, "expected": description, "timeout_ms": timeout_ms},
                suggestion="Re-run the live oracle after checking whether AEAT changed the NIF-IVA form shape.",
            ) from exc
        logger.error(
            "nif iva playwright stage timed out failure_mode=%s stage=%s description=%s timeout_ms=%s",
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            timeout_ms,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"NIF-IVA browser stage timed out: {description}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": stage, "description": description, "timeout_ms": timeout_ms},
        ) from exc
    except PlaywrightError as exc:
        logger.error(
            "nif iva playwright stage failed failure_mode=%s stage=%s description=%s exc_type=%s",
            SedeFailureMode.LIVE_NAVIGATION_FAILED,
            stage,
            description,
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"NIF-IVA browser stage failed: {description}",
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


__all__ = [
    "AEAT_NIF_IVA_ENTRY_URL",
    "AEAT_NIF_IVA_VERIFICATION_URL",
    "DEFAULT_NIF_IVA_TIMEOUT_MS",
    "NifIvaCheckObservation",
    "NifIvaCheckResult",
    "NifIvaCheckSedeDriver",
    "collect_nif_iva_check_observations",
    "extract_verdict_from_response_text",
]
