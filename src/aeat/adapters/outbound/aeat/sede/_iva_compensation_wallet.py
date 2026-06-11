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
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup
from pydantic import AnyUrl

from .....core import Period
from .....core.config import Settings
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import now
from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .._playwright import PlaywrightError
from ..browser import DefaultBrowserSession, default_browser_session_factory
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_NETWORKIDLE as _WAIT_NETWORKIDLE,
)
from ._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ._iva_compensation_wallet_parsing import (
    _EXTERNAL,
    _PRE303,
    _SEDE_HOST,
    _WALLET_HOST,
    _WALLET_RUNTIME_HOST,
    _WALLET_URL,
    _assert_own_name_representation_form_html,
    _has_wallet_table,
    _is_allowed_wallet_host,
    _looks_like_executed_empty_wallet_page,
    _redacted_url,
    _wallet_execute_form_method,
    _wallet_execute_gate_status,
    _wallet_page_shape_context,
    discover_iva_compensation_wallet_entrypoint,
    is_aeat_wallet_auth_gate_redirect,
    parse_iva_compensation_wallet_html,
)
from ._schema import IvaCompensationWalletObservation

if TYPE_CHECKING:
    from .._playwright import Page
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_PRE303_PRESENTATION_URL = f"{_EXTERNAL.aeat.domains.www1}{_PRE303.presentation_service_path}"
_PRE303_SELECTOR_URL = _EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(_PRE303.presentation_service_path, safe=""),
)
_WALLET_SELECTOR_URL = _EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(_EXTERNAL.aeat.sede_paths.iva_compensation_wallet, safe=""),
)
_OWN_NAME_REPRESENTATION_ACTION = _PRE303.representation_own_name_action_label
_WALLET_DISCOVERED_ENTRYPOINT_ACTION = _PRE303.wallet_discovered_entrypoint_action_label
_WALLET_EXECUTE_READ_ACTION = _PRE303.wallet_execute_read_action_label
IVA_COMPENSATION_WALLET_URL = _WALLET_URL
PRE303_PRESENTATION_SERVICE_URL = _PRE303_PRESENTATION_URL
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-iva-compensation-wallet-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_WALLET_HOST, _WALLET_RUNTIME_HOST, _SEDE_HOST),
    allowed_read_post_paths=(_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.wallet_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
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
    if target_period.filing_year != target_year:
        raise SedeNavigationError(
            "IVA wallet target_year does not match target_period.year",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={"target_year": target_year, "target_period_year": target_period.filing_year},
        )
    _assert_read_http("GET", _PRE303_PRESENTATION_URL)
    _assert_read_http("GET", _WALLET_URL)
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    if session.storage_state_path is None:
        raise SedeNavigationError(
            "AeatSession has no persisted auth session; run `aeat config auth status` first",
            translated_message=tr("adapters.sede.errors.no_auth_session"),
        )
    browser_session = await default_browser_session_factory(settings)
    try:
        context = await browser_session.create_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            try:
                await _open_authenticated_surface(
                    page,
                    browser_session=browser_session,
                    settings=settings,
                    selector_url=_PRE303_SELECTOR_URL,
                    target_path=_PRE303.presentation_service_path,
                    expected_url=_PRE303_PRESENTATION_URL,
                    surface="pre303_presentation_service",
                    target_year=target_period.filing_year,
                    target_period=target_period,
                )
                if is_aeat_wallet_auth_gate_redirect(page.url):
                    raise SedeNavigationError(
                        "AEAT Pre303 presentation surface rejected the authenticated session with 4033",
                        failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                        context={
                            "landing_url": _redacted_url(page.url),
                            "expected_url": _redacted_url(_PRE303_PRESENTATION_URL),
                            "surface": "pre303_presentation_service",
                        },
                        suggestion=(
                            "Authenticate specifically for the Pre303 presentation service before reading "
                            "the IVA compensation wallet."
                        ),
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
                        target_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
                        expected_url=_WALLET_URL,
                        surface="iva_compensation_wallet",
                        target_year=target_period.filing_year,
                        target_period=target_period,
                    )
            except PlaywrightError as exc:
                raise SedeNavigationError(
                    f"Pre303/wallet navigation failed for {_PRE303_PRESENTATION_URL!r} -> {_WALLET_URL!r}: {exc}",
                ) from exc
            if is_aeat_wallet_auth_gate_redirect(page.url):
                raise SedeNavigationError(
                    "AEAT IVA compensation wallet rejected the authenticated session with 4033",
                    failure_mode=SedeFailureMode.AUTH_GATE_DETECTED,
                    context={
                        "landing_url": _redacted_url(page.url),
                        "expected_url": _redacted_url(_WALLET_URL),
                        "surface": "iva_compensation_wallet",
                    },
                    suggestion=(
                        "Authenticate specifically for the Pre303 presentation service, then retry the "
                        "read-only wallet capture."
                    ),
                )
            html = await page.content()
            final_dump_dir = settings.aeat_wallet_diagnostic_dump_dir
            if final_dump_dir is not None:
                await _dump_wallet_diagnostic(page, label="final-parse-input", dump_dir=final_dump_dir)
            try:
                return parse_iva_compensation_wallet_html(
                    html,
                    taxpayer_nif=taxpayer_nif or session.identity_nif,
                    authenticated_identity=session.identity_nif,
                    target_year=target_period.filing_year,
                    target_period=target_period,
                    source_url=_WALLET_URL,
                    captured_at=now(),
                    allow_empty_wallet_shell=wallet_execute_submitted,
                )
            except SedeParseError as exc:
                raise SedeParseError(
                    str(exc),
                    failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                    context=_wallet_page_shape_context(html, landing_url=page.url),
                    suggestion=(
                        "Inspect the captured AEAT wallet page shape and update the read-only parser or "
                        "navigation chain; do not hard-code operator wallet values into tests."
                    ),
                ) from exc
        finally:
            try:
                await context.close()
            except Exception as exc:
                log.debug("fetch_iva_compensation_wallet: context.close suppressed: %s", exc, exc_info=True)
    finally:
        await browser_session.close()


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
    """Open an AEAT app through the selector so Cl@ve app-local state is minted."""
    _assert_read_http("GET", selector_url)
    await browser_session.navigate(page, selector_url)
    await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
    current_url = getattr(page, "url", "") or ""
    selector_marker = _EXTERNAL.aeat.clave_movil.selector_access_path_marker
    if selector_marker in current_url:
        _assert_read_browser_action("clave-movil-authorize")
        await page.click(_EXTERNAL.aeat.clave_movil.authorize_button_selector)
        try:
            await page.wait_for_url(
                lambda url: (
                    target_path in url or is_aeat_wallet_auth_gate_redirect(url) or _is_representation_gate_url(url)
                ),
                timeout=settings.aeat_browser_navigation_timeout_ms,
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
        await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.aeat_browser_navigation_timeout_ms)
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
    return _EXTERNAL.aeat.clave_movil.dialogo_representacion_path_marker in path


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
            expected_url=_WALLET_URL,
            target_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
            surface="iva_compensation_wallet",
        )
    try:
        await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.aeat_browser_navigation_timeout_ms)
    except PlaywrightError:
        log.debug(
            "Discovered IVA wallet entrypoint did not reach networkidle current_url=%s",
            getattr(page, "url", None),
            exc_info=True,
        )
    return await _submit_wallet_execute_gate_if_present(
        page,
        settings=settings,
        expected_url=_WALLET_URL,
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
        await page.click(_PRE303.representation_submit_selector)
        await page.wait_for_url(
            lambda url: target_path in url or is_aeat_wallet_auth_gate_redirect(url),
            timeout=settings.aeat_browser_navigation_timeout_ms,
        )
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED)
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT representation gate did not expose the own-name continuation expected for the "
            "authenticated profile user.",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={
                "landing_url": _redacted_url(getattr(page, "url", None)),
                "expected_url": _redacted_url(expected_url),
                "surface": surface,
                "blocked_operation": "representative_or_unknown_representation_gate",
            },
            suggestion="Do not provide represented-third-party data through this driver.",
        ) from exc


async def _wait_for_own_name_representation_selector(page: Page, *, settings: Settings) -> str:
    last_error: PlaywrightError | None = None
    for selector in _own_name_representation_selectors(
        _PRE303.representation_own_name_label_selector,
        _PRE303.representation_own_name_selector,
    ):
        try:
            await page.wait_for_selector(selector, timeout=settings.aeat_browser_selector_probe_timeout_ms)
            return selector
        except PlaywrightError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise SedeNavigationError(
        "AEAT own-name representation selector configuration is empty",
        failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
    )


def _own_name_representation_selectors(*selectors: str) -> tuple[str, ...]:
    deduped: list[str] = []
    for selector in selectors:
        value = selector.strip()
        if value and value not in deduped:
            deduped.append(value)
    return tuple(deduped)


async def _assert_own_name_representation_form(page: Page, *, expected_path: str) -> None:
    html = await page.content()
    _assert_own_name_representation_form_html(
        html,
        landing_url=getattr(page, "url", "") or "",
        expected_path=expected_path,
    )


async def _dismiss_pre303_alert_modal_if_present(page: Page) -> None:
    html = await page.content()
    modal_marker = _PRE303.alert_modal_selector.lstrip("#")
    if _PRE303.alert_modal_selector not in html and modal_marker not in html:
        return
    continue_selector = f'{_PRE303.alert_modal_selector} button:has-text("{_PRE303.alert_continue_button_text}")'
    await page.click(continue_selector)


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
        link = await page.query_selector(_PRE303.tipo_actuacion_own_name_link_selector)
    except PlaywrightError:
        link = None
    if link is None:
        return False
    href = await link.get_attribute("href")
    if not href:
        return False
    target = urljoin(getattr(page, "url", "") or _WALLET_URL, href)
    parsed = urlsplit(target)
    if parsed.path != _EXTERNAL.aeat.sede_paths.iva_compensation_wallet or not _is_allowed_wallet_host(parsed.netloc):
        raise SedeNavigationError(
            "AEAT cartera own-name option did not resolve to the expected wallet surface",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={
                "landing_url": _redacted_url(getattr(page, "url", None)),
                "own_name_target": _redacted_url(target),
            },
        )
    _assert_read_http("GET", target)
    _assert_read_browser_action(_OWN_NAME_REPRESENTATION_ACTION)
    try:
        await link.click()
        await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=settings.aeat_browser_navigation_timeout_ms)
        try:
            await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.aeat_browser_navigation_timeout_ms)
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
            context={"landing_url": _redacted_url(getattr(page, "url", None))},
        ) from exc
    dump_dir = settings.aeat_wallet_diagnostic_dump_dir
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
    ejercicio_selector = _PRE303.wallet_ejercicio_input_selector
    periodo_selector = _PRE303.wallet_periodo_input_selector
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
            _PRE303.wallet_execute_submit_selector,
            timeout=settings.aeat_browser_selector_probe_timeout_ms,
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
            timeout_ms=settings.aeat_browser_navigation_timeout_ms,
        )
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT IVA wallet execute gate could not be inspected",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        ) from exc
    if result == "unexpected-wallet-form":
        raise SedeNavigationError(
            "AEAT IVA wallet form action did not match the expected wallet surface",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=_wallet_page_shape_context(html, landing_url=getattr(page, "url", "") or ""),
        )
    if result == "wallet-execute-submit-present":
        current_url = getattr(page, "url", "") or expected_url
        current = urlsplit(current_url)
        submission_url = f"{current.scheme}://{current.netloc}{expected_path}"
        method = _wallet_execute_form_method(html)
        _assert_read_http(method, submission_url)
        _assert_read_browser_action(_WALLET_EXECUTE_READ_ACTION)
        await _fill_wallet_query_form(
            page,
            target_year=target_period.filing_year,
            target_period_token=target_period.registry_token,
        )
        _diag_dump_dir = settings.aeat_wallet_diagnostic_dump_dir
        if _diag_dump_dir is not None:
            await _dump_wallet_diagnostic(page, label="pre-execute", dump_dir=_diag_dump_dir)
        try:
            await page.click(_PRE303.wallet_execute_submit_selector)
            await page.wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=settings.aeat_browser_navigation_timeout_ms)
            try:
                await page.wait_for_load_state(_WAIT_NETWORKIDLE, timeout=settings.aeat_browser_navigation_timeout_ms)
            except PlaywrightError:
                log.debug(
                    "IVA wallet execute read query did not reach networkidle current_url=%s",
                    getattr(page, "url", None),
                    exc_info=True,
                )
            post_execute_html = await _wait_for_wallet_execute_terminal_shape(
                page,
                content=content,
                expected_path=expected_path,
                timeout_ms=settings.aeat_browser_navigation_timeout_ms,
            )
            if _diag_dump_dir is not None:
                await _dump_wallet_diagnostic(page, label="post-execute", dump_dir=_diag_dump_dir)
            if _wallet_execute_gate_status(
                post_execute_html, expected_path=expected_path,
            ) == "wallet-execute-submit-present" and not _has_wallet_table(post_execute_html):
                raise SedeNavigationError(
                    "AEAT IVA wallet read query left the executable wallet shell without a wallet table",
                    failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
                    context=_wallet_page_shape_context(
                        post_execute_html,
                        landing_url=getattr(page, "url", "") or current_url,
                    ),
                    suggestion=(
                        "Treat this as an incomplete wallet read, not an empty wallet. Inspect the structural "
                        "diagnostic before accepting zero compensation evidence."
                    ),
                )
        except PlaywrightError as exc:
            raise SedeNavigationError(
                "AEAT IVA wallet read query could not be completed",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
                context={
                    **_wallet_page_shape_context(html, landing_url=current_url),
                    "expected_url": _redacted_url(expected_url),
                    "blocked_operation": "wallet_execute_read_query",
                },
                suggestion=(
                    "Inspect the structural wallet shape diagnostic; do not provide or hard-code live "
                    "taxpayer wallet values."
                ),
            ) from exc
        return True
    return False


async def _wait_for_wallet_execute_initial_shape(
    *,
    content,
    expected_path: str,
    timeout_ms: int,
) -> tuple[str, str]:
    deadline = now().timestamp() + timeout_ms / 1000
    last_html = await content()
    last_status = _wallet_execute_gate_status(last_html, expected_path=expected_path)
    while now().timestamp() < deadline:
        html = await content()
        status = _wallet_execute_gate_status(html, expected_path=expected_path)
        last_html = html
        last_status = status
        if status in {
            "wallet-execute-submit-present",
            "unexpected-wallet-form",
            "no-wallet-execute-submit",
        }:
            return html, status
        if _has_wallet_table(html) or _looks_like_executed_empty_wallet_page(BeautifulSoup(html, "html.parser")):
            return html, status
        await asyncio.sleep(0.5)
    return last_html, last_status


async def _wait_for_wallet_execute_terminal_shape(
    page: Page,
    *,
    content,
    expected_path: str,
    timeout_ms: int,
) -> str:
    deadline = now().timestamp() + timeout_ms / 1000
    last_html = await content()
    while now().timestamp() < deadline:
        html = await content()
        last_html = html
        if _has_wallet_table(html) or _looks_like_executed_empty_wallet_page(BeautifulSoup(html, "html.parser")):
            return html
        if _wallet_execute_gate_status(html, expected_path=expected_path) != "wallet-execute-submit-present":
            return html
        await asyncio.sleep(0.5)
    return last_html


async def _dump_wallet_diagnostic(page: Page, *, label: str, dump_dir: Path) -> None:
    """Best-effort capture of redacted page-shape metadata for wallet DOM-drift diagnosis.

    Enabled only when :attr:`Settings.aeat_wallet_diagnostic_dump_dir` is set;
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
            shape = _wallet_page_shape_context(html, landing_url=url)
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
                frame_shape = _wallet_page_shape_context(frame_html, landing_url=frame_url)
                summary.append(
                    f"page[{page_index}].frame[{frame_index}] url={frame_shape['landing_url']} "
                    f"tables={frame_shape['table_count']} forms={frame_shape['form_count']} "
                    f"raw_sha256={frame_shape['raw_sha256']}",
                )
            except (PlaywrightError, OSError) as exc:
                log.debug("wallet diagnostic: frame dump failed: %s", exc, exc_info=True)
    try:
        (dump_dir / f"{label}-summary.txt").write_text("\n".join(summary) + "\n", encoding=UTF_8_ENCODING)
    except OSError as exc:
        log.debug("wallet diagnostic: summary write failed: %s", exc, exc_info=True)
    log.info("wallet diagnostic captured label=%s pages=%s dir=%s", label, len(pages), dump_dir)


def _assert_read_http(method: str, url: str) -> None:
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="http", method=method, url=AnyUrl(url)),
    )


def _assert_read_browser_action(action: str) -> None:
    assert_remote_operation_allowed(
        _READ_GUARD_POLICY,
        RemoteOperation(kind="browser_action", action=action),
    )


__all__ = [
    "IVA_COMPENSATION_WALLET_URL",
    "PRE303_PRESENTATION_SERVICE_URL",
    "discover_iva_compensation_wallet_entrypoint",
    "fetch_iva_compensation_wallet",
    "is_aeat_wallet_auth_gate_redirect",
    "parse_iva_compensation_wallet_html",
]
