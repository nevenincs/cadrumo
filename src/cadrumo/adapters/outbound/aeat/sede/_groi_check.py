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
- **IXVI** (``_nif_iva_check``): "is this foreign EU IVA-ID valid
  per VIES?" — used to confirm foreign EU counterparties on modelo
  349 hold a valid IVA identifier.

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
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from playwright.async_api import Page

from pydantic import AnyUrl, Field

from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    CheckerObservation,
    RegistryValidationError,
    RemoteOperation,
    RemoteStateGuardPolicy,
)
from ..browser import BrowserError, BrowserSession, default_browser_session_factory
from ._adapter_utils import (
    _LocateHelper,
    _SedeCheckerModel,
    assert_query_browser_action_for,
    assert_read_landing,
    extract_marker_verdict,
    make_locate_helper,
    nif_check_operation_tail,
    registry_failure_message,
    require_playwright_page,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_NETWORKIDLE as _WAIT_NETWORKIDLE,
)
from ._browser_constants import (
    default_viewport,
)
from ._browser_stage import build_playwright_stage_runner
from .errors import BrowserAdapterTypeError, SedeError, SedeFailureMode, SedeNavigationError, SedeParseError

logger = get_logger(__name__)
_EXTERNAL = Settings.external_constants()
_GROI_HOST = urlsplit(_EXTERNAL.aeat.oracles.groi_check).netloc

# The one page this driver is allowed to be sitting on. The GROI form posts
# back to its own servlet -- the form's ``action`` is a RELATIVE path whose
# final segment ``_assert_form_action_is_consult_endpoint`` pins to this
# path's own last segment before any click runs -- so the servlet path is
# both the form page and the response page, and nothing else is a GROI read.
_GROI_READ_PATH_PREFIXES: tuple[str, ...] = (urlsplit(_EXTERNAL.aeat.oracles.groi_check).path,)


DEFAULT_GROI_TIMEOUT_MS: int = 30000

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
    # Widen to any subdomain under the AEAT apex so a ``www{n}`` load-balancer
    # dispatch is tolerated, not refused; success detection is unchanged.
    allowed_host_suffixes=(_EXTERNAL.aeat.domains.host_suffix,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.consult_oracle_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=False,
)


def assert_groi_read_landing(landing_url: str) -> None:
    """Refuse a landing that is not the GROI consult servlet.

    The pre-submit form-action check confirms where a click WILL post; this
    confirms where AEAT actually SERVED. They are different questions: the
    form action is read off a DOM AEAT controls, and a redirect chain after
    the POST is invisible to it. Called after every navigation and after
    every submit, so the verdict parser only ever reads a page this driver
    is entitled to be on.

    Public so the driver's no-write proof exercises this exact rule rather
    than a mirrored copy, which would keep agreeing with itself after the
    rule changed shape.

    Args:
        landing_url: The URL AEAT actually served, read off the page.

    Raises:
        SedeNavigationError: When the landing is not the GROI servlet.
    """
    assert_read_landing(
        landing_url,
        surface="GROI",
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=_GROI_READ_PATH_PREFIXES,
    )


def _assert_read_landing(page: Page) -> None:
    """Read the landed URL off ``page`` and route it through the GROI landing rule."""
    assert_groi_read_landing(getattr(page, "url", "") or "")


def _assert_query_browser_action(action: str) -> None:
    """Assert that ``action`` is permitted under the GROI read-only guard policy.

    Thin delegator to :func:`~._adapter_utils.assert_query_browser_action_for`
    with the GROI module-level ``_READ_GUARD_POLICY`` pre-bound.
    """
    assert_query_browser_action_for(_READ_GUARD_POLICY, action)


_playwright_stage = build_playwright_stage_runner(
    surface_label="GROI",
    log_prefix="groi",
    logger=logger,
)

_locate: _LocateHelper = make_locate_helper("GROI")


class GroiNifVerdict(_SedeCheckerModel):
    """One observation per declared Spanish NIF after live navigation.

    ``verdict`` is the AEAT-rendered ROI-registration status: ``valid``
    when AEAT reports the NIF as a registered intra-community operator,
    ``invalid`` when AEAT either says the NIF is unregistered or that
    the input format is malformed, ``unknown`` when the response text
    is structurally unanswerable.
    """

    nif: str = Field(min_length=1, max_length=32)
    verdict: Literal["valid", "invalid", "unknown"]
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class GroiResult(_SedeCheckerModel):
    """Aggregate live-driver result across every declared Spanish NIF."""

    observations: tuple[GroiNifVerdict, ...] = ()


class GroiSedeDriver:
    """Live AEAT GROI driver backed by the central BrowserSession surface.

    The driver navigates directly to the form servlet (the surface is
    reachable post cl@ve-movil auth without an intermediate sede entry
    page) and queries each declared NIF in alphabetical order. Verdict
    parsing keys off the AEAT certification phrases captured live.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Initialise the driver with optional ``Settings`` override.

        Args:
            settings: If ``None``, the driver resolves :class:`Settings`
                from the default load path when the session is created.
        """
        self._settings = settings

    @property
    def mode(self) -> Literal["live"]:
        """Always ``"live"`` — the driver requires a real Playwright session."""
        return "live"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Return the ordered list of :class:`RemoteOperation` entries planned for this driver run.

        Builds the sequence: GET the GROI URL, open the form, then one
        ``check-nif-<NIF>`` browser action per declared NIF (sorted
        alphabetically), and finally ``discard-session``.  At least one
        entry in ``expected`` is required; raises
        :class:`RegistryValidationError` otherwise.
        """
        del payload
        if not expected:
            raise RegistryValidationError("GroiSedeDriver.planned_operations requires at least one expected NIF")
        operations: list[RemoteOperation] = [
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl(Settings.external_constants().aeat.oracles.groi_check),
            ),
            RemoteOperation(kind="browser_action", action="open-groi-form"),
        ]
        # Normalise to match GroiOracle._expected_values so the operation
        # labels the guard pre-flight sees (driverless oracle path) match
        # what the live driver emits.
        return (*operations, *nif_check_operation_tail(expected))

    def collect(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_GROI_TIMEOUT_MS,
    ) -> GroiResult:
        """Run the async GROI driver synchronously and return a :class:`GroiResult`.

        Wraps :meth:`collect_async` in ``asyncio.run``.
        :class:`SedeError`, :class:`SiteHealthError`, and
        :class:`BrowserError` are re-raised as
        :class:`RegistryValidationError` for the registry oracle layer.
        """
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
        """Async entry point returning :class:`GroiResult` — delegates to :func:`collect_groi_observations`."""
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
    ) -> CheckerObservation:
        """Return the canonical checker observation from the per-NIF result.

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
        return CheckerObservation(values=values, raw_evidence_locator=evidence_locator)


async def collect_groi_observations(
    payload: bytes,
    *,
    expected: Mapping[str, object],
    settings: Settings | None = None,
    timeout_ms: int = DEFAULT_GROI_TIMEOUT_MS,
    browser_session_factory: Callable[[Settings], Awaitable[BrowserSession]] | None = None,
) -> GroiResult:
    """Drive the GROI form per declared NIF and return a :class:`GroiResult` with one observation each."""
    del payload
    if not expected:
        raise RegistryValidationError("collect_groi_observations requires at least one expected NIF")
    nifs = tuple(sorted(str(key) for key in expected))

    factory = browser_session_factory or default_browser_session_factory
    browser_session = await factory(settings or Settings())
    context = None
    try:
        context = await browser_session.create_context()
        page = require_playwright_page(await context.new_page())
        await _playwright_stage(
            page.set_viewport_size(default_viewport()),
            stage="set-viewport",
            description="GROI viewport",
            timeout_ms=timeout_ms,
        )

        observations: list[GroiNifVerdict] = []
        for nif in nifs:
            # The GROI servlet renders a fresh form on each GET; navigate per
            # NIF so each query starts clean and the response page is the
            # only DOM the verdict parser sees.
            await browser_session.navigate(page, Settings.external_constants().aeat.oracles.groi_check)
            await _playwright_stage(
                page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=timeout_ms),
                stage="wait-form-networkidle",
                description="GROI form network idle",
                timeout_ms=timeout_ms,
            )
            _assert_read_landing(page)
            await _open_groi_form(page, timeout_ms=timeout_ms)
            verdict = await _check_single_nif(page, nif=nif, timeout_ms=timeout_ms)
            observations.append(GroiNifVerdict(nif=nif, verdict=verdict, raw_evidence_locator=page.url))

        return GroiResult(observations=tuple(observations))
    except (BrowserAdapterTypeError, SedeError, SiteHealthError, BrowserError):
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
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-groi-check-close",
        )


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
        "open-groi-form:nif",
        "GROI NIF input",
        timeout_ms,
    )
    await _locate(
        page,
        _SUBMIT_SELECTORS,
        "open-groi-form:submit",
        "GROI submit button",
        timeout_ms,
    )
    await _assert_form_action_is_consult_endpoint(page, timeout_ms=timeout_ms)


# The form's ``action`` attribute is captured live as the final relative path
# segment of the centralized GROI oracle URL. Any deviation indicates AEAT
# changed the submission target and the driver must refuse to submit until the
# change is investigated.
_EXPECTED_FORM_ACTION = urlsplit(Settings.external_constants().aeat.oracles.groi_check).path.rsplit("/", 1)[-1]


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
        f"check-nif-{nif}:nif",
        "GROI NIF input",
        timeout_ms,
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
        f"check-nif-{nif}:submit",
        "GROI submit button",
        timeout_ms,
    )
    await _playwright_stage(
        submit.click(timeout=timeout_ms),
        stage=f"check-nif-{nif}:click",
        description="GROI submit click",
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )
    await _playwright_stage(
        page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=timeout_ms),
        stage=f"check-nif-{nif}:wait-response",
        description="GROI response network idle",
        timeout_ms=timeout_ms,
    )
    # The submit click issues a browser form POST. That POST never reaches
    # the first-party HTTP guard and the package's forbidden-verb source
    # scan permits ``click`` outright, so this is the only wall standing
    # between the click and whatever AEAT chose to serve.
    _assert_read_landing(page)
    body_text = await _playwright_stage(
        page.locator("body").inner_text(timeout=timeout_ms),
        stage=f"check-nif-{nif}:scrape-body",
        description="GROI response body text",
        timeout_ms=timeout_ms,
    )
    return extract_verdict_from_response_text(body_text)


_POSITIVE_MARKERS: tuple[str, ...] = (
    "consta un operador intracomunitario",
    "consta como operador intracomunitario",
    "operador intracomunitario identificado",
)


def extract_verdict_from_response_text(body_text: str) -> Literal["valid", "invalid", "unknown"]:
    """Parse the AEAT GROI verdict from the response body text.

    Positive markers are GROI's own ROI-registration phrases, verified
    against live AEAT response samples captured 2026-05-07. Rejection is
    classified by the shared
    :data:`~._adapter_utils.SPANISH_NEGATIVE_VERDICT_MARKERS` table, which
    every sede checker reads so one driver cannot recognise a refusal the
    other misses.
    """
    return extract_marker_verdict(body_text, positive_markers=_POSITIVE_MARKERS)


__all__ = [
    "DEFAULT_GROI_TIMEOUT_MS",
    "GroiNifVerdict",
    "GroiResult",
    "GroiSedeDriver",
    "collect_groi_observations",
    "extract_verdict_from_response_text",
]
