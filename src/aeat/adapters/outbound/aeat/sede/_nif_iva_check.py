"""Read-only AEAT NIF-IVA / VIES proxy browser driver.

Drives the public AEAT-hosted form servlet that proxies non-Spanish EU
IVA-identifier validity queries to the European Commission's VIES
service. The driver navigates from the sede gestiones page (which
issues the session cookies the form servlet requires) to the form
servlet itself, fills the country-code + IVA-number form per declared
NIF, scrapes the rendered validity verdict, and returns one
observation per declared NIF.

The contract mirrors :mod:`_renta_web_open`: a sibling sede adapter exposing
an async collection coroutine plus a synchronous wrapper that the registry
oracle can call. Browser-session lifecycle, guarded navigation, form
interaction, response parsing, and error mapping are implemented here.

The driver is intentionally read-only: the form mutates no AEAT-side
state under any NIF, requires no clave-móvil session, and writes
nothing to the autonomo's filing history. The remote-state guard
host-pinning suffix (``agenciatributaria.gob.es``) covers both the
sede entry subdomain and the www1 form-servlet subdomain.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

from pydantic import AnyUrl, Field

from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.i18n import tr
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    AeatNifIvaObservation,
    RegistryValidationError,
    RemoteOperation,
    RemoteStateGuardPolicy,
)
from .._playwright import PlaywrightError, PlaywrightTimeoutError
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
from ._errors import BrowserAdapterTypeError, SedeError, SedeFailureMode, SedeNavigationError

logger = get_logger(__name__)
_EXTERNAL = Settings.external_constants()
_AEAT_AUTH_GATE_4033_PATH = _EXTERNAL.aeat.sede_paths.auth_gate_4033
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_GROI_AUTH_UNLOCK_DESCRIPTOR = _EXTERNAL.aeat.oracles.groi_auth_unlock_descriptor
_NIF_IVA_AUTH_LOCKED_DESCRIPTOR = _EXTERNAL.aeat.oracles.nif_iva_auth_locked_descriptor
_NIF_IVA_ENTRY_HOST = urlsplit(f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.help_pages.nif_iva_landing}").netloc
_NIF_IVA_VERIFICATION_HOST = urlsplit(_EXTERNAL.aeat.oracles.nif_iva_verification).netloc

_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-nif-iva-direct-driver-read",
    evidence_tier="executable_parity_evidence",
    classification="open_simulator",
    allowed_hosts=(_NIF_IVA_ENTRY_HOST, _NIF_IVA_VERIFICATION_HOST),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.consult_oracle_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=False,
    requires_aeat_authorization=False,
)


def _assert_query_browser_action(action: str) -> None:
    assert_query_browser_action_for(_READ_GUARD_POLICY, action)


def _nif_iva_shape_suggestion() -> str:
    return tr("adapters.aeat.sede.nif_iva.suggestions.shape_change")


_playwright_stage = build_playwright_stage_runner(
    surface_label="NIF-IVA",
    log_prefix="nif iva",
    shape_suggestion=_nif_iva_shape_suggestion(),
    logger=logger,
)

_locate: _LocateHelper = make_locate_helper("NIF-IVA", _nif_iva_shape_suggestion())

DEFAULT_NIF_IVA_TIMEOUT_MS: int = 30000
_COUNTRY_SELECTORS: tuple[str, ...] = (
    'select[name*="pais" i]',
    'select[id*="pais" i]',
    'select[name*="country" i]',
    'select[id*="country" i]',
    'input[name*="pais" i]',
    'input[id*="pais" i]',
    'input[name*="country" i]',
    'input[id*="country" i]',
    "input.z-combobox-input",
)
_IVA_NUMBER_SELECTORS: tuple[str, ...] = (
    'input[name*="nif" i]',
    'input[id*="nif" i]',
    'input[name*="iva" i]',
    'input[id*="iva" i]',
    'input[name*="iva" i]',
    'input[id*="iva" i]',
    'input[type="text"]',
)
_SUBMIT_SELECTORS: tuple[str, ...] = (
    'button:has-text("Consultar")',
    'button:has-text("Comprobar")',
    'button:has-text("Verificar")',
    'input[type="submit"][value*="Consultar" i]',
    'input[type="submit"][value*="Comprobar" i]',
    'input[type="submit"][value*="Verificar" i]',
    'button[type="submit"]',
    'input[type="submit"]',
    'input[type="button"]',
)


class NifIvaCheckObservation(_SedeCheckerModel):
    """One observation emitted per declared NIF after live navigation.

    ``verdict`` is the AEAT/VIES-rendered validity for that NIF:
    ``valid``, ``invalid``, or ``unknown`` when the response is
    structurally unanswerable (network error mid-query, etc.).
    """

    nif: str = Field(min_length=1, max_length=32)
    verdict: Literal["valid", "invalid", "unknown"]
    raw_evidence_locator: str | None = Field(default=None, max_length=512)


class NifIvaCheckResult(_SedeCheckerModel):
    """Aggregate live-driver result across all declared NIFs for one browser pass.

    Each entry in ``observations`` corresponds to one NIF submitted to the
    AEAT-hosted VIES proxy form. An empty tuple signals that no NIFs were
    queried (caller-side guard: ``expected`` was empty before the driver ran).
    """

    observations: tuple[NifIvaCheckObservation, ...] = ()


class NifIvaCheckSedeDriver:
    """Live AEAT NIF-IVA driver backed by the central BrowserSession surface.

    The driver follows the sequence the oracle's ``planned_operations``
    enumerates: GET sede entry, GET form servlet, open the form,
    per-NIF check, discard the session.

    The driver follows the read-only public VIES proxy flow and converts the
    rendered AEAT response text into registry parity observations.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Construct a driver bound to ``settings``.

        Args:
            settings: Optional :class:`~aeat.core.config.Settings` instance.
                When ``None`` a default ``Settings()`` instance is created at
                ``collect_async`` / ``collect`` call time so callers that
                only inspect :attr:`mode` or call :meth:`planned_operations`
                pay no settings-resolution cost.
        """
        self._settings = settings

    @property
    def mode(self) -> Literal["live"]:
        """Driver execution mode — always ``"live"`` for this adapter."""
        return "live"

    def planned_operations(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> tuple[RemoteOperation, ...]:
        """Return the ordered list of remote operations this driver will perform.

        The sequence is fixed: one HTTP GET to the sede (AEAT electronic office)
        gestiones entry page, one HTTP GET to the VIES proxy form servlet, one
        browser action to open the form, one ``check-nif-<NIF>`` browser action
        per NIF in ``expected`` (sorted alphabetically), and finally a
        ``discard-session`` action. The sequence is used by the remote-state
        guard pre-flight to validate that all planned operations are within the
        driver's declared :class:`~aeat.domain.calculations.registry.RemoteStateGuardPolicy`.

        Args:
            payload: Raw oracle payload bytes. Not read by this driver; the
                argument exists to satisfy the oracle driver protocol.
            expected: Mapping keyed by NIF (Spanish or EU IVA identifier) whose
                VIES validity is to be checked. At least one entry is required.

        Returns:
            An immutable tuple of :class:`~aeat.domain.calculations.registry.RemoteOperation`
            records in execution order.

        Raises:
            RegistryValidationError: When ``expected`` is empty.
        """
        del payload
        if not expected:
            raise RegistryValidationError("NifIvaCheckSedeDriver.planned_operations requires at least one expected NIF")
        _ext = Settings.external_constants()
        operations: list[RemoteOperation] = [
            RemoteOperation(
                kind="http",
                method="GET",
                url=AnyUrl(f"{_ext.aeat.domains.sede}{_ext.aeat.help_pages.nif_iva_landing}"),
            ),
            RemoteOperation(kind="http", method="GET", url=AnyUrl(_ext.aeat.oracles.nif_iva_verification)),
            RemoteOperation(kind="browser_action", action="open-nif-iva-form"),
        ]
        # Normalise to match AeatNifIvaCheckerOracle._expected_values so the
        # operation labels the guard pre-flight sees (driverless oracle path)
        # match what the live driver emits.
        for nif in sorted(str(key).strip().upper() for key in expected):
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
        """Synchronous wrapper around :meth:`collect_async` for oracle callers.

        Runs the full browser-drive sequence inside ``asyncio.run`` and
        translates :class:`SedeError`, :class:`SiteHealthError`, and
        :class:`BrowserError` into :class:`RegistryValidationError` so the
        oracle protocol sees a single typed failure shape.

        Args:
            payload: Raw oracle payload bytes. Not read; present for protocol
                compatibility.
            expected: Mapping keyed by NIF whose VIES validity is to be checked.
            timeout_ms: Per-operation Playwright timeout in milliseconds.
                Defaults to ``DEFAULT_NIF_IVA_TIMEOUT_MS``.

        Returns:
            A :class:`NifIvaCheckResult` with one observation per NIF.

        Raises:
            RegistryValidationError: On browser navigation, sede, or health
                failures.
        """
        try:
            return asyncio.run(self.collect_async(payload, expected=expected, timeout_ms=timeout_ms))
        except (SedeError, SiteHealthError, BrowserError) as exc:
            raise RegistryValidationError(registry_failure_message(exc)) from exc

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
    ) -> AeatNifIvaObservation:
        """Collect results and return a typed :class:`~aeat.domain.calculations.registry.AeatNifIvaObservation`.

        Calls :meth:`collect` and projects the observations into the
        ``AeatNifIvaObservation`` shape the registry oracle expects: a
        ``values`` mapping of ``NIF -> verdict`` string and a single
        ``raw_evidence_locator`` (the first non-``None`` URL from the
        observation set).

        Args:
            payload: Raw oracle payload bytes. Not read; present for protocol
                compatibility.
            expected: Mapping keyed by NIF whose VIES validity is to be checked.

        Returns:
            An :class:`~aeat.domain.calculations.registry.AeatNifIvaObservation`
            with the collected verdicts and evidence locator.
        """
        result = self.collect(payload, expected=expected)
        values: dict[str, str] = {observation.nif: observation.verdict for observation in result.observations}
        evidence = next(
            (
                observation.raw_evidence_locator
                for observation in result.observations
                if observation.raw_evidence_locator
            ),
            None,
        )
        return AeatNifIvaObservation(values=values, raw_evidence_locator=evidence)

    async def collect_async(
        self,
        payload: bytes,
        *,
        expected: Mapping[str, object],
        timeout_ms: int = DEFAULT_NIF_IVA_TIMEOUT_MS,
    ) -> NifIvaCheckResult:
        """Async entry point that delegates to :func:`collect_nif_iva_check_observations`.

        Args:
            payload: Raw oracle payload bytes. Not read; present for protocol
                compatibility.
            expected: Mapping keyed by NIF whose VIES validity is to be checked.
            timeout_ms: Per-operation Playwright timeout in milliseconds.
                Defaults to ``DEFAULT_NIF_IVA_TIMEOUT_MS``.

        Returns:
            A :class:`NifIvaCheckResult` with one observation per NIF.
        """
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
    browser_session_factory: Callable[[Settings], Awaitable[BrowserSession]] | None = None,
) -> NifIvaCheckResult:
    """Open the NIF-IVA form, query each declared NIF, scrape verdicts into a :class:`NifIvaCheckResult`.

    The function navigates the AEAT sede gestiones entry, follows
    through to the form servlet (which the entry's session cookies
    authorise), iterates the declared NIFs alphabetically, and returns
    one observation per NIF.
    """
    del payload
    if not expected:
        raise RegistryValidationError("collect_nif_iva_check_observations requires at least one expected NIF")
    nifs = tuple(sorted(str(key) for key in expected))

    factory = browser_session_factory or default_browser_session_factory
    browser_session = await factory(settings or Settings())
    context = None
    try:
        context = await browser_session.create_context(storage_state={})
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
            description="NIF-IVA viewport",
            timeout_ms=timeout_ms,
        )

        # Sede entry: acquire the session cookies the form servlet requires.
        await browser_session.navigate(
            page, f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.help_pages.nif_iva_landing}",
        )
        await _playwright_stage(
            page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=timeout_ms),
            stage="wait-entry-networkidle",
            description="NIF-IVA sede entry network idle",
            timeout_ms=timeout_ms,
        )

        # Form servlet: now reachable with sede cookies set.
        await browser_session.navigate(page, _EXTERNAL.aeat.oracles.nif_iva_verification)
        await _playwright_stage(
            page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=timeout_ms),
            stage="wait-form-networkidle",
            description="NIF-IVA form servlet network idle",
            timeout_ms=timeout_ms,
        )

        # AEAT redirects unauthenticated requests to the centralized 4033 auth-gate path.
        # The standard country/IVA selectors won't be present on that page; if
        # we proceed they'll time out and surface as a misleading shape-change
        # error. Detect the redirect explicitly and surface auth-gate context.
        if is_aeat_auth_gate_redirect(page.url):
            raise SedeNavigationError(
                "IXVI form requires AEAT auth tier above cl@ve-movil; landed on AEAT 4033 page",
                failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                context={
                    "stage": "post-form-navigation",
                    "landing_url": page.url,
                    "expected_url": _EXTERNAL.aeat.oracles.nif_iva_verification,
                    "auth_tested": "clave_movil",
                    "auth_tested_unlocks": _GROI_AUTH_UNLOCK_DESCRIPTOR,
                    "auth_tested_does_not_unlock": _NIF_IVA_AUTH_LOCKED_DESCRIPTOR,
                },
                suggestion=(
                    "Empirical finding (live probe 2026-05-07 via DefaultBrowserSession + "
                    f"cl@ve-movil): the same authenticated session that unlocks the "
                    f"{_GROI_AUTH_UNLOCK_DESCRIPTOR} Spanish-ROI consult surface is REJECTED by the "
                    f"{_NIF_IVA_AUTH_LOCKED_DESCRIPTOR} foreign-EU surface. Next auth tier to test is "
                    "X.509 certificate "
                    "(via the certificate auth provider). If certificate also 4033s, the "
                    "IXVI surface likely requires the caller's own NIF to be ROI-registered "
                    "(modelo 036/037 box 582). Until either path lands, use the GROI "
                    "adapter for Spanish-counterparty verification or pivot foreign-EU "
                    "verification to the EU Commission's public VIES at ec.europa.eu "
                    "(separate adapter; requires expanding the host-pinning allow-list)."
                ),
            )

        await _open_nif_iva_form(page, timeout_ms=timeout_ms)

        observations: list[NifIvaCheckObservation] = []
        for nif in nifs:
            verdict = await _check_single_nif(page, nif=nif, timeout_ms=timeout_ms)
            observations.append(NifIvaCheckObservation(nif=nif, verdict=verdict, raw_evidence_locator=page.url))

        return NifIvaCheckResult(observations=tuple(observations))
    except (BrowserAdapterTypeError, SedeError, SiteHealthError, BrowserError):
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


async def _open_nif_iva_form(page: Page, *, timeout_ms: int) -> None:
    """Wait for the country and IVA-number controls to become interactive."""
    _assert_query_browser_action("open-nif-iva-form")
    await _locate(
        page,
        _COUNTRY_SELECTORS,
        "open-nif-iva-form:country",
        "NIF-IVA country-code control",
        timeout_ms,
    )
    await _locate(
        page,
        _IVA_NUMBER_SELECTORS,
        "open-nif-iva-form:iva-number",
        "NIF-IVA IVA-number control",
        timeout_ms,
    )


async def _check_single_nif(
    page: Page,
    *,
    nif: str,
    timeout_ms: int,
) -> Literal["valid", "invalid", "unknown"]:
    """Submit one NIF query and scrape the rendered verdict."""
    _assert_query_browser_action(f"check-nif-{nif}")
    country_code, iva_number = _split_vies_nif(nif)
    await _select_country_code(page, country_code, timeout_ms=timeout_ms)
    await _fill_iva_number(page, iva_number, timeout_ms=timeout_ms)
    await _click_query_button(page, timeout_ms=timeout_ms)
    await _playwright_stage(
        page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=timeout_ms),
        stage=f"check-nif-{nif}:wait-response",
        description="NIF-IVA response network idle",
        timeout_ms=timeout_ms,
    )
    body_text = await _playwright_stage(
        page.locator("body").inner_text(timeout=timeout_ms),
        stage=f"check-nif-{nif}:scrape-body",
        description="NIF-IVA response body text",
        timeout_ms=timeout_ms,
    )
    return extract_verdict_from_response_text(body_text)


def is_aeat_auth_gate_redirect(current_url: str) -> bool:
    """Return True when the live page URL points at AEAT's 4033 / 403 error page.

    AEAT redirects unauthenticated requests to the form servlet to its
    centralized 4033 auth-gate path (HTTP 200 OK landing on a 403-titled
    page). The detector keys off the configured path and host suffix so
    it stays specific to that exact failure mode. Other AEAT errors are
    intentionally not matched.
    """
    if not current_url:
        return False
    parsed = urlsplit(current_url)
    host = parsed.netloc.casefold()
    host_suffix = _AEAT_HOST_SUFFIX.casefold()
    if host != host_suffix and not host.endswith(f".{host_suffix}"):
        return False
    return _AEAT_AUTH_GATE_4033_PATH.casefold() in parsed.path.casefold()


def extract_verdict_from_response_text(body_text: str) -> Literal["valid", "invalid", "unknown"]:
    """Parse the AEAT-rendered verdict from response body text.

    AEAT renders the VIES response in Spanish. The parser is conservative:
    explicit negative verdicts win over generic positive words such as
    ``válido`` so phrases like ``no válido`` cannot be misclassified.
    """
    normalized = normalize_response_text(body_text)
    if not normalized:
        return "unknown"
    negative_markers = (
        "no consta",
        "no valido",
        "no es valido",
        "no esta identificado",
        "no se encuentra identificado",
        "no identificado",
        "operador no identificado",
        "invalid",
    )
    if any(marker in normalized for marker in negative_markers):
        return "invalid"
    positive_markers = (
        "si consta",
        "si esta identificado",
        "operador intracomunitario identificado",
        "operador identificado",
        "nif iva valido",
        "nif-iva valido",
        "valid",
    )
    if any(marker in normalized for marker in positive_markers):
        return "valid"
    return "unknown"


async def _select_country_code(page: Page, country_code: str, *, timeout_ms: int) -> None:
    locator = await _locate(
        page,
        _COUNTRY_SELECTORS,
        "check-nif:country",
        "NIF-IVA country-code control",
        timeout_ms,
    )
    try:
        await locator.select_option(value=country_code, timeout=timeout_ms)
        return
    except (AttributeError, PlaywrightError, PlaywrightTimeoutError):
        logger.debug("NIF-IVA country control did not accept select_option; falling back to fill", exc_info=True)
    await _fill_expected(
        locator,
        country_code,
        stage="check-nif:country",
        description="NIF-IVA country-code control",
        timeout_ms=timeout_ms,
    )


async def _fill_iva_number(page: Page, iva_number: str, *, timeout_ms: int) -> None:
    locator = await _locate(
        page,
        _IVA_NUMBER_SELECTORS,
        "check-nif:iva-number",
        "NIF-IVA IVA-number control",
        timeout_ms,
    )
    await _fill_expected(
        locator,
        iva_number,
        stage="check-nif:iva-number",
        description="NIF-IVA IVA-number control",
        timeout_ms=timeout_ms,
    )


async def _click_query_button(page: Page, *, timeout_ms: int) -> None:
    locator = await _locate(
        page,
        _SUBMIT_SELECTORS,
        "check-nif:submit",
        "NIF-IVA query button",
        timeout_ms,
    )
    await _click_expected(locator, stage="check-nif:submit", description="NIF-IVA query button", timeout_ms=timeout_ms)


async def _fill_expected(locator: Locator, value: str, *, stage: str, description: str, timeout_ms: int) -> None:
    await _playwright_stage(
        locator.fill(value, timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )


async def _click_expected(locator: Locator, *, stage: str, description: str, timeout_ms: int) -> None:
    await _playwright_stage(
        locator.click(timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )


def _split_vies_nif(nif: str) -> tuple[str, str]:
    normalized_nif = nif.strip().upper().replace(" ", "").replace("-", "")
    if len(normalized_nif) < 3 or not normalized_nif[:2].isalpha():
        raise RegistryValidationError(f"NIF-IVA value {nif!r} must start with a two-letter EU country code")
    iva_number = normalized_nif[2:]
    if not iva_number:
        raise RegistryValidationError(f"NIF-IVA value {nif!r} must include a IVA number after the country code")
    return normalized_nif[:2], iva_number


__all__ = [
    "DEFAULT_NIF_IVA_TIMEOUT_MS",
    "NifIvaCheckObservation",
    "NifIvaCheckResult",
    "NifIvaCheckSedeDriver",
    "collect_nif_iva_check_observations",
    "extract_verdict_from_response_text",
    "is_aeat_auth_gate_redirect",
]
