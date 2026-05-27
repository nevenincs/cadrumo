"""Read-only AEAT IVA compensation wallet reader.

The wallet is external AEAT account state. This module only captures
and parses evidence from the authenticated Sede surface; calculation
selection happens later in the application reconciliation layer.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

from bs4 import BeautifulSoup
from pydantic import AnyHttpUrl, AnyUrl, TypeAdapter

from .....core.config import Settings
from .....core.logging import get_logger
from .....domain.calculations.registry import (
    RemoteOperation,
    RemoteStateGuardPolicy,
    assert_remote_operation_allowed,
)
from .._playwright import PlaywrightError
from ..browser import DefaultBrowserSession, default_browser_session_factory
from ._adapter_utils import normalize_response_text
from ._auth_state import storage_state_for_session
from ._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ._schema import IvaCompensationWalletObservation, IvaCompensationWalletRow

if TYPE_CHECKING:
    from .._playwright import Page
    from ..auth._authenticator import AeatSession


log = get_logger(__name__)

_ANY_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)

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
_OWN_NAME_REPRESENTATION_ACTION = "representation-gate-own-name-continue"
_WALLET_EXECUTE_READ_ACTION = "wallet-execute-read-query"
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
    """Fetch and parse AEAT's read-only IVA compensation wallet."""

    _assert_read_http("GET", _PRE303_PRESENTATION_URL)
    _assert_read_http("GET", _WALLET_URL)
    settings = settings or Settings()
    storage_state = storage_state_for_session(session)
    if session.storage_state_path is None:
        raise SedeNavigationError("AeatSession has no persisted auth session; run `aeat config auth status` first")
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
                wallet_execute_submitted = await _open_authenticated_surface(
                    page,
                    browser_session=browser_session,
                    settings=settings,
                    selector_url=_WALLET_SELECTOR_URL,
                    target_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
                    expected_url=_WALLET_URL,
                    surface="iva_compensation_wallet",
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
            try:
                return parse_iva_compensation_wallet_html(
                    html,
                    taxpayer_nif=taxpayer_nif or session.identity_nif,
                    authenticated_identity=session.identity_nif,
                    target_year=target_year,
                    target_period=target_period,
                    source_url=_WALLET_URL,
                    captured_at=datetime.now(UTC),
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
    """Parse wallet rows from a captured AEAT wallet HTML page."""

    validated_source_url = _ANY_HTTP_URL_ADAPTER.validate_python(source_url)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[IvaCompensationWalletRow] = []
    matched_wallet_table = False
    for table in soup.find_all("table"):
        header = _normalised_text(table.get_text(" "))
        if not all(token in header for token in _PRE303.iva_wallet_header_tokens):
            continue
        matched_wallet_table = True
        for table_row in table.find_all("tr"):
            cells = [_normalised_text(cell.get_text(" ")) for cell in table_row.find_all(["td", "th"])]
            if len(cells) < 5 or _looks_like_header(cells):
                continue
            try:
                rows.append(_wallet_row_from_cells(cells))
            except SedeParseError:
                raise
            except Exception as exc:
                raise SedeParseError(f"could not parse IVA compensation wallet row {cells!r}: {exc}") from exc

    if not matched_wallet_table and allow_empty_wallet_shell and _looks_like_executed_empty_wallet_page(soup):
        return IvaCompensationWalletObservation(
            taxpayer_nif=taxpayer_nif,
            authenticated_identity=authenticated_identity,
            target_year=target_year,
            target_period=target_period,
            rows=(),
            total_pending=Decimal("0"),
            source_url=validated_source_url,
            captured_at=captured_at,
            raw_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        )
    if not matched_wallet_table:
        raise SedeParseError("captured page does not contain a recognizable IVA compensation wallet table")

    total_pending = sum((row.pending_amount for row in rows), Decimal("0"))
    return IvaCompensationWalletObservation(
        taxpayer_nif=taxpayer_nif,
        authenticated_identity=authenticated_identity,
        target_year=target_year,
        target_period=target_period,
        rows=tuple(rows),
        total_pending=total_pending,
        source_url=validated_source_url,
        captured_at=captured_at,
        raw_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
    )


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
) -> bool:
    """Open an AEAT app through the selector so Cl@ve app-local state is minted."""

    _assert_read_http("GET", selector_url)
    await browser_session.navigate(page, selector_url)
    await page.wait_for_load_state("domcontentloaded")
    current_url = getattr(page, "url", "") or ""
    selector_marker = _EXTERNAL.aeat.clave_movil.selector_access_path_marker
    if selector_marker in current_url:
        _assert_read_browser_action("clave-movil-authorize")
        await page.click(_EXTERNAL.aeat.clave_movil.authorize_button_selector)
        try:
            await page.wait_for_url(
                lambda url: (
                    target_path in url
                    or is_aeat_wallet_auth_gate_redirect(url)
                    or _is_representation_gate_url(url)
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
        await page.wait_for_load_state("domcontentloaded")
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
        await page.wait_for_load_state("networkidle", timeout=settings.aeat_browser_navigation_timeout_ms)
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
        await page.wait_for_selector(
            _PRE303.representation_own_name_label_selector,
            timeout=settings.aeat_browser_selector_probe_timeout_ms,
        )
        await _dismiss_pre303_alert_modal_if_present(page)
        await page.click(_PRE303.representation_own_name_label_selector)
        await page.click(_PRE303.representation_submit_selector)
        await page.wait_for_url(
            lambda url: target_path in url or is_aeat_wallet_auth_gate_redirect(url),
            timeout=settings.aeat_browser_navigation_timeout_ms,
        )
        await page.wait_for_load_state("domcontentloaded")
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


async def _dismiss_pre303_alert_modal_if_present(page: Page) -> None:
    html = await page.content()
    modal_marker = _PRE303.alert_modal_selector.lstrip("#")
    if _PRE303.alert_modal_selector not in html and modal_marker not in html:
        return
    continue_selector = f'{_PRE303.alert_modal_selector} button:has-text("{_PRE303.alert_continue_button_text}")'
    await page.click(continue_selector)


async def _submit_wallet_execute_gate_if_present(
    page: Page,
    *,
    settings: Settings,
    expected_url: str,
) -> bool:
    expected_path = urlsplit(expected_url).path
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
        html = await content()
    except PlaywrightError as exc:
        raise SedeNavigationError(
            "AEAT IVA wallet execute gate could not be inspected",
            failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
        ) from exc
    result = _wallet_execute_gate_status(html, expected_path=expected_path)
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
        try:
            await page.click(_PRE303.wallet_execute_submit_selector)
            await page.wait_for_load_state("domcontentloaded", timeout=settings.aeat_browser_navigation_timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=settings.aeat_browser_navigation_timeout_ms)
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
            if (
                _wallet_execute_gate_status(post_execute_html, expected_path=expected_path)
                == "wallet-execute-submit-present"
                and not _has_wallet_table(post_execute_html)
            ):
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


async def _wait_for_wallet_execute_terminal_shape(
    page: Page,
    *,
    content,
    expected_path: str,
    timeout_ms: int,
) -> str:
    deadline = datetime.now(UTC).timestamp() + timeout_ms / 1000
    last_html = await content()
    while datetime.now(UTC).timestamp() < deadline:
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


def _wallet_page_shape_context(html: str, *, landing_url: str) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    forms = tuple(
        {
            "id": _bounded_text(form.get("id", "")),
            "name": _bounded_text(form.get("name", "")),
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
        }
        for input_node in soup.find_all("input")[:20]
    )
    return {
        "landing_url": _redacted_url(landing_url),
        "wallet_executed_empty_shape": _looks_like_executed_empty_wallet_page(soup),
        "heading_count": len(soup.find_all(["h1", "h2", "h3"])),
        "table_count": len(soup.find_all("table")),
        "form_count": len(soup.find_all("form")),
        "forms": forms,
        "inputs": inputs,
        "raw_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


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


def _normalised_title(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    return _bounded_text(title.get_text(" ")) if title is not None else ""


def _bounded_text(value: object, *, max_length: int = 120) -> str:
    text = " ".join(str(value).replace("\xa0", " ").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _wallet_row_from_cells(cells: list[str]) -> IvaCompensationWalletRow:
    year = _parse_year(cells[0])
    period = cells[1].strip().upper()
    if not period:
        raise SedeParseError("IVA wallet period cell is empty")
    return IvaCompensationWalletRow(
        generation_year=year,
        generation_period=period,
        generated_amount=_parse_spanish_decimal(cells[2]),
        applied_amount=_parse_spanish_decimal(cells[3]),
        pending_amount=_parse_spanish_decimal(cells[4]),
        raw_label=" | ".join(cells[:5]),
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
        raise SedeParseError("IVA wallet amount cell is empty")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise SedeParseError(f"IVA wallet amount could not be parsed from {value!r}") from exc
    if amount < Decimal("0"):
        raise SedeParseError(f"IVA wallet amount must be non-negative: {value!r}")
    return amount


def _normalised_text(value: str) -> str:
    return normalize_response_text(value).casefold()


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(cells)
    return _PRE303.iva_wallet_header_tokens[0] in joined and _PRE303.iva_wallet_header_tokens[1] in joined


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
    "fetch_iva_compensation_wallet",
    "is_aeat_wallet_auth_gate_redirect",
    "parse_iva_compensation_wallet_html",
]
