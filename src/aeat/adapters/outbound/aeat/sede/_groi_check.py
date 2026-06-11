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

from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.i18n import tr
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    GroiObservation,
    RegistryValidationError,
    RemoteOperation,
    RemoteStateGuardPolicy,
)
from ..browser import BrowserError, BrowserSession, default_browser_session_factory
from ._adapter_utils import (
    _LocateHelper,
    _SedeCheckerModel,
    assert_query_browser_action_for,
    make_locate_helper,
    normalize_response_text,
    registry_failure_message,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_NETWORKIDLE as _WAIT_NETWORKIDLE,
)
from ._browser_constants import (
    default_viewport,
)
from ._browser_stage import build_playwright_stage_runner
from ._errors import BrowserAdapterTypeError, SedeError, SedeFailureMode, SedeNavigationError, SedeParseError

logger = get_logger(__name__)
_EXTERNAL = Settings.external_constants()
_GROI_HOST = urlsplit(_EXTERNAL.aeat.oracles.groi_check).netloc


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
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.consult_oracle_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=False,
)


def _assert_query_browser_action(action: str) -> None:
    """Assert that ``action`` is permitted under the GROI read-only guard policy.

    Thin delegator to :func:`~._adapter_utils.assert_query_browser_action_for`
    with the GROI module-level ``_READ_GUARD_POLICY`` pre-bound.
    """
    assert_query_browser_action_for(_READ_GUARD_POLICY, action)


def _groi_shape_suggestion() -> str:
    """Return the localised shape-change suggestion string for GROI error messages."""
    return tr("adapters.aeat.sede.groi.suggestions.shape_change")


_playwright_stage = build_playwright_stage_runner(
    surface_label="GROI",
    log_prefix="groi",
    shape_suggestion=_groi_shape_suggestion(),
    logger=logger,
)

_locate: _LocateHelper = make_locate_helper("GROI", _groi_shape_suggestion())


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
                kind="http", method="GET", url=AnyUrl(Settings.external_constants().aeat.oracles.groi_check),
            ),
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
    ) -> GroiObservation:
        """Return a :class:`GroiObservation` by adapting the per-NIF result into the registry-Protocol shape.

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
        from playwright.async_api import Page as _Page

        _raw_page = await context.new_page()
        if not isinstance(_raw_page, _Page):
            raise BrowserAdapterTypeError(
                f"BrowserContext.new_page() did not return a Playwright Page; got {type(_raw_page)}",
                context={"actual_type": type(_raw_page).__name__},
            )
        page: _Page = _raw_page
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
