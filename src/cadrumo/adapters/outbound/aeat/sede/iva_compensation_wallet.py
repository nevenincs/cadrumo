"""Read-only AEAT IVA compensation wallet reader.

The wallet is external AEAT account state. This module only captures
and parses evidence from the authenticated Sede surface; calculation
selection happens later in the application reconciliation layer.

This module owns the Playwright navigation and representation-gate state
machine; the side-effect-free HTML parsing, URL-audit, and page-shape
diagnostics live in the sibling ``_iva_compensation_wallet_parsing`` module
and are re-imported here so the public read surface is unchanged.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import quote, urljoin, urlsplit

from pydantic import AnyUrl

from .....core.async_cleanup import close_async_resources
from .....core.config import Settings, load_settings
from .....core.directory_scan import scan_directory
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.paths import select_filesystem_retention_survivors
from .....core.period import Period
from .....core.time.clock import now
from .....domain.calculations.registry.remote_state_guard import (
    RemoteOperation,
    assert_remote_operation_allowed,
)
from .._html import parse_html
from .._playwright import PlaywrightError
from .._representation_gate import (
    dismiss_pre303_alert_modal_if_present,
    wait_for_own_name_representation_selector,
)
from ..browser.factory import DefaultBrowserSession, default_browser_session_factory
from ._adapter_utils import assert_read_landing, is_aeat_auth_gate_redirect, landed_origin, redacted_url
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_NETWORKIDLE as _WAIT_NETWORKIDLE,
)
from ._iva_compensation_wallet_parsing import (
    EXTERNAL,
    IVA_COMPENSATION_WALLET_READ_POLICY,
    PRE303,
    WALLET_PATH,
    WALLET_URL,
    assert_own_name_representation_form_html,
    discover_iva_compensation_wallet_entrypoint,
    has_wallet_table,
    is_aeat_wallet_read_url,
    looks_like_executed_empty_wallet_page,
    parse_iva_compensation_wallet_html,
    wallet_execute_form_method,
    wallet_execute_gate_status,
    wallet_page_shape_context,
)
from .errors import SedeFailureMode, SedeNavigationError, SedeParseError
from .schema import IvaCompensationWalletObservation

if TYPE_CHECKING:
    from .....application.auth.session_types import AeatSession
    from .._playwright import Page


log = get_logger(__name__)

_PRE303_PRESENTATION_URL = f"{EXTERNAL.aeat.domains.sede}{PRE303.presentation_service_path}"
_PRE303_SELECTOR_URL = EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(PRE303.presentation_service_path, safe=""),
)
_WALLET_SELECTOR_URL = EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(EXTERNAL.aeat.sede_paths.iva_compensation_wallet, safe=""),
)
_OWN_NAME_REPRESENTATION_ACTION = PRE303.representation_own_name_action_label
_WALLET_DISCOVERED_ENTRYPOINT_ACTION = PRE303.wallet_discovered_entrypoint_action_label
_WALLET_EXECUTE_READ_ACTION = PRE303.wallet_execute_read_action_label
IVA_COMPENSATION_WALLET_URL = WALLET_URL
PRE303_PRESENTATION_SERVICE_URL = _PRE303_PRESENTATION_URL

# The pages a wallet READ legitimately rests on: the Pre303 presentation
# service the wallet link is discovered from, and the wallet itself. Both
# are already-declared constants reduced to their PATH, so the allow-list
# asserts nothing this module did not already navigate to on purpose, and
# the Pre303 entry's query (``?forigen=pre303``) is dropped because a path
# comparison must not see it.
#
# The two Cl@ve surfaces this read passes THROUGH -- the access selector
# and AEAT's acting-capacity gate -- are deliberately absent. They are
# transit, not rest, and admitting either would let a traversal that
# stalled on it pass as a completed read.
#
# What sits in front of each landing rule is NOT the same guarantee, so do
# not read them as one. Four run on this module. The own-name
# continuation's follows a ``wait_for_url`` that has already required the
# traversal to reach the target path, so a stall raises before the rule is
# reached. The execute read carries two, neither behind a URL wait: one
# runs as soon as the page's shape is known and before that shape is
# judged, so every exit from the execute read has passed a rule; the other
# runs after the ``ejecutar`` POST and is the only wall that sees where
# AEAT served it. The fourth runs at the terminal parse, where the
# recorded ``source_url`` is CONSTRUCTED from the landed origin plus the
# wallet path rather than observed.
#
# The parser is not a fifth. It demands a wallet table, so it answers "is
# this a wallet?" and never "did AEAT serve a page we declared?" -- it
# backstops the shape, not the landing.
#
# The acting-capacity gate additionally CANNOT be admitted through the
# shared rule, and the reason is worth stating where someone would
# otherwise try: the canonical AEAT write-verb scan matches its substrings,
# and ``DialogoRepresentacion`` contains ``presentacion``. Any code that
# routes that URL through a remote-state guard is refused with a message
# naming a write token the page does not carry. Do not "fix" that by
# narrowing the canonical token set -- it exists to catch real presentation
# surfaces; give the gate its own predicate if a rule for it is ever needed.
_WALLET_READ_PATH_PREFIXES: tuple[str, ...] = (
    urlsplit(PRE303.presentation_service_path).path,
    urlsplit(WALLET_PATH).path,
)


async def fetch_iva_compensation_wallet(
    session: AeatSession,
    *,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    settings: Settings | None = None,
) -> IvaCompensationWalletObservation:
    """Fetch and parse AEAT's read-only IVA compensation wallet as a :class:`IvaCompensationWalletObservation`."""
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    if target_period.filing_year != target_year:
        raise SedeNavigationError(
            "IVA wallet target_year does not match target_period.filing_year",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"target_year": target_year, "target_period_year": target_period.filing_year},
        )
    _assert_read_http("GET", _PRE303_PRESENTATION_URL)
    _assert_read_http("GET", WALLET_URL)
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    browser_session = await default_browser_session_factory(settings)
    context = None
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        page = await context.new_page()
        try:
            await _open_authenticated_surface(
                page,
                browser_session=browser_session,
                settings=settings,
                selector_url=_PRE303_SELECTOR_URL,
                target_path=PRE303.presentation_service_path,
                expected_url=_PRE303_PRESENTATION_URL,
                surface="pre303_presentation_service",
                target_year=target_period.filing_year,
                target_period=target_period,
            )
            if is_aeat_auth_gate_redirect(page.url):
                raise SedeNavigationError(
                    "AEAT Pre303 presentation surface rejected the authenticated session with 4033",
                    failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                    context={
                        "landing_url": redacted_url(page.url),
                        "expected_url": redacted_url(_PRE303_PRESENTATION_URL),
                        "surface": "pre303_presentation_service",
                    },
                )
            pre303_html = await page.content()
            discovered_wallet_url = discover_iva_compensation_wallet_entrypoint(
                pre303_html,
                base_url=getattr(page, "url", "") or _PRE303_PRESENTATION_URL,
            )
            if discovered_wallet_url is not None:
                wallet_execute_submitted = await _open_discovered_wallet_entrypoint(
                    page,
                    browser_session=browser_session,
                    settings=settings,
                    discovered_url=discovered_wallet_url,
                    target_year=target_period.filing_year,
                    target_period=target_period,
                )
            else:
                wallet_execute_submitted = await _open_authenticated_surface(
                    page,
                    browser_session=browser_session,
                    settings=settings,
                    selector_url=_WALLET_SELECTOR_URL,
                    target_path=EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
                    expected_url=WALLET_URL,
                    surface="iva_compensation_wallet",
                    target_year=target_period.filing_year,
                    target_period=target_period,
                )
        except PlaywrightError as exc:
            raise SedeNavigationError(
                f"Pre303/wallet navigation failed for {_PRE303_PRESENTATION_URL!r} -> {WALLET_URL!r}: {exc}",
            ) from exc
        if is_aeat_auth_gate_redirect(page.url):
            raise SedeNavigationError(
                "AEAT IVA compensation wallet rejected the authenticated session with 4033",
                failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                context={
                    "landing_url": redacted_url(page.url),
                    "expected_url": redacted_url(WALLET_URL),
                    "surface": "iva_compensation_wallet",
                },
            )
        # The terminal read, and the one that had no landing rule. The two
        # rules above sit on branches -- after the representation gate, and
        # after the ejecutar submit -- so a wallet that was ALREADY executed
        # takes neither, and this parse ran with only the 4033 auth-gate
        # check between it and whatever AEAT served.
        #
        # It matters more here than on either branch, because
        # _landed_wallet_url CONSTRUCTS the recorded source_url as
        # origin + the wallet path. It refuses an unreadable origin but
        # never checks the path, so a readable landing on the wrong page
        # produced evidence asserting the wallet path for a page that was
        # not the wallet. Asserting the landing first is what makes that
        # construction truthful.
        _assert_read_landing(page)
        html = await page.content()
        final_dump_dir = settings.cadrumo_wallet_diagnostic_dump_dir
        if final_dump_dir is not None:
            await _dump_wallet_diagnostic(page, label="final-parse-input", dump_dir=final_dump_dir)
        try:
            return parse_iva_compensation_wallet_html(
                html,
                taxpayer_nif=taxpayer_nif or session.identity_nif,
                authenticated_identity=session.identity_nif,
                target_year=target_period.filing_year,
                target_period=target_period,
                source_url=_landed_wallet_url(page),
                captured_at=now(),
                allow_empty_wallet_shell=wallet_execute_submitted,
            )
        except SedeParseError as exc:
            raise SedeParseError(
                str(exc),
                failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                context=wallet_page_shape_context(html, landing_url=page.url),
            ) from exc
    finally:
        await close_async_resources(
            context,
            browser_session,
            task_name="cadrumo-iva-wallet-close",
        )


async def _open_authenticated_surface(
    page: Page,
    *,
    browser_session: DefaultBrowserSession,
    settings: Settings,
    selector_url: str,
    target_path: str,
    expected_url: str,
    surface: str,
    target_year: int,
    target_period: Period,
) -> bool:
    """Open an aeat app through the selector so Cl@ve app-local state is minted."""
    _assert_read_http("GET", selector_url)
    await browser_session.navigate(page, selector_url)
    await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
    current_url = getattr(page, "url", "") or ""
    selector_marker = EXTERNAL.aeat.clave_movil.selector_access_path_marker
    if selector_marker in current_url:
        _assert_read_browser_action("clave-movil-authorize")
        await page.click(EXTERNAL.aeat.clave_movil.authorize_button_selector)
        try:
            await page.wait_for_url(
                lambda url: target_path in url or is_aeat_auth_gate_redirect(url) or _is_representation_gate_url(url),
                timeout=settings.cadrumo_browser_navigation_timeout_ms,
            )
        except PlaywrightError:
            log.debug(
                "IVA wallet selector dispatch did not reach expected surface=%s expected_url=%s current_url=%s",
                surface,
                expected_url,
                getattr(page, "url", None),
                exc_info=True,
            )
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
    current_url = getattr(page, "url", "") or ""
    if _is_representation_gate_url(current_url):
        await _continue_own_name_representation(
            page,
            settings=settings,
            expected_url=expected_url,
            target_path=target_path,
            surface=surface,
        )
    try:
        await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.cadrumo_browser_navigation_timeout_ms)
    except PlaywrightError:
        log.debug(
            "IVA wallet surface did not reach networkidle surface=%s current_url=%s",
            surface,
            getattr(page, "url", None),
            exc_info=True,
        )
    if surface == "iva_compensation_wallet":
        return await _submit_wallet_execute_gate_if_present(
            page,
            settings=settings,
            expected_url=expected_url,
            target_year=target_period.filing_year,
            target_period=target_period,
        )
    return False


def _is_representation_gate_url(current_url: str) -> bool:
    if not current_url:
        return False
    try:
        path = urlsplit(current_url).path
    except ValueError:
        return False
    return EXTERNAL.aeat.clave_movil.dialogo_representacion_path_marker in path


async def _open_discovered_wallet_entrypoint(
    page: Page,
    *,
    browser_session: DefaultBrowserSession,
    settings: Settings,
    discovered_url: str,
    target_year: int,
    target_period: Period,
) -> bool:
    """Open a wallet link discovered from the authenticated Pre303 page."""
    _assert_read_http("GET", discovered_url)
    _assert_read_browser_action(_WALLET_DISCOVERED_ENTRYPOINT_ACTION)
    await browser_session.navigate(page, discovered_url)
    await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
    if _is_representation_gate_url(getattr(page, "url", "") or ""):
        await _continue_own_name_representation(
            page,
            settings=settings,
            expected_url=WALLET_URL,
            target_path=EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
            surface="iva_compensation_wallet",
        )
    try:
        await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.cadrumo_browser_navigation_timeout_ms)
    except PlaywrightError:
        log.debug(
            "Discovered IVA wallet entrypoint did not reach networkidle current_url=%s",
            getattr(page, "url", None),
            exc_info=True,
        )
    return await _submit_wallet_execute_gate_if_present(
        page,
        settings=settings,
        expected_url=WALLET_URL,
        target_year=target_period.filing_year,
        target_period=target_period,
    )


async def _continue_own_name_representation(
    page: Page,
    *,
    settings: Settings,
    expected_url: str,
    target_path: str,
    surface: str,
) -> None:
    """Continue only through AEAT's own-name acting-capacity selector."""
    _assert_read_browser_action(_OWN_NAME_REPRESENTATION_ACTION)
    try:
        selected_own_name = await _wait_for_own_name_representation_selector(page, settings=settings)
        await _dismiss_pre303_alert_modal_if_present(page)
        await _assert_own_name_representation_form(page, expected_path=target_path)
        await page.click(selected_own_name)
        await _assert_own_name_representation_form(page, expected_path=target_path)
        await page.click(PRE303.representation_submit_selector)
        await page.wait_for_url(
            lambda url: target_path in url or is_aeat_auth_gate_redirect(url),
            timeout=settings.cadrumo_browser_navigation_timeout_ms,
        )
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
        # The wait predicate admits the 4033 auth gate on purpose, so the
        # caller can raise its own diagnostic; it is not a landing rule.
        # This is.
        _assert_read_landing(page)
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT representation gate did not expose the own-name continuation expected for the "
            "authenticated profile user.",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={
                "landing_url": redacted_url(getattr(page, "url", None)),
                "expected_url": redacted_url(expected_url),
                "surface": surface,
                "blocked_operation": "representative_or_unknown_representation_gate",
            },
        ) from exc


async def _wait_for_own_name_representation_selector(page: Page, *, settings: Settings) -> str:
    def _raise_configuration_error(message: str) -> NoReturn:
        raise SedeNavigationError(message, failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED)

    return await wait_for_own_name_representation_selector(
        page,
        own_name_label_selector=PRE303.representation_own_name_label_selector,
        own_name_selector=PRE303.representation_own_name_selector,
        probe_timeout_ms=settings.cadrumo_browser_selector_probe_timeout_ms,
        raise_configuration_error=_raise_configuration_error,
    )


async def _assert_own_name_representation_form(page: Page, *, expected_path: str) -> None:
    html = await page.content()
    assert_own_name_representation_form_html(
        html,
        landing_url=getattr(page, "url", "") or "",
        expected_path=expected_path,
    )


async def _dismiss_pre303_alert_modal_if_present(page: Page) -> None:
    """Dismiss AEAT's pre303 alert modal, delegating to the canonical collapsed check.

    Per operator directive, this reader's prior raw-substring test (no
    ``"show"``-class check at all) was ruled the incorrect half of a critical
    double declaration against the auth reader's copy and is deleted, not
    kept as an alternative -- see
    :func:`~adapters.outbound.aeat._representation_gate.dismiss_pre303_alert_modal_if_present` for
    the collapsed predicate and the residual evidence gap this ruling
    accepts. Unlike the auth caller, this one supplies a diagnostic: a
    decline here is NEW behaviour (the deleted version would have clicked in
    this exact case), on a live AEAT money-surface reader, so it must be
    visible in this reader's own log output rather than read off a stack
    trace three layers away if the read subsequently stalls or times out.
    """

    def _log_declined_hidden_modal() -> None:
        log.warning(
            "pre303 alert modal present but not shown; declining to dismiss it "
            "(selector=%r) -- if the read stalls or times out next, this is why",
            PRE303.alert_modal_selector,
        )

    await dismiss_pre303_alert_modal_if_present(
        page,
        alert_modal_selector=PRE303.alert_modal_selector,
        alert_continue_button_text=PRE303.alert_continue_button_text,
        on_declined_hidden_modal=_log_declined_hidden_modal,
    )


async def _select_own_name_actuacion_if_present(page: Page, *, settings: Settings) -> bool:
    """Continue in own-name mode on AEAT's CarteraCuotas "tipo de actuación" selector.

    AEAT renders the representation-type choice at the wallet URL itself as two
    links — own-name (``?np=true``) and representative (``?np=false``) — followed by
    a detached Ejecutar control. The read-only driver continues only through the
    own-name link; it never follows the representative option. Returns True when the
    own-name link was present and followed, False when the page is not the
    tipo-actuación selector (so the caller proceeds to the execute gate unchanged).
    """
    try:
        link = await page.query_selector(PRE303.tipo_actuacion_own_name_link_selector)
    except PlaywrightError:
        link = None
    if link is None:
        return False
    href = await link.get_attribute("href")
    if not href:
        return False
    target = urljoin(getattr(page, "url", "") or WALLET_URL, href)
    if not is_aeat_wallet_read_url(target):
        raise SedeNavigationError(
            "AEAT cartera own-name option did not resolve to the expected wallet surface",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={
                "landing_url": redacted_url(getattr(page, "url", None)),
                "own_name_target": redacted_url(target),
            },
        )
    _assert_read_http("GET", target)
    _assert_read_browser_action(_OWN_NAME_REPRESENTATION_ACTION)
    try:
        await link.click()
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=settings.cadrumo_browser_navigation_timeout_ms)
        try:
            await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.cadrumo_browser_navigation_timeout_ms)
        except PlaywrightError:
            log.debug(
                "cartera own-name continuation did not reach networkidle current_url=%s",
                getattr(page, "url", None),
                exc_info=True,
            )
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT cartera own-name continuation failed",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"landing_url": redacted_url(getattr(page, "url", None))},
        ) from exc
    dump_dir = settings.cadrumo_wallet_diagnostic_dump_dir
    if dump_dir is not None:
        await _dump_wallet_diagnostic(page, label="post-own-name", dump_dir=dump_dir)
    return True


async def _fill_wallet_query_form(page: Page, *, target_year: int, target_period_token: str) -> None:
    """Fill AEAT's CarteraCuotas ejercicio/período query fields before the Ejecutar read query.

    The own-name CarteraCuotas form requires a target Ejercicio (year) and Período
    before it returns the prior-period pending-compensation rows; submitting empty
    fields re-renders the same shell. The taxpayer NIF field is server-prefilled to
    the authenticated identity and is never written here. Both fields are required
    when the execute gate is present; a future server-rendered shape change must
    fail closed instead of allowing a wrong/default-period read to persist.
    """
    ejercicio_selector = PRE303.wallet_ejercicio_input_selector
    periodo_selector = PRE303.wallet_periodo_input_selector
    try:
        ejercicio_field = await page.query_selector(ejercicio_selector)
        periodo_field = await page.query_selector(periodo_selector)
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT IVA wallet query fields could not be inspected before the read query",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        ) from exc
    if ejercicio_field is None or periodo_field is None:
        raise SedeNavigationError(
            "AEAT IVA wallet execute gate is missing required ejercicio/período query fields",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={"target_year": target_year, "target_period": target_period_token},
        )
    await page.fill(ejercicio_selector, str(target_year))
    await page.fill(periodo_selector, target_period_token)


async def _submit_wallet_execute_gate_if_present(
    page: Page,
    *,
    settings: Settings,
    expected_url: str,
    target_year: int,
    target_period: Period,
) -> bool:
    expected_path = urlsplit(expected_url).path
    await _select_own_name_actuacion_if_present(page, settings=settings)
    try:
        await page.wait_for_selector(
            PRE303.wallet_execute_submit_selector,
            timeout=settings.cadrumo_browser_selector_probe_timeout_ms,
        )
    except PlaywrightError:
        log.debug(
            "IVA wallet execute control was not attached before static inspection current_url=%s",
            getattr(page, "url", None),
            exc_info=True,
        )
    content = getattr(page, "content", None)
    if content is None:
        raise SedeNavigationError(
            "Playwright page does not expose content(); cannot inspect AEAT wallet execute gate",
            failure_mode=SedeFailureMode.BROWSER_BACKEND_FAILED,
        )
    try:
        html, result = await _wait_for_wallet_execute_initial_shape(
            content=content,
            expected_path=expected_path,
            timeout_ms=settings.cadrumo_browser_navigation_timeout_ms,
        )
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT IVA wallet execute gate could not be inspected",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        ) from exc
    # Every exit from here is a landing this read rests on, so the rule runs
    # before the shape is judged rather than inside one branch. It used to sit
    # only in the ``wallet-execute-submit-present`` arm below, which left the
    # other statuses -- ``no-wallet-form`` above all, what a page carrying no
    # wallet form yields, including AEAT's acting-capacity gate -- returning
    # with no landing rule run at all. The parser refused those pages anyway,
    # for want of a wallet table, but it answers "is this a wallet?" and so
    # reported a changed external shape where the truth was an undeclared
    # landing -- sending the next reader to widen the parser rather than to ask
    # why AEAT served that page. Asserting here also orders the diagnostics
    # correctly: an undeclared landing is named as one before a wallet-shaped
    # page is judged for its form action.
    _assert_read_landing(page)
    if result == "unexpected-wallet-form":
        raise SedeNavigationError(
            "AEAT IVA wallet form action did not match the expected wallet surface",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=wallet_page_shape_context(html, landing_url=getattr(page, "url", "") or ""),
        )
    if result != "wallet-execute-submit-present":
        return False
    await _run_wallet_execute_query(
        page,
        content=content,
        html=html,
        expected_path=expected_path,
        expected_url=expected_url,
        settings=settings,
        target_period=target_period,
    )
    return True


async def _run_wallet_execute_query(
    page: Page,
    *,
    content: Callable[[], Awaitable[object]],
    html: str,
    expected_path: str,
    expected_url: str,
    settings: Settings,
    target_period: Period,
) -> None:
    """Submit an executable wallet query and verify its terminal page shape."""
    # Same landed-origin question as the observation source_url, and the same
    # answer: the host that answered decides, and an origin that cannot be
    # established is refused rather than guessed.
    current_url = getattr(page, "url", "") or expected_url
    current_origin = landed_origin(getattr(page, "url", "") or "")
    if current_origin is None:
        raise SedeNavigationError(
            "AEAT IVA wallet execute gate landed on no usable origin; "
            "the host that answered cannot be established, so no "
            "submission URL can be built for this read",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        )
    submission_url = f"{current_origin}{expected_path}"
    method = wallet_execute_form_method(html)
    _assert_read_http(method, submission_url)
    _assert_read_browser_action(_WALLET_EXECUTE_READ_ACTION)
    await _fill_wallet_query_form(
        page,
        target_year=target_period.filing_year,
        target_period_token=target_period.registry_token,
    )
    diagnostic_dir = settings.cadrumo_wallet_diagnostic_dump_dir
    if diagnostic_dir is not None:
        await _dump_wallet_diagnostic(page, label="pre-execute", dump_dir=diagnostic_dir)
    try:
        await page.click(PRE303.wallet_execute_submit_selector)
        nav_timeout_ms = settings.cadrumo_browser_navigation_timeout_ms
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=nav_timeout_ms)
        try:
            await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=nav_timeout_ms)
        except PlaywrightError:
            log.debug(
                "IVA wallet execute read query did not reach networkidle current_url=%s",
                getattr(page, "url", None),
                exc_info=True,
            )
        _assert_read_landing(page)
        post_execute_html = await _wait_for_wallet_execute_terminal_shape(
            page,
            content=content,
            expected_path=expected_path,
            timeout_ms=settings.cadrumo_browser_navigation_timeout_ms,
        )
        if diagnostic_dir is not None:
            await _dump_wallet_diagnostic(page, label="post-execute", dump_dir=diagnostic_dir)
        _raise_if_wallet_terminal_shape_invalid(
            post_execute_html,
            expected_path=expected_path,
            landing_url=getattr(page, "url", "") or current_url,
        )
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT IVA wallet read query could not be completed",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={
                **wallet_page_shape_context(html, landing_url=current_url),
                "expected_url": redacted_url(expected_url),
                "blocked_operation": "wallet_execute_read_query",
            },
        ) from exc


def _raise_if_wallet_terminal_shape_invalid(
    html: str,
    *,
    expected_path: str,
    landing_url: str,
) -> None:
    if wallet_execute_gate_status(
        html, expected_path=expected_path
    ) == "wallet-execute-submit-present" and not has_wallet_table(html):
        raise SedeNavigationError(
            "AEAT IVA wallet read query left the executable wallet shell without a wallet table",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=wallet_page_shape_context(html, landing_url=landing_url),
        )


async def _wait_for_wallet_execute_initial_shape(
    *,
    content: Callable[[], Awaitable[object]],
    expected_path: str,
    timeout_ms: int,
) -> tuple[str, str]:
    deadline = now().timestamp() + timeout_ms / 1000
    last_html = await _read_wallet_html(content)
    last_status = wallet_execute_gate_status(last_html, expected_path=expected_path)
    while now().timestamp() < deadline:
        html = await _read_wallet_html(content)
        status = wallet_execute_gate_status(html, expected_path=expected_path)
        last_html = html
        last_status = status
        if status in {
            "wallet-execute-submit-present",
            "unexpected-wallet-form",
            "no-wallet-execute-submit",
        }:
            return html, status
        if has_wallet_table(html) or looks_like_executed_empty_wallet_page(parse_html(html)):
            return html, status
        await asyncio.sleep(0.5)
    return last_html, last_status


async def _wait_for_wallet_execute_terminal_shape(
    page: Page,
    *,
    content: Callable[[], Awaitable[object]],
    expected_path: str,
    timeout_ms: int,
) -> str:
    deadline = now().timestamp() + timeout_ms / 1000
    last_html = await _read_wallet_html(content)
    while now().timestamp() < deadline:
        html = await _read_wallet_html(content)
        last_html = html
        if has_wallet_table(html) or looks_like_executed_empty_wallet_page(parse_html(html)):
            return html
        if wallet_execute_gate_status(html, expected_path=expected_path) != "wallet-execute-submit-present":
            return html
        await asyncio.sleep(0.5)
    return last_html


async def _read_wallet_html(content: Callable[[], Awaitable[object]]) -> str:
    """Read a page snapshot and refuse a browser backend's non-text payload."""
    html = await content()
    if not isinstance(html, str):
        raise SedeNavigationError(
            "Playwright page content() returned a non-text payload; cannot inspect AEAT wallet",
            failure_mode=SedeFailureMode.BROWSER_BACKEND_FAILED,
        )
    return html


async def _dump_wallet_diagnostic(page: Page, *, label: str, dump_dir: Path) -> None:
    """Best-effort capture of redacted page-shape metadata for wallet DOM-drift diagnosis.

    Enabled only when :attr:`Settings.cadrumo_wallet_diagnostic_dump_dir` is set;
    callers pass that directory in as ``dump_dir``. The dump intentionally writes
    only redacted structural metadata: URL without query, table/form/input counts,
    form action paths, input identifiers, and hashes. It never writes raw HTML,
    frame HTML, screenshots, input values, or wallet amounts.
    """
    try:
        dump_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.debug("wallet diagnostic: dump dir create failed: %s", exc, exc_info=True)
        return
    context = getattr(page, "context", None)
    pages = list(getattr(context, "pages", None) or [page])
    summary: list[str] = [f"label={label}", f"page_count={len(pages)}"]
    for page_index, candidate in enumerate(pages):
        try:
            url = getattr(candidate, "url", "") or ""
            html = await candidate.content()
            shape = wallet_page_shape_context(html, landing_url=url)
            summary.append(
                f"page[{page_index}] url={shape['landing_url']} tables={shape['table_count']} "
                f"forms={shape['form_count']} wallet_entrypoints={shape['wallet_entrypoint_count']} "
                f"raw_sha256={shape['raw_sha256']}",
            )
            for form_index, form in enumerate(shape["forms"]):
                summary.append(f"page[{page_index}].form[{form_index}] {form}")
            for input_index, input_shape in enumerate(shape["inputs"]):
                summary.append(f"page[{page_index}].input[{input_index}] {input_shape}")
        except (PlaywrightError, OSError) as exc:
            summary.append(f"page[{page_index}] content_error={type(exc).__name__}")
            log.debug("wallet diagnostic: page content dump failed idx=%s: %s", page_index, exc, exc_info=True)
        for frame_index, frame in enumerate(getattr(candidate, "frames", None) or []):
            try:
                frame_url = getattr(frame, "url", "") or ""
                frame_html = await frame.content()
                frame_shape = wallet_page_shape_context(frame_html, landing_url=frame_url)
                summary.append(
                    f"page[{page_index}].frame[{frame_index}] url={frame_shape['landing_url']} "
                    f"tables={frame_shape['table_count']} forms={frame_shape['form_count']} "
                    f"raw_sha256={frame_shape['raw_sha256']}",
                )
            except (PlaywrightError, OSError) as exc:
                log.debug("wallet diagnostic: frame dump failed: %s", exc, exc_info=True)
    try:
        (dump_dir / f"{label}-summary.txt").write_text("\n".join(summary) + "\n", encoding=UTF_8_ENCODING, newline="\n")
    except OSError as exc:
        log.debug("wallet diagnostic: summary write failed: %s", exc, exc_info=True)
    log.info("wallet diagnostic captured label=%s pages=%s dir=%s", label, len(pages), dump_dir)
    prune_wallet_diagnostic_dumps(dump_dir)


def prune_wallet_diagnostic_dumps(
    dump_dir: Path,
    *,
    retention_days: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Delete wallet diagnostic dump files older than the retention window.

    The dump directory is opt-in (``cadrumo_wallet_diagnostic_dump_dir``);
    callers pass the configured directory in. ``retention_days`` defaults to
    :attr:`~core.config.Settings.cadrumo_wallet_diagnostic_retention_days`.
    Invoked automatically after each dump so the opt-in directory carries a
    declared retention lifecycle instead of accumulating stale summaries once
    captures stop. Entirely best-effort: an unenumerable directory or an
    unremovable file is logged and skipped, never raised. The survivor
    decision (age cutoff alone) delegates to the shared
    :func:`~cadrumo.core.paths.select_filesystem_retention_survivors`
    selector; the enumeration and the removal side effect stay here.

    Returns:
        Number of dump files removed.
    """
    cfg = settings or load_settings()
    effective_retention_days = (
        retention_days if retention_days is not None else cfg.cadrumo_wallet_diagnostic_retention_days
    )
    cutoff = now() - timedelta(days=effective_retention_days)
    try:
        entries = scan_directory(dump_dir, require_root=True)
    except OSError:
        log.debug("wallet diagnostic: dump dir not enumerable at %s", dump_dir, exc_info=True)
        return 0
    candidates: list[tuple[Path, datetime]] = []
    for entry in entries:
        try:
            if entry.is_file():
                candidates.append((entry, datetime.fromtimestamp(entry.stat().st_mtime, tz=UTC)))
        except OSError:
            log.debug("wallet diagnostic: could not stat dump entry %s", entry, exc_info=True)
    _keep, stale = select_filesystem_retention_survivors(
        candidates,
        timestamp=lambda pair: pair[1],
        cutoff=cutoff,
    )
    removed = 0
    for entry, _mtime in stale:
        try:
            entry.unlink()
            removed += 1
        except OSError:
            log.debug("wallet diagnostic: could not prune dump file %s", entry, exc_info=True)
    return removed


def _landed_wallet_url(page: object) -> str:
    """Return the wallet URL naming the host that actually served this read.

    AEAT dispatches an authenticated session to one of its numbered sede
    hosts, so recording a constructed URL claims the read happened
    somewhere it may not have. The observation's ``source_url`` is stored
    evidence and is what the value is defended with later, so it must name
    the host that answered.

    REFUSES when the landing is unreadable, rather than falling back to the
    unnumbered wallet URL.

    The fallback used to be defended as "the best true answer available".
    It is not an answer at all: AEAT dispatches the authenticated session
    across its numbered pool, so exactly when the landing cannot be read is
    when there is no evidence the read stayed on the unnumbered origin.
    Recording it would print a guess into the observation's ``source_url``,
    where a later reader cannot distinguish it from a measurement.

    Conforms to the censal reader, which already refused for this reason.

    Raises:
        SedeNavigationError: When the landing carries no usable scheme + host.
    """
    origin = landed_origin(getattr(page, "url", "") or "")
    if origin is None:
        raise SedeNavigationError(
            "AEAT IVA compensation wallet read landed on no usable origin; "
            "the host that answered cannot be established, so no source URL "
            "can be recorded for this observation",
        )
    return f"{origin}{WALLET_PATH}"


def assert_wallet_read_landing(landing_url: str) -> None:
    """Refuse a landing outside the four pages this wallet read traverses.

    This is the most write-adjacent driver in the package: it fills an
    ejercicio and periodo and then clicks AEAT's ``ejecutar`` SUBMIT input.
    That click issues a browser form POST which the first-party HTTP guard
    never sees and which the package's forbidden-verb source scan permits
    by design, so before this rule nothing established where the POST had
    landed. The post-execute shape check reads the returned HTML's form
    action, which is a DOM AEAT controls and says nothing about the URL
    actually served.

    The allow-list is the traversal itself, and every entry is an existing
    declared constant rather than a new claim: the Cl@ve access selector,
    AEAT's representation gate, the Pre303 presentation service, and the
    wallet path. The wallet path is additionally the surface's only
    declared read-POST path on the guard policy, so a POST landing there
    is admitted by the policy while a POST landing anywhere else is not.

    Public so the wallet's proof exercises this exact rule rather than a
    mirrored copy that would keep agreeing with itself.

    Args:
        landing_url: The URL AEAT actually served, read off the page.

    Raises:
        SedeNavigationError: When the landing is not a declared read page.
    """
    assert_read_landing(
        landing_url,
        surface="IVA compensation wallet",
        policy=IVA_COMPENSATION_WALLET_READ_POLICY,
        allowed_path_prefixes=_WALLET_READ_PATH_PREFIXES,
    )


def _assert_read_landing(page: Page) -> None:
    """Read the landed URL off ``page`` and route it through the wallet landing rule."""
    assert_wallet_read_landing(getattr(page, "url", "") or "")


def _assert_read_http(method: str, url: str) -> None:
    assert_remote_operation_allowed(
        IVA_COMPENSATION_WALLET_READ_POLICY,
        RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


def _assert_read_browser_action(action: str) -> None:
    assert_remote_operation_allowed(
        IVA_COMPENSATION_WALLET_READ_POLICY,
        RemoteOperation(kind="browser_action", action=action),
    )


__all__ = [
    "IVA_COMPENSATION_WALLET_URL",
    "PRE303_PRESENTATION_SERVICE_URL",
    "discover_iva_compensation_wallet_entrypoint",
    "fetch_iva_compensation_wallet",
    "parse_iva_compensation_wallet_html",
]
