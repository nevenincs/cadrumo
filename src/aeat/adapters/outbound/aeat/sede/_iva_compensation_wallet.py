"""Read-only AEAT IVA compensation wallet reader.

The wallet is external AEAT account state. This module only captures
and parses evidence from the authenticated Sede surface; calculation
selection happens later in the application reconciliation layer.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl, AnyUrl, TypeAdapter

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
from ._adapter_utils import normalize_response_text
from ._auth_state import storage_state_for_session
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._browser_constants import (
    PLAYWRIGHT_WAIT_NETWORKIDLE as _WAIT_NETWORKIDLE,
)
from ._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ._schema import IvaCompensationWalletObservation, IvaCompensationWalletRow

if TYPE_CHECKING:
    from .._playwright import Page
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_ANY_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
_SPANISH_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}")

_EXTERNAL = Settings.external_constants()
_WALLET_URL = f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
_WALLET_HOST = urlsplit(_EXTERNAL.aeat.domains.www1).netloc
_WALLET_RUNTIME_HOST = urlsplit(_EXTERNAL.aeat.domains.www6).netloc
_SEDE_HOST = urlsplit(_EXTERNAL.aeat.domains.sede).netloc
_PRE303 = _EXTERNAL.aeat.pre303
_PRE303_PRESENTATION_URL = f"{_EXTERNAL.aeat.domains.www1}{_PRE303.presentation_service_path}"
_PRE303_SELECTOR_URL = _EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(_PRE303.presentation_service_path, safe="")
)
_WALLET_SELECTOR_URL = _EXTERNAL.aeat.clave_movil.selector_access_url_template.format(
    target=quote(_EXTERNAL.aeat.sede_paths.iva_compensation_wallet, safe="")
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
    target_period: str,
    taxpayer_nif: str | None = None,
    settings: Settings | None = None,
) -> IvaCompensationWalletObservation:
    """Fetch and parse AEAT's read-only IVA compensation wallet as a :class:`IvaCompensationWalletObservation`."""
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
                    target_year=target_year,
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
                        target_year=target_year,
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
                        target_year=target_year,
                        target_period=target_period,
                    )
            except PlaywrightError as exc:
                raise SedeNavigationError(
                    f"Pre303/wallet navigation failed for {_PRE303_PRESENTATION_URL!r} -> {_WALLET_URL!r}: {exc}"
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
                    target_year=target_year,
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


def parse_iva_compensation_wallet_html(
    html: str,
    *,
    taxpayer_nif: str,
    authenticated_identity: str,
    target_year: int,
    target_period: str,
    source_url: str,
    captured_at: datetime,
    allow_empty_wallet_shell: bool = False,
) -> IvaCompensationWalletObservation:
    """Parse wallet rows and the total from a captured AEAT cartera HTML page.

    Returns a :class:`IvaCompensationWalletObservation` with the aggregate and per-period detail rows.

    The own-name "Cartera de cuotas de IVA a compensar" results view carries an
    authoritative aggregate — the "Cuotas a compensar pendientes de períodos
    anteriores" line — plus a detail table (``Ejercicio`` / ``Período`` /
    ``Cuota Disponible``) itemising the still-available balance per generation
    period. The aggregate is the contract value surfaced as ``total_pending``;
    the detail rows are cross-checked against it so a parse drift cannot silently
    under-declare. A genuinely empty wallet renders the same aggregate line at
    ``0,00`` with no detail rows.
    """
    validated_source_url = _ANY_HTTP_URL_ADAPTER.validate_python(source_url)
    soup = BeautifulSoup(html, "html.parser")
    summary_total = _parse_wallet_summary_total(soup)
    rows, matched_wallet_table = _parse_wallet_result_rows(soup)
    _assert_wallet_result_target_matches(soup, target_year=target_year, target_period=target_period)

    if summary_total is None and not matched_wallet_table:
        if allow_empty_wallet_shell and _looks_like_executed_empty_wallet_page(soup):
            raise SedeParseError(
                "executed IVA wallet shell does not contain AEAT's explicit zero aggregate; "
                "refusing to persist a synthetic zero wallet observation"
            )
        raise SedeParseError("captured page does not contain a recognizable IVA compensation wallet table")

    row_sum = sum((row.pending_amount for row in rows), Decimal("0"))
    if summary_total is not None and rows and summary_total != row_sum:
        raise SedeParseError(
            f"IVA wallet summary total {summary_total} does not equal the sum of Cuota Disponible rows {row_sum}; "
            "refusing to persist an inconsistent wallet observation"
        )
    total_pending = summary_total if summary_total is not None else row_sum
    return IvaCompensationWalletObservation(
        taxpayer_nif=taxpayer_nif,
        authenticated_identity=authenticated_identity,
        target_year=target_year,
        target_period=target_period,
        rows=tuple(rows),
        total_pending=total_pending,
        source_url=validated_source_url,
        captured_at=captured_at,
        raw_sha256=hashlib.sha256(html.encode(UTF_8_ENCODING)).hexdigest(),
    )


def _parse_wallet_result_rows(soup: BeautifulSoup) -> tuple[list[IvaCompensationWalletRow], bool]:
    """Parse the cartera detail table rows and whether a wallet table was matched.

    Matches the AEAT results table by its normalised column headers
    (``Ejercicio`` / ``Período`` / ``Cuota Disponible``) and reads each data row
    (header ``<th>`` rows are skipped). Returns the parsed rows plus a flag
    indicating the wallet table was present, so the caller distinguishes an empty
    wallet (table absent, aggregate ``0,00``) from an unrecognised page.
    """
    rows: list[IvaCompensationWalletRow] = []
    matched_wallet_table = False
    for table in soup.find_all("table"):
        header = _normalised_text(table.get_text(" "))
        if not all(token in header for token in _PRE303.iva_wallet_header_tokens):
            continue
        matched_wallet_table = True
        for table_row in table.find_all("tr"):
            if table_row.find_all("th"):
                continue
            cells = [_normalised_text(cell.get_text(" ")) for cell in table_row.find_all("td")]
            if len(cells) < 3:
                continue
            try:
                rows.append(_wallet_row_from_cells(cells))
            except SedeParseError:
                raise
            except Exception as exc:
                raise SedeParseError(f"could not parse IVA compensation wallet row {cells!r}: {exc}") from exc
    return rows, matched_wallet_table


def _parse_wallet_summary_total(soup: BeautifulSoup) -> Decimal | None:
    """Return AEAT's authoritative "pendientes de períodos anteriores" aggregate, or None.

    The cartera results view prints the binding total on a single labelled line
    (``Cuotas a compensar pendientes de períodos anteriores: <amount>``). The
    smallest element carrying both label tokens and a Spanish-decimal amount is
    used, so the value is read from its own line rather than summed from the
    detail table.
    """
    label_tokens = _PRE303.iva_wallet_total_label_tokens
    for node in soup.find_all(["li", "p", "span", "div"]):
        text = node.get_text(" ")
        if not all(token in _normalised_text(text) for token in label_tokens):
            continue
        amount = _extract_spanish_amount(text)
        if amount is not None:
            return amount
    return None


def _assert_wallet_result_target_matches(soup: BeautifulSoup, *, target_year: int, target_period: str) -> None:
    """Fail closed when AEAT renders result target labels that do not match the requested query."""
    rendered_year, rendered_period = _parse_wallet_result_target(soup)
    if rendered_year is not None and rendered_year != target_year:
        raise SedeParseError(
            f"IVA wallet result exercise {rendered_year} does not match requested exercise {target_year}"
        )
    if rendered_period is not None and rendered_period != target_period.strip().upper():
        raise SedeParseError(
            f"IVA wallet result period {rendered_period!r} does not match requested period {target_period!r}"
        )


def _parse_wallet_result_target(soup: BeautifulSoup) -> tuple[int | None, str | None]:
    rendered_year: int | None = None
    rendered_period: str | None = None
    ejercicio_token = _PRE303.iva_wallet_header_tokens[0]
    periodo_token = _PRE303.iva_wallet_header_tokens[1]
    for node in soup.find_all(["li", "p", "div"]):
        strong = node.find("strong")
        if strong is None:
            continue
        label = _normalised_text(strong.get_text(" "))
        if _is_wallet_result_label(label, ejercicio_token):
            text = _wallet_label_value_text(node, strong)
            if text:
                rendered_year = _parse_year(text)
        elif _is_wallet_result_label(label, periodo_token):
            text = _wallet_label_value_text(node, strong)
            if text:
                rendered_period = text.strip().upper()
    return rendered_year, rendered_period


def _is_wallet_result_label(label: str, token: str) -> bool:
    return label.replace(":", " ").strip() == token


def _wallet_label_value_text(node: Tag, label_node: Tag) -> str:
    span = node.find("span")
    if span is not None:
        return _normalised_display_text(span.get_text(" "))
    node_text = node.get_text(" ")
    label_text = label_node.get_text(" ")
    return _normalised_display_text(node_text.replace(label_text, "", 1).replace(":", " "))


def discover_iva_compensation_wallet_entrypoint(html: str, *, base_url: str) -> str | None:
    """Return AEAT's Pre303-provided wallet URL when the authenticated page exposes one."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(["a", "form"]):
        raw_url = node.get("href") if node.name == "a" else node.get("action")
        if not raw_url:
            continue
        candidate = _absolute_audited_wallet_url(str(raw_url), base_url=base_url)
        if candidate is not None:
            return candidate
    return None


def is_aeat_wallet_auth_gate_redirect(current_url: str) -> bool:
    """Return True when wallet navigation lands on AEAT's certificate/auth 4033 page."""
    if not current_url:
        return False
    parsed = urlsplit(current_url)
    host = parsed.netloc.casefold()
    host_suffix = _EXTERNAL.aeat.domains.host_suffix.casefold()
    if host != host_suffix and not host.endswith(f".{host_suffix}"):
        return False
    auth_gate_marker = _EXTERNAL.aeat.sede_paths.auth_gate_4033.casefold()
    return auth_gate_marker in parsed.path.casefold()


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
    target_period: str,
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
            target_year=target_year,
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
    target_period: str,
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
        target_year=target_year,
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


def _assert_own_name_representation_form_html(html: str, *, landing_url: str, expected_path: str) -> None:
    soup = BeautifulSoup(html, "html.parser")
    submit = soup.select_one(_PRE303.representation_submit_selector)
    if submit is None:
        raise SedeNavigationError(
            "AEAT representation gate does not expose the configured own-name submit control",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=_representation_gate_context(html, landing_url=landing_url),
        )
    form = submit.find_parent("form")
    if form is None:
        raise SedeNavigationError(
            "AEAT representation submit control is not inside a form",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=_representation_gate_context(html, landing_url=landing_url),
        )
    method = str(form.get("method", "GET")).strip().upper() or "GET"
    action = urljoin(landing_url or _PRE303_PRESENTATION_URL, str(form.get("action", "")))
    parsed_action = urlsplit(action)
    if not _own_name_representation_action_allowed(
        method=method,
        action_path=parsed_action.path,
        action_host=parsed_action.netloc,
        landing_url=landing_url,
        expected_path=expected_path,
    ):
        raise SedeNavigationError(
            "AEAT representation form boundary changed before own-name continuation",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={
                **_representation_gate_context(html, landing_url=landing_url),
                "form_method": method,
                "form_action_path": parsed_action.path,
            },
        )
    own_name = soup.select_one(_PRE303.representation_own_name_selector)
    representative = soup.select_one(_PRE303.representation_representative_selector)
    if own_name is None or representative is None:
        raise SedeNavigationError(
            "AEAT representation gate does not expose both own-name and representative controls",
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context=_representation_gate_context(html, landing_url=landing_url),
        )
    if _input_checked(representative):
        raise SedeNavigationError(
            "AEAT representation gate has representative mode selected; refusing to continue",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context=_representation_gate_context(html, landing_url=landing_url),
            suggestion="Use only the authenticated profile user's own-name access for read-only wallet capture.",
        )
    represented_fields = tuple(
        str(node.get("name") or node.get("id") or "")
        for node in soup.find_all("input")
        if str(node.get("name") or node.get("id") or "").casefold() in {"nif", "nombre"}
        and str(node.get("value") or "").strip()
    )
    if represented_fields:
        raise SedeNavigationError(
            "AEAT representation gate carries represented-taxpayer text fields; refusing to continue",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            context={
                **_representation_gate_context(html, landing_url=landing_url),
                "represented_fields": represented_fields,
            },
            suggestion="Use only the authenticated profile user's own-name access for read-only wallet capture.",
        )


def _own_name_representation_action_allowed(
    *,
    method: str,
    action_path: str,
    action_host: str,
    landing_url: str,
    expected_path: str,
) -> bool:
    if not _is_allowed_wallet_host(action_host):
        return False
    if method == "POST" and action_path == expected_path:
        return True
    landing_path = urlsplit(landing_url).path
    dialogo_path = _EXTERNAL.aeat.clave_movil.dialogo_representacion_path
    return method == "GET" and landing_path == dialogo_path and action_path == dialogo_path


def _representation_gate_context(html: str, *, landing_url: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    forms = tuple(
        {
            "id": _bounded_text(form.get("id", "")),
            "method": _bounded_text(form.get("method", "")),
            "action_path": urlsplit(str(form.get("action", ""))).path,
        }
        for form in soup.find_all("form")[:8]
    )
    inputs = tuple(
        {
            "id": _bounded_text(input_node.get("id", "")),
            "name": _bounded_text(input_node.get("name", "")),
            "type": _bounded_text(input_node.get("type", "")),
            "checked": _input_checked(input_node),
        }
        for input_node in soup.find_all("input")[:20]
    )
    return {"landing_url": _redacted_url(landing_url), "forms": forms, "inputs": inputs}


def _input_checked(node: object) -> bool:
    get = getattr(node, "get", None)
    if get is None:
        return False
    checked = get("checked")
    return checked is not None and str(checked).casefold() not in {"", "false", "0", "none"}


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


async def _fill_wallet_query_form(page: Page, *, target_year: int, target_period: str) -> None:
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
            context={"target_year": target_year, "target_period": target_period},
        )
    await page.fill(ejercicio_selector, str(target_year))
    await page.fill(periodo_selector, str(target_period))


async def _submit_wallet_execute_gate_if_present(
    page: Page,
    *,
    settings: Settings,
    expected_url: str,
    target_year: int,
    target_period: str,
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
        await _fill_wallet_query_form(page, target_year=target_year, target_period=target_period)
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
                post_execute_html, expected_path=expected_path
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


def _wallet_execute_gate_status(html: str, *, expected_path: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one(_PRE303.wallet_form_selector)
    if form is None:
        return "no-wallet-form"
    action_path = urlsplit(str(form.get("action", ""))).path
    if action_path != expected_path:
        return "unexpected-wallet-form"
    submit = form.select_one(_PRE303.wallet_execute_submit_selector) or soup.select_one(
        _PRE303.wallet_execute_submit_selector
    )
    if submit is None:
        return "no-wallet-execute-submit"
    return "wallet-execute-submit-present"


def _wallet_execute_form_method(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one(_PRE303.wallet_form_selector)
    if form is None:
        return "GET"
    method = str(form.get("method", "GET")).strip().upper()
    return method or "GET"


def _has_wallet_table(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        header = _normalised_text(table.get_text(" "))
        if all(token in header for token in _PRE303.iva_wallet_header_tokens):
            return True
    return False


class _WalletFormShape(TypedDict):
    id: str
    name: str
    method: str
    action_path: str


class _WalletInputShape(TypedDict):
    id: str
    name: str
    type: str


class _WalletPageShape(TypedDict):
    landing_url: str | None
    wallet_executed_empty_shape: bool
    heading_count: int
    table_count: int
    form_count: int
    wallet_entrypoint_count: int
    wallet_entrypoint_paths: tuple[str, ...]
    forms: tuple[_WalletFormShape, ...]
    inputs: tuple[_WalletInputShape, ...]
    raw_sha256: str


def _wallet_page_shape_context(html: str, *, landing_url: str) -> _WalletPageShape:
    soup = BeautifulSoup(html, "html.parser")
    wallet_entrypoints = tuple(
        entrypoint
        for entrypoint in (
            _wallet_entrypoint_path(str(node.get("href") if node.name == "a" else node.get("action") or ""))
            for node in soup.find_all(["a", "form"])[:40]
        )
        if entrypoint is not None
    )
    forms: tuple[_WalletFormShape, ...] = tuple(
        _WalletFormShape(
            id=_bounded_text(form.get("id", "")),
            name=_bounded_text(form.get("name", "")),
            method=_bounded_text(form.get("method", "")),
            action_path=urlsplit(str(form.get("action", ""))).path,
        )
        for form in soup.find_all("form")[:8]
    )
    inputs: tuple[_WalletInputShape, ...] = tuple(
        _WalletInputShape(
            id=_bounded_text(input_node.get("id", "")),
            name=_bounded_text(input_node.get("name", "")),
            type=_bounded_text(input_node.get("type", "")),
        )
        for input_node in soup.find_all("input")[:20]
    )
    return _WalletPageShape(
        landing_url=_redacted_url(landing_url),
        wallet_executed_empty_shape=_looks_like_executed_empty_wallet_page(soup),
        heading_count=len(soup.find_all(["h1", "h2", "h3"])),
        table_count=len(soup.find_all("table")),
        form_count=len(soup.find_all("form")),
        wallet_entrypoint_count=len(wallet_entrypoints),
        wallet_entrypoint_paths=wallet_entrypoints[:8],
        forms=forms,
        inputs=inputs,
        raw_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
    )


def _redacted_url(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if not parsed.scheme and not parsed.netloc:
        return parsed.path
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _absolute_audited_wallet_url(raw_url: str, *, base_url: str) -> str | None:
    try:
        candidate = urljoin(base_url, raw_url)
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.path != _EXTERNAL.aeat.sede_paths.iva_compensation_wallet:
        return None
    if not _is_allowed_wallet_host(parsed.netloc):
        return None
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{query}"


def _wallet_entrypoint_path(raw_url: str) -> str | None:
    try:
        path = urlsplit(raw_url).path
    except ValueError:
        return None
    if path == _EXTERNAL.aeat.sede_paths.iva_compensation_wallet:
        return path
    return None


def _is_allowed_wallet_host(netloc: str) -> bool:
    host = netloc.casefold()
    return host in {
        _WALLET_HOST.casefold(),
        _WALLET_RUNTIME_HOST.casefold(),
        _SEDE_HOST.casefold(),
    }


def _normalised_title(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    return _bounded_text(title.get_text(" ")) if title is not None else ""


def _bounded_text(value: object, *, max_length: int = 120) -> str:
    text = " ".join(str(value).replace("\xa0", " ").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _wallet_row_from_cells(cells: list[str]) -> IvaCompensationWalletRow:
    """Build one wallet row from a cartera detail row: Ejercicio, Período, Cuota Disponible.

    The AEAT cartera consultation surface exposes only the still-available balance
    per generation period, so ``pending_amount`` carries the "Cuota Disponible"
    cell and the generated/applied movement columns stay ``None``.
    """
    year = _parse_year(cells[0])
    period = cells[1].strip().upper()
    if not period:
        raise SedeParseError(
            "IVA wallet period cell is empty",
            translated_message=tr("adapters.sede.errors.iva_wallet_empty_period_cell"),
        )
    return IvaCompensationWalletRow(
        generation_year=year,
        generation_period=period,
        pending_amount=_parse_spanish_decimal(cells[2]),
        raw_label=" | ".join(cells[:3]),
    )


def _parse_year(value: str) -> int:
    match = re.search(r"\b(20[0-9]{2})\b", value)
    if match is None:
        raise SedeParseError(f"IVA wallet generation year could not be parsed from {value!r}")
    return int(match.group(1))


def _parse_spanish_decimal(value: str) -> Decimal:
    cleaned = value.replace("\xa0", " ").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned:
        raise SedeParseError(
            "IVA wallet amount cell is empty",
            translated_message=tr("adapters.sede.errors.iva_wallet_empty_amount_cell"),
        )
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise SedeParseError(f"IVA wallet amount could not be parsed from {value!r}") from exc
    if amount < Decimal("0"):
        raise SedeParseError(f"IVA wallet amount must be non-negative: {value!r}")
    return amount


def _extract_spanish_amount(text: str) -> Decimal | None:
    """Return the last Spanish-decimal amount embedded in ``text`` (e.g. ``123,45``), or None.

    Used to read AEAT's aggregate "pendientes de períodos anteriores" line, where the
    amount trails a textual label on the same element.
    """
    matches = _SPANISH_AMOUNT_RE.findall(text.replace("\xa0", " "))
    if not matches:
        return None
    return _parse_spanish_decimal(matches[-1])


def _normalised_text(value: str) -> str:
    return normalize_response_text(value).casefold()


def _normalised_display_text(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _looks_like_executed_empty_wallet_page(soup: BeautifulSoup) -> bool:
    title_and_heading = _normalised_text(
        f"{_normalised_title(soup)} {' '.join(node.get_text(' ') for node in soup.find_all(['h1', 'h2']))}"
    )
    if not all(token in title_and_heading for token in _PRE303.iva_wallet_empty_page_tokens):
        return False
    has_wallet_form = False
    for form in soup.find_all("form"):
        action_path = urlsplit(str(form.get("action", ""))).path
        if action_path != _EXTERNAL.aeat.sede_paths.iva_compensation_wallet:
            continue
        has_wallet_form = True
        if any(_is_wallet_execute_submit(input_node) for input_node in form.find_all("input")):
            return False
    return has_wallet_form and not any(_is_wallet_execute_submit(input_node) for input_node in soup.find_all("input"))


def _is_wallet_execute_submit(input_node: object) -> bool:
    get = getattr(input_node, "get", None)
    if get is None:
        return False
    return (
        str(get("id", "")).casefold() == "ejecutar"
        and str(get("name", "")).casefold() == "ejecutar"
        and str(get("type", "")).casefold() == "submit"
    )


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
                f"raw_sha256={shape['raw_sha256']}"
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
                    f"raw_sha256={frame_shape['raw_sha256']}"
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
