"""Pure HTML-parsing and URL-audit layer for the AEAT IVA compensation wallet.

This module is the side-effect-free half of the wallet reader: it takes
captured AEAT cartera HTML (or URLs) and returns parsed observations,
structural shape diagnostics, and host/path audit decisions. It has no
Playwright, browser-session, or navigation dependency, so the
navigation/state-machine half (``_iva_compensation_wallet``) imports from
here rather than the reverse.

The wallet URL/host constants live here too because both halves consume them;
the navigation module re-imports them so there is a single definition.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TypedDict
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from pydantic import AnyHttpUrl, TypeAdapter

from .....core.config import Settings
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n import tr
from ._adapter_utils import normalize_response_text
from ._errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ._schema import IvaCompensationWalletObservation, IvaCompensationWalletRow

_ANY_HTTP_URL_ADAPTER: TypeAdapter[AnyHttpUrl] = TypeAdapter(AnyHttpUrl)
_SPANISH_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}")

_EXTERNAL = Settings.external_constants()
_WALLET_URL = f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
_WALLET_HOST = urlsplit(_EXTERNAL.aeat.domains.www1).netloc
_WALLET_RUNTIME_HOST = urlsplit(_EXTERNAL.aeat.domains.www6).netloc
_SEDE_HOST = urlsplit(_EXTERNAL.aeat.domains.sede).netloc
_PRE303 = _EXTERNAL.aeat.pre303
_PRE303_PRESENTATION_URL = f"{_EXTERNAL.aeat.domains.www1}{_PRE303.presentation_service_path}"


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
