"""Read-only Renta WEB Open browser driver for the AEAT electronic office.

Drives the AEAT Renta WEB Open anonymous simulator — a publicly
accessible ZK-framework web application that lets an operator open a
synthetic IRPF (personal income tax) declaration, populate casilla
(numbered form field) inputs, and read back the computed summary values
without creating a real submission.

The driver is strictly read-only for tax-filing purposes: it never
presents, signs, or submits a declaration. It uses the *open* (no-auth)
simulator path so no citizen credential is required. The computed
values are returned as a :class:`RentaWebOpenObservation` for use by
the registry oracle comparison gate.

Key public surfaces:

* :class:`RentaWebOpenSedeDriver` — driver class wired to the central
  AEAT :class:`BrowserSession` surface.
* :func:`collect_renta_web_open_observation` — standalone async
  function that opens the simulator, fills the identification profile,
  optionally applies casilla overrides, and scrapes the summary values.
* :func:`extract_renta_web_open_summary_value` — pure text extractor
  for Spanish-formatted numeric values from the summary body text.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from re import compile
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import AnyUrl
from pydantic import ValidationError as PydanticValidationError

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Locator, Page

from .....core import CasillaId
from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....core.errors import SiteHealthError
from .....core.i18n import tr
from .....core.logging import get_logger
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .....domain.calculations.registry.renta_web_open_oracle import (
    RentaWebOpenDisplayOverride,
    RentaWebOpenLivePayload,
    RentaWebOpenObservation,
    RentaWebOpenSyntheticProfile,
    parse_renta_web_open_live_payload,
)
from .._playwright import PlaywrightError, PlaywrightTimeoutError
from ..browser import BrowserError, BrowserSession, DefaultBrowserSession, default_browser_session_factory
from ._adapter_utils import (
    assert_read_landing,
    normalize_display_text,
    registry_failure_message,
    require_playwright_page,
)
from ._browser_constants import PLAYWRIGHT_WAIT_NETWORKIDLE, default_viewport
from ._browser_stage import build_playwright_stage_runner
from ._renta_web_open_safety import assert_click_target_safe, install_page_safety_net
from .errors import BrowserAdapterTypeError, SedeError, SedeFailureMode, SedeNavigationError

_SPANISH_AMOUNT_RE = compile(r"[-+]?\d{1,3}(?:\.\d{3})*,\d{2}|[-+]?\d+(?:[.,]\d+)?")
logger = get_logger(__name__)

_EXTERNAL = Settings.external_constants()
_RENTA_WEB_OPEN_APP_HOST = urlsplit(_EXTERNAL.aeat.oracles.renta_web_open_app_template).netloc

# The OPEN simulator's own application directory, taken as the parent of the
# configured app template path. Everything the driver reads is a page inside
# that ZK application, so the directory is the whole read surface.
#
# This is the one landing rule in the package that must NOT key on ``.zul``:
# the simulator is itself served from ``index.zul``, so the censal reader's
# marker list -- which forbids ``.zul`` because AEAT's M036 filing tool is a
# ZK app -- would refuse the very page this driver exists to read. Per-surface
# evidence is why the allow-list is a directory here and a servlet path there.
_RENTA_WEB_OPEN_READ_PATH_PREFIXES: tuple[str, ...] = (
    urlsplit(_EXTERNAL.aeat.oracles.renta_web_open_app_template).path.rsplit("/", 1)[0] + "/",
)

# Local policy, declared the same way the GROI and NIF-IVA drivers declare
# theirs. The oracle's own policy is supplied by its registry cross-reference
# and is not reachable from this module; this one authorises nothing new, it
# only gives the landing rule an authority to check the landed host against.
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-renta-web-open-direct-driver-read",
    evidence_tier="executable_parity_evidence",
    classification="open_simulator",
    allowed_hosts=(_RENTA_WEB_OPEN_APP_HOST,),
    # Widen to any subdomain under the AEAT apex so a www{n} load-balancer
    # dispatch is tolerated, not refused; the path allow-list is unchanged.
    allowed_host_suffixes=(_EXTERNAL.aeat.domains.host_suffix,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.renta_web_open_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=False,
    requires_aeat_authorization=False,
)


def assert_renta_web_open_read_landing(landing_url: str) -> None:
    """Refuse a landing outside the anonymous OPEN simulator application.

    ``app_url`` is a field on the caller-supplied live payload, so the URL
    this driver navigates to is external input rather than a constant. The
    driver then fills a synthetic identification profile and casilla values
    into whatever it landed on. The click guard blocks a *presentar* click
    and the page safety net blocks a forbidden navigation, but neither
    establishes that the page being FILLED is the anonymous simulator --
    and a synthetic profile typed into a real declaration is already
    damage, whether or not the submit that follows is blocked.

    This rule closes that: the landing must be inside the OPEN application
    directory, so a payload pointing anywhere else is refused before any
    field is filled.

    Public so the driver's proof exercises this exact rule rather than a
    mirrored copy that would keep agreeing with itself.

    Args:
        landing_url: The URL AEAT actually served, read off the page.

    Raises:
        SedeNavigationError: When the landing is outside the OPEN simulator.
    """
    assert_read_landing(
        landing_url,
        surface="Renta WEB Open",
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=_RENTA_WEB_OPEN_READ_PATH_PREFIXES,
    )


def assert_renta_web_open_app_url(app_url: str) -> None:
    """Refuse a payload ``app_url`` this driver is not allowed to request.

    The landing rule below refuses the page being FILLED. This refuses the
    page being REQUESTED, and the two are not the same moment: a landing
    check runs after the browser has already issued the GET, so on its own
    it would let an off-AEAT ``app_url`` be fetched and only then refuse.

    That gap is narrow here and worth stating rather than overselling. The
    context is anonymous (``storage_state={}``), so no AEAT session travels
    with the request, and the simulator needs no credential. What this adds
    is that the request is not made at all, which also makes this the only
    ``navigate`` in the package whose target was unchecked while its seven
    siblings pre-flight theirs.

    The policy it checks against is this module's own, introduced with the
    landing rule and wired to nothing else, so the refusal cannot narrow or
    widen any other surface's allow-list.

    Args:
        app_url: The ``app_url`` carried on the live payload.

    Raises:
        SedeNavigationError: When the URL is not one this driver may request.
    """
    try:
        assert_remote_operation_allowed(
            _READ_GUARD_POLICY,
            RemoteOperation(kind="http", method="GET", url=AnyUrl(app_url)),
        )
    except (RegistryValidationError, PydanticValidationError) as exc:
        raise SedeNavigationError(
            f"Renta WEB Open payload app_url was refused before navigation: {exc}",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            translated_message=tr("adapters.sede.errors.landing_off_policy"),
            context={"app_url": app_url, "policy_id": _READ_GUARD_POLICY.id},
        ) from exc


def _assert_read_landing(page: Page) -> None:
    """Read the landed URL off ``page`` and route it through the OPEN simulator landing rule."""
    assert_renta_web_open_read_landing(getattr(page, "url", "") or "")


#: Timeout (ms) for the "element visible" fast-path probe when locating
#: casilla inputs. Deliberately short: fall through to the XPath fallback
#: immediately rather than block the caller loop.
_VISIBLE_PROBE_TIMEOUT_MS: int = 2_000

#: Timeout (ms) for individual element interactions (wait_for, click) in
#: the Renta WEB Open casilla navigation flow. Matches the Settings default
#: for form-interaction interactions across the sede adapter.
_ELEMENT_WAIT_TIMEOUT_MS: int = 10_000


_playwright_stage = build_playwright_stage_runner(
    surface_label="Renta WEB Open",
    log_prefix="renta web open",
    logger=logger,
)


class RentaWebOpenSedeDriver:
    """Renta WEB Open driver backed by the central AEAT BrowserSession surface."""

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
        expected: Mapping[CasillaId, object],
    ) -> tuple[RemoteOperation, ...]:
        """Return the ordered sequence of remote operations this driver will perform.

        Deserialises ``payload`` via :func:`parse_renta_web_open_live_payload`
        and builds the :class:`RemoteOperation` list: navigate to the app URL,
        start the open simulator, fill the identification profile, accept,
        apply any casilla-id-keyed overrides, navigate to the Resumen, scrape
        summary labels declared by canonical casilla id, navigate to any extra
        display-number scrape targets, and finally close the browser context.
        """
        live_payload = parse_renta_web_open_live_payload(payload)
        _require_payload_covers_expected_casillas(live_payload, expected)
        operations: list[RemoteOperation] = [
            RemoteOperation(kind="http", method="GET", url=live_payload.app_url),
            RemoteOperation(kind="browser_action", action="start-open-simulator"),
            RemoteOperation(kind="browser_action", action="fill-synthetic-profile"),
            RemoteOperation(kind="browser_action", action="accept-identification"),
        ]
        for casilla_id, override in sorted(live_payload.display_overrides_by_casilla_id.items()):
            display_number = override.display_number
            operations.append(
                RemoteOperation(kind="browser_action", action=f"navigate-to-display-number:{display_number}"),
            )
            operations.append(
                RemoteOperation(kind="browser_action", action=f"apply-display-override:{casilla_id}"),
            )
        if live_payload.display_overrides_by_casilla_id:
            operations.append(RemoteOperation(kind="browser_action", action="navigate-to-resumen"))
        for label in sorted(live_payload.summary_labels_by_casilla_id.values()):
            operations.append(RemoteOperation(kind="browser_action", action=f"scrape-summary-field:{label}"))
        for display_number in sorted(live_payload.scrape_display_numbers_by_casilla_id.values()):
            operations.append(
                RemoteOperation(kind="browser_action", action=f"navigate-to-display-number:{display_number}"),
            )
        operations.append(RemoteOperation(kind="browser_action", action="close-browser-context"))
        return tuple(operations)

    def collect_observation(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> RentaWebOpenObservation:
        """Run the async driver synchronously and return a :class:`RentaWebOpenObservation`.

        Wraps :meth:`collect_observation_async` in ``asyncio.run``.
        :class:`SedeError`, :class:`SiteHealthError`, and
        :class:`BrowserError` are re-raised as
        :class:`RegistryValidationError` so the registry oracle layer
        sees a uniform failure type.
        """
        try:
            return asyncio.run(self.collect_observation_async(payload, expected=expected))
        except (SedeError, SiteHealthError, BrowserError) as exc:
            raise RegistryValidationError(registry_failure_message(exc)) from exc

    async def collect_observation_async(
        self,
        payload: bytes,
        *,
        expected: Mapping[CasillaId, object],
    ) -> RentaWebOpenObservation:
        """Return a :class:`RentaWebOpenObservation` by delegating to the functional collector."""
        return await collect_renta_web_open_observation(payload, expected=expected, settings=self._settings)


async def collect_renta_web_open_observation(
    payload: bytes,
    *,
    expected: Mapping[CasillaId, object],
    settings: Settings | None = None,
) -> RentaWebOpenObservation:
    """Open the anonymous simulator, create a synthetic declaration, and return a :class:`RentaWebOpenObservation`."""
    live_payload = parse_renta_web_open_live_payload(payload)
    _require_payload_covers_expected_casillas(live_payload, expected)
    browser_session = await default_browser_session_factory(settings or Settings())
    context = None
    try:
        page, context = await _open_renta_web_open_session(browser_session, live_payload=live_payload)
        await _drive_open_simulator_identification(page, live_payload=live_payload)
        if live_payload.display_overrides_by_casilla_id:
            await _apply_display_overrides(
                page,
                live_payload.display_overrides_by_casilla_id,
                timeout_ms=live_payload.timeout_ms,
            )
            await _navigate_to_resumen(page, timeout_ms=live_payload.timeout_ms)
        values = await _scrape_renta_web_open_values(page, live_payload=live_payload)
        # raw_evidence_locator is stored parity evidence; assert the landing
        # before recording it so the locator names a page this driver was
        # entitled to read.
        _assert_read_landing(page)
        return RentaWebOpenObservation(values=values, raw_evidence_locator=page.url)
    except (BrowserAdapterTypeError, SedeError, SiteHealthError, BrowserError):
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
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-renta-web-open-close",
        )


async def _open_renta_web_open_session(
    browser_session: BrowserSession | DefaultBrowserSession,
    *,
    live_payload: RentaWebOpenLivePayload,
) -> tuple[Page, BrowserContext]:
    """Create a Playwright context, install safety nets, and navigate to the open simulator app.

    Returns ``(page, context)``. SAFETY-CRITICAL: installs the
    dialog auto-dismiss + URL navigation guard before any user
    interaction — the page-level safety net is the outermost
    defense layer; click-time ``assert_click_target_safe`` is the
    inner ring.
    """
    context = await browser_session.create_context(storage_state={})
    page = require_playwright_page(await context.new_page())
    await install_page_safety_net(page)
    await _playwright_stage(
        page.set_viewport_size(default_viewport()),
        stage="set-viewport",
        description="Renta WEB Open viewport",
        timeout_ms=live_payload.timeout_ms,
    )
    assert_renta_web_open_app_url(str(live_payload.app_url))
    await browser_session.navigate(page, str(live_payload.app_url))
    await _playwright_stage(
        page.wait_for_load_state(PLAYWRIGHT_WAIT_NETWORKIDLE, timeout=live_payload.timeout_ms),
        stage="wait-app-networkidle",
        description="Renta WEB Open network idle after app navigation",
        timeout_ms=live_payload.timeout_ms,
    )
    # app_url is caller-supplied payload input, so this is the first point
    # at which the page about to be FILLED can be established as the
    # anonymous simulator rather than something else AEAT served.
    _assert_read_landing(page)
    return page, context


async def _drive_open_simulator_identification(page: Page, *, live_payload: RentaWebOpenLivePayload) -> None:
    """Drive the "Nueva declaración" -> identification profile -> "Aceptar" -> summary wait flow."""
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


async def _scrape_renta_web_open_values(
    page: Page,
    *,
    live_payload: RentaWebOpenLivePayload,
) -> dict[CasillaId, str]:
    """Scrape summary-label values + extra form values by canonical casilla id.

    The summary scrape reads the body text once and extracts each label
    declared in ``summary_labels_by_casilla_id``. The extra form scrape
    navigates to each requested browser display number via the Buscar dialog
    and reads the input value off the form page. All emitted values are keyed
    by canonical ``casilla.id``.
    """
    body_text = await _playwright_stage(
        page.locator("body").inner_text(timeout=live_payload.timeout_ms),
        stage="scrape-summary-text",
        description="Renta WEB Open body text",
        timeout_ms=live_payload.timeout_ms,
    )
    values: dict[CasillaId, str] = {}
    for casilla_id, label in sorted(live_payload.summary_labels_by_casilla_id.items()):
        observed = extract_renta_web_open_summary_value(body_text, label)
        if observed is not None:
            values[casilla_id] = observed
    for casilla_id, display_number in sorted(live_payload.scrape_display_numbers_by_casilla_id.items()):
        scraped = await _scrape_display_form_value(page, display_number, timeout_ms=live_payload.timeout_ms)
        if scraped is not None:
            values[casilla_id] = scraped
    return values


def _require_payload_covers_expected_casillas(
    live_payload: RentaWebOpenLivePayload,
    expected: Mapping[CasillaId, object],
) -> None:
    expected_ids = frozenset(expected)
    declared_ids = frozenset(live_payload.summary_labels_by_casilla_id) | frozenset(
        live_payload.scrape_display_numbers_by_casilla_id,
    )
    if not declared_ids:
        raise RegistryValidationError(
            "Renta WEB Open live payload must declare summary_labels_by_casilla_id or "
            "scrape_display_numbers_by_casilla_id keyed by canonical casilla.id",
        )
    missing = tuple(sorted(expected_ids - declared_ids))
    if missing:
        raise RegistryValidationError(
            "Renta WEB Open live payload does not declare scrape coordinates for expected "
            f"casilla.id values {missing!r}",
        )


def extract_renta_web_open_summary_value(body_text: str, label: str) -> str | None:
    """Extract one Spanish-formatted numeric value from Renta WEB Open summary text."""
    normalized_label = normalize_display_text(label)
    lines = [normalize_display_text(line) for line in body_text.splitlines()]
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


async def _navigate_to_display_number(page: Page, display_number: str, *, timeout_ms: int) -> None:
    """Open the Buscar casilla dialog, enter the visible field number, jump to the page.

    On the Resumen view the "Buscar casilla" button lives on a secondary
    toolbar that is collapsed by default; we expand it via the
    "Mostrar opciones" toggle first. Once visible, clicking Buscar opens
    a modal dialog with a 4-char "Número de casilla" input and an
    "Ir a la página" button. Typing a valid display number enables both
    the search button and the navigation button; clicking "Ir a la
    página" navigates the form to the page containing that casilla.
    """
    # Expand the secondary toolbar (idempotent — already expanded is fine).
    # If the locator isn't visible (toolbar already expanded), skip silently
    # without clicking — _click_expected raises rather than no-ops, which is
    # the contract we need to gate on visibility first.
    mostrar = page.locator('button[title="Mostrar opciones"]').first
    try:
        await mostrar.wait_for(state="visible", timeout=_ELEMENT_WAIT_TIMEOUT_MS)
    except Exception as exc:
        logger.debug("mostrar opciones already expanded or unavailable: %s", exc, exc_info=True)
    else:
        await _click_expected(
            mostrar,
            stage=f"navigate-to-display-number:{display_number}:mostrar-opciones",
            description="Mostrar opciones toolbar expander",
            timeout_ms=_ELEMENT_WAIT_TIMEOUT_MS,
        )
    await _click_expected(
        page.locator('button[title="Buscar casilla"]').first,
        stage=f"navigate-to-display-number:{display_number}:open-dialog",
        description="Buscar casilla button",
        timeout_ms=timeout_ms,
    )
    casilla_input = page.locator('input.estiloAlfanumerico[maxlength="4"]').first
    await _fill_expected(
        casilla_input,
        display_number,
        stage=f"navigate-to-display-number:{display_number}:type-number",
        description="Buscar casilla display-number input",
        timeout_ms=timeout_ms,
    )
    # Pressing Enter (or Tab) commits the value and triggers ZK validation
    # so the inline "Buscar casilla" lupa button enables.
    await casilla_input.press("Enter", timeout=timeout_ms)
    # After validation the "Ir a la página" button becomes enabled.
    ir_pagina = page.locator('button:has-text("Ir a la página")').first
    await ir_pagina.wait_for(state="visible", timeout=timeout_ms)
    await _click_expected(
        ir_pagina,
        stage=f"navigate-to-display-number:{display_number}:jump-to-page",
        description="Ir a la página button",
        timeout_ms=timeout_ms,
    )


async def _navigate_to_resumen(page: Page, *, timeout_ms: int) -> None:
    """Return to the Resumen view after editing form casillas."""
    await _click_expected(
        page.locator('button:has-text("Resumen")').first,
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


async def _locate_display_number_input(page: Page, display_number: str, *, timeout_ms: int) -> Locator:
    """Locate the editable input for a given visible form-field number.

    The Buscar casilla dialog's "Ir a la página" navigation auto-focuses
    the target input field. We first try the focused-element fast path,
    then fall back to a wider search by the display number's nearby
    label text. ZK form widgets carry the display number as a
    sibling span/label rather than on the input itself.
    """
    # Fast path: the navigation auto-focuses the casilla input.
    focused_input = page.locator("input:focus").first
    try:
        await focused_input.wait_for(state="visible", timeout=_VISIBLE_PROBE_TIMEOUT_MS)
        return focused_input
    except Exception as exc:
        logger.debug("focused-input fast path unavailable for %s: %s", display_number, exc, exc_info=True)
    # Fallback: locate an input adjacent to a label containing the display number.
    return page.locator(f"xpath=//*[normalize-space(text())='{display_number}']/following::input[1]").first


async def _apply_display_overrides(
    page: Page,
    overrides_by_casilla_id: Mapping[CasillaId, RentaWebOpenDisplayOverride],
    *,
    timeout_ms: int,
) -> None:
    """Apply each canonical-casilla override by navigating and filling it.

    Uses the Buscar casilla dialog to jump to each display number's page, then
    fills the auto-focused input (or the input near the display number's
    label) with the requested value.
    """
    for casilla_id, override in overrides_by_casilla_id.items():
        display_number = override.display_number
        await _navigate_to_display_number(page, display_number, timeout_ms=timeout_ms)
        locator = await _locate_display_number_input(page, display_number, timeout_ms=timeout_ms)
        await _fill_expected(
            locator,
            override.value,
            stage=f"apply-display-override:{casilla_id}",
            description=f"casilla.id {casilla_id} display-number {display_number} input",
            timeout_ms=timeout_ms,
        )


async def _scrape_display_form_value(
    page: Page,
    display_number: str,
    *,
    timeout_ms: int,
) -> str | None:
    """Read the current value of one visible form-field input.

    Navigates to the casilla via the Buscar dialog, reads the input value,
    and returns the raw string. Returns None when the locator does not
    resolve (the casilla may be on a page that requires upstream inputs).
    """
    try:
        await _navigate_to_display_number(page, display_number, timeout_ms=timeout_ms)
    except SedeNavigationError as exc:
        logger.debug(
            "renta web open: navigation to display number %s failed; treating as unreadable (%s)",
            display_number,
            exc,
        )
        return None
    try:
        locator = await _locate_display_number_input(page, display_number, timeout_ms=timeout_ms)
        return await locator.input_value(timeout=timeout_ms)
    except (PlaywrightError, PlaywrightTimeoutError, BrowserError, SedeError) as exc:
        logger.debug(
            "renta web open: input read for display number %s failed; treating as unreadable (%s)",
            display_number,
            exc,
        )
        return None


async def _fill_identification_profile(page: Page, profile: RentaWebOpenSyntheticProfile, *, timeout_ms: int) -> None:
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


async def _select_combo_item(page: Page, *, combo_index: int, item_text: str, timeout_ms: int) -> None:
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


async def _fill_expected(locator: Locator, value: str, *, stage: str, description: str, timeout_ms: int) -> None:
    await _expect_visible(locator, stage=stage, description=description, timeout_ms=timeout_ms)
    await _playwright_stage(
        locator.fill(value, timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
    )


async def _click_expected(locator: Locator, *, stage: str, description: str, timeout_ms: int) -> None:
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


async def _expect_visible(locator: Locator, *, stage: str, description: str, timeout_ms: int) -> None:
    await _playwright_stage(
        locator.wait_for(state="visible", timeout=timeout_ms),
        stage=stage,
        description=description,
        timeout_ms=timeout_ms,
        timeout_is_shape_change=True,
    )


__all__ = [
    "RentaWebOpenLivePayload",
    "RentaWebOpenSedeDriver",
    "collect_renta_web_open_observation",
    "extract_renta_web_open_summary_value",
]
