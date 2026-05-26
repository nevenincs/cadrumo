"""AEAT GROI Spanish-ROI consult browser driver.

Drives the public AEAT-hosted GROI servlet that confirms whether a
given Spanish NIF is registered as an intra-community operator
(``Registro de Operadores Intracomunitarios``). The form accepts a
single 9-character Spanish NIF, posts to the same servlet path, and
renders a verdict text such as ``CONSTA UN OPERADOR INTRACOMUNITARIO``
(registered) or ``no es un NIF válido`` (input-format error).

This adapter is the SPANISH-counterparty sibling of the IXVI
``_nif_iva_check`` adapter (foreign-EU VIES proxy). Live probing on
2026-05-07 confirmed:

- The GROI servlet at www2 is reachable under cl@ve-movil auth.
- The IXVI servlet at www1 requires a stricter auth tier than
  cl@ve-movil and is currently blocked.

The two surfaces serve different verification needs:

- **GROI** (this adapter): "is this Spanish NIF registered as an
  intra-community operator in Spain?" — used to confirm Spanish
  counterparties on modelo 349 are ROI-registered.
- **IXVI** (``_nif_iva_check``): "is this foreign EU VAT-ID valid
  per VIES?" — used to confirm foreign EU counterparties on modelo
  349 hold a valid VAT identifier.

The driver reaches the form servlet directly via authenticated
BrowserSession (caller is responsible for loading the cl@ve-movil /
certificate storage state). Form selectors are verified against
captured live HTML (form action ``ConsultaOperadorSedeGroiServlet``;
input ``id=nif name=nif maxlength=9``; submit ``id=enviar
name=enviar``); verdict markers are derived from real AEAT response
samples captured 2026-05-07.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page, ViewportSize

from pydantic import BaseModel, ConfigDict, Field

from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.i18n import tr
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    GroiObservation,
    RegistryValidationError,
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .....domain.calculations.registry._groi_oracle import AEAT_GROI_URL
from ..browser import BrowserError, default_browser_session_factory
from ._adapter_utils import (
    first_visible_locator,
    normalize_response_text,
    registry_failure_message,
)
from ._browser_stage import build_playwright_stage_runner
from ._errors import SedeError, SedeFailureMode, SedeNavigationError, SedeParseError

logger = get_logger(__name__)
_EXTERNAL = Settings.external_constants()
_GROI_HOST = urlsplit(str(AEAT_GROI_URL)).netloc

_TIMEOUT_DEFAULTS = Settings()
DEFAULT_GROI_TIMEOUT_MS: int = _TIMEOUT_DEFAULTS.aeat_browser_navigation_timeout_ms
_SELECTOR_PROBE_TIMEOUT_MS: int = _TIMEOUT_DEFAULTS.aeat_browser_selector_probe_timeout_ms
_DEFAULT_VIEWPORT: ViewportSize = {
    "width": _TIMEOUT_DEFAULTS.aeat_browser_viewport_width,
    "height": _TIMEOUT_DEFAULTS.aeat_browser_viewport_height,
}

# Form selectors verified against live HTML capture (2026-05-07):
# ``<input id="nif" name="nif" type="text" maxlength="9" size="9">``
# ``<input id="enviar" name="enviar" type="submit" value="Enviar">``.
_NIF_INPUT_SELECTORS: tuple[str, ...] = (
    "input#nif",
    'input[name="nif"]',
)
_SUBMIT_SELECTORS: tuple[str, ...] = (
    "input#enviar",
    'input[name="enviar"]',
    'input[type="submit"][value="Enviar"]',
)

_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-groi-direct-driver-read",
    evidence_tier="executable_parity_evidence",
    classification="integration_test_service",
    allowed_hosts=(_GROI_HOST,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.consult_oracle_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=False,
)


def _assert_query_browser_action(action: str) -> None:
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="browser_action", action=action),
    )


def _groi_shape_suggestion() -> str:
    return tr("adapters.aeat.sede.groi.suggestions.shape_change")


_playwright_stage = build_playwright_stage_runner(
    surface_label="GROI",
    log_prefix="groi",
    shape_suggestion=_groi_shape_suggestion(),
    logger=logger,
)


async def _locate(
    page: Page,
    selectors: tuple[str, ...],
    *,
    stage: str,
    description: str,
    timeout_ms: int,
) -> Locator:
    return await first_visible_locator(
        page,
        selectors,
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
        probe_timeout_ms=_SELECTOR_PROBE_TIMEOUT_MS,
        surface_label="GROI",
        shape_suggestion=_groi_shape_suggestion(),
    )


class GroiNifVerdict(BaseModel):
    """One observation per declared Spanish NIF after live navigation.

    ``verdict`` is the AEAT-rendered ROI-registration status: ``valid``
    when AEAT reports the NIF as a registered intra-community operator,
    ``invalid`` when AEAT either says the NIF is unregistered or that
    the input format is malformed, ``unknown`` when the response text
    is structurally unanswerable.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    nif: str = Field(min_length=1, max_length=32)
    verdict: Literal["valid", "invalid", "unknown"]
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class GroiResult(BaseModel):
    """Aggregate live-driver result across every declared Spanish NIF."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    observations: tuple[GroiNifVerdict, ...] = ()


class GroiSedeDriver:
    """Live AEAT GROI driver backed by the central BrowserSession surface.

    The driver navigates directly to the form servlet (the surface is
    reachable post cl@ve-movil auth without an intermediate sede entry
    page) and queries each declared NIF in alphabetical order. Verdict
    parsing keys off the AEAT certification phrases captured live.
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
            raise RegistryValidationError("GroiSedeDriver.planned_operations requires at least one expected NIF")
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=AEAT_GROI_URL),
            RemoteOperation(kind="browser_action", action="open-groi-form"),
        ]
        # Normalise to match GroiOracle._expected_values so the operation
        # labels the guard pre-flight sees (driverless oracle path) match
        # what the live driver emits.
        for nif in sorted(str(key).strip().upper() for key in expected):
            operations.append(RemoteOperation(kind="browser_action", action=f"check-nif-{nif}"))
        operations.append(RemoteOperation(kind="browser_action", action="discard-session"))
        return tuple(operations)

    def collect(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_GROI_TIMEOUT_MS,
    ) -> GroiResult:
        try:
            return asyncio.run(self.collect_async(payload, expected=expected, timeout_ms=timeout_ms))
        except (SedeError, SiteHealthError, BrowserError) as exc:
            raise RegistryValidationError(registry_failure_message(exc)) from exc

    async def collect_async(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_GROI_TIMEOUT_MS,
    ) -> GroiResult:
        return await collect_groi_observations(
            payload,
            expected=expected,
            settings=self._settings,
            timeout_ms=timeout_ms,
        )

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> GroiObservation:
        """Adapt the per-NIF result tuple into the registry-Protocol observation shape.

        Drives the live GROI form via :meth:`collect`, then collapses the
        per-NIF observations into a flat ``{nif: verdict}`` mapping that
        the GROI oracle wrapper compares against the caller's expected
        verdicts.
        """

        result = self.collect(payload, expected=expected)
        values: dict[str, str] = {
            observation.nif.upper(): str(observation.verdict) for observation in result.observations
        }
        evidence_locator: str | None = None
        if result.observations:
            evidence_locator = result.observations[0].raw_evidence_locator
        return GroiObservation(values=values, raw_evidence_locator=evidence_locator)


async def collect_groi_observations(
    payload: bytes,
    *,
    expected: Mapping[str, object],
    settings: Settings | None = None,
    timeout_ms: int = DEFAULT_GROI_TIMEOUT_MS,
) -> GroiResult:
    """Drive the GROI form per declared NIF and return one observation each."""

    del payload
    if not expected:
        raise RegistryValidationError("collect_groi_observations requires at least one expected NIF")
    nifs = tuple(sorted(str(key) for key in expected))

    browser_session = await default_browser_session_factory(settings or Settings())
    context = None
    try:
        context = await browser_session.create_context()
        from playwright.async_api import Page as _Page

        _raw_page = await context.new_page()
        if not isinstance(_raw_page, _Page):
            raise TypeError(f"BrowserContext.new_page() did not return a Playwright Page; got {type(_raw_page)}")
        page: _Page = _raw_page
        await _playwright_stage(
            page.set_viewport_size(_DEFAULT_VIEWPORT),
            stage="set-viewport",
            description="GROI viewport",
            timeout_ms=timeout_ms,
        )

        observations: list[GroiNifVerdict] = []
        for nif in nifs:
            # The GROI servlet renders a fresh form on each GET; navigate per
            # NIF so each query starts clean and the response page is the
            # only DOM the verdict parser sees.
            await browser_session.navigate(page, str(AEAT_GROI_URL))
            await _playwright_stage(
                page.wait_for_load_state("networkidle", timeout=timeout_ms),
                stage="wait-form-networkidle",
                description="GROI form network idle",
                timeout_ms=timeout_ms,
            )
            await _open_groi_form(page, timeout_ms=timeout_ms)
            verdict = await _check_single_nif(page, nif=nif, timeout_ms=timeout_ms)
            observations.append(GroiNifVerdict(nif=nif, verdict=verdict, raw_evidence_locator=page.url))

        return GroiResult(observations=tuple(observations))
    except (SedeError, SiteHealthError, BrowserError):
        raise
    except Exception as exc:
        logger.error(
            "groi check live observation failed unexpectedly exc_type=%s",
            type(exc).__name__,
            exc_info=True,
        )
        raise SedeNavigationError(
            f"GROI live observation failed: {exc}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"stage": "unknown", "cause_type": type(exc).__name__},
        ) from exc
    finally:
        if context is not None:
            await context.close()
        await browser_session.close()


async def _open_groi_form(page: Page, *, timeout_ms: int) -> None:
    """Wait for the NIF input + submit button + verify the form's action URL.

    Read-only mandate: before any submit click runs, this check confirms
    the form's ``action`` attribute still points at the expected
    ``ConsultaOperadorSedeGroiServlet`` consult endpoint. If AEAT silently
    retargeted the form to a different action (e.g., a write endpoint
    masquerading under the same URL), the driver refuses to submit.
    """

    _assert_query_browser_action("open-groi-form")
    await _locate(
        page,
        _NIF_INPUT_SELECTORS,
        stage="open-groi-form:nif",
        description="GROI NIF input",
        timeout_ms=timeout_ms,
    )
    await _locate(
        page,
        _SUBMIT_SELECTORS,
        stage="open-groi-form:submit",
        description="GROI submit button",
        timeout_ms=timeout_ms,
    )
    await _assert_form_action_is_consult_endpoint(page, timeout_ms=timeout_ms)


# The form's ``action`` attribute is captured live as the relative path
# ``ConsultaOperadorSedeGroiServlet`` (relative to the page's www2 host).
# Any deviation indicates AEAT changed the form's submission target and
# the driver must refuse to submit until the change is investigated.
_EXPECTED_FORM_ACTION = "ConsultaOperadorSedeGroiServlet"


async def _assert_form_action_is_consult_endpoint(page: Page, *, timeout_ms: int) -> None:
    form = page.locator("form").first
    action = await _playwright_stage(
        form.get_attribute("action", timeout=timeout_ms),
        stage="open-groi-form:assert-action",
        description="GROI form action attribute",
        timeout_ms=timeout_ms,
    )
    if action != _EXPECTED_FORM_ACTION:
        raise SedeParseError(
            f"GROI form action drift detected: expected {_EXPECTED_FORM_ACTION!r}, got {action!r}",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={
                "stage": "open-groi-form:assert-action",
                "expected_action": _EXPECTED_FORM_ACTION,
                "observed_action": action or "<missing>",
            },
            suggestion=(
                "AEAT changed the GROI form's submission target. The driver "
                "refuses to submit until the change is investigated and the "
                "expected action constant is updated. This is the read-only "
                "mandate's last line of defense before a click would post to "
                "the new (potentially state-modifying) endpoint."
            ),
        )


async def _check_single_nif(
    page: Page,
    *,
    nif: str,
    timeout_ms: int,
) -> Literal["valid", "invalid", "unknown"]:
    """Fill the form with one NIF, submit, scrape the rendered verdict."""

    _assert_query_browser_action(f"check-nif-{nif}")
    nif_input = await _locate(
        page,
        _NIF_INPUT_SELECTORS,
        stage=f"check-nif-{nif}:nif",
        description="GROI NIF input",
        timeout_ms=timeout_ms,
    )
    await _playwright_stage(
        nif_input.fill(nif, timeout=timeout_ms),
        stage=f"check-nif-{nif}:fill",
        description="GROI NIF input fill",
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )
    submit = await _locate(
        page,
        _SUBMIT_SELECTORS,
        stage=f"check-nif-{nif}:submit",
        description="GROI submit button",
        timeout_ms=timeout_ms,
    )
    await _playwright_stage(
        submit.click(timeout=timeout_ms),
        stage=f"check-nif-{nif}:click",
        description="GROI submit click",
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )
    await _playwright_stage(
        page.wait_for_load_state("networkidle", timeout=timeout_ms),
        stage=f"check-nif-{nif}:wait-response",
        description="GROI response network idle",
        timeout_ms=timeout_ms,
    )
    body_text = await _playwright_stage(
        page.locator("body").inner_text(timeout=timeout_ms),
        stage=f"check-nif-{nif}:scrape-body",
        description="GROI response body text",
        timeout_ms=timeout_ms,
    )
    return extract_verdict_from_response_text(body_text)


def extract_verdict_from_response_text(body_text: str) -> Literal["valid", "invalid", "unknown"]:
    """Parse the AEAT GROI verdict from the response body text.

    Markers verified against live AEAT response samples captured
    2026-05-07. Negative markers are checked first so explicit
    rejection cannot be misclassified by a generic positive token.
    """

    normalized = normalize_response_text(body_text)
    if not normalized:
        return "unknown"
    negative_markers = (
        "no consta",
        "no es un nif valido",
        "el campo nif no es un nif valido",
        "operador no identificado",
        "no se encuentra identificado",
        "no esta identificado",
    )
    if any(marker in normalized for marker in negative_markers):
        return "invalid"
    positive_markers = (
        "consta un operador intracomunitario",
        "consta como operador intracomunitario",
        "operador intracomunitario identificado",
    )
    if any(marker in normalized for marker in positive_markers):
        return "valid"
    return "unknown"


__all__ = [
    "DEFAULT_GROI_TIMEOUT_MS",
    "GroiNifVerdict",
    "GroiResult",
    "GroiSedeDriver",
    "collect_groi_observations",
    "extract_verdict_from_response_text",
]
