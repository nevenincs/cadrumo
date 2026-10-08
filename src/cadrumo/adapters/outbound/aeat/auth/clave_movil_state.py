"""Observed Cl@ve Móvil page states, independent of navigation history."""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .....core.config import Settings
from .....core.external_constants import AeatClaveMovilSurface
from .....core.remote_authority import canonical_remote_hostname, is_current_aeat_host
from .._html import parse_html
from ._clave_provider_common import is_authenticated_clave_landing


class ClaveMovilPageState(StrEnum):
    """States on which the browser driver can safely act."""

    SELECTOR = "selector"
    QR = "qr"
    IDENTITY = "identity"
    WAITING = "waiting"
    REPRESENTATION = "representation"
    AUTHENTICATED = "authenticated"
    PENDING = "pending"
    UNKNOWN = "unknown"
    UNTRUSTED = "untrusted"


def _classify_text_state(
    *,
    path: str,
    text: str,
    surface: AeatClaveMovilSurface,
) -> ClaveMovilPageState | None:
    if any(marker.casefold() in text for marker in surface.pending_petition_text_markers):
        return ClaveMovilPageState.PENDING
    if surface.dialogo_representacion_path_marker in path:
        return ClaveMovilPageState.REPRESENTATION
    return None


def _classify_form_state(*, soup: BeautifulSoup, surface: AeatClaveMovilSurface) -> ClaveMovilPageState | None:
    if soup.select_one(surface.authorize_button_selector) is not None:
        return ClaveMovilPageState.SELECTOR
    if soup.select_one(surface.nif_input_selector) is not None:
        return ClaveMovilPageState.IDENTITY
    if soup.select_one(surface.verification_code_selector) is not None:
        return ClaveMovilPageState.WAITING
    return None


def classify_clave_movil_page(*, url: str, html: str, target_path: str, settings: Settings) -> ClaveMovilPageState:
    """Classify trusted page structure without exposing its content or credentials."""
    host = canonical_remote_hostname(url)
    if host is None or not is_current_aeat_host(host):
        return ClaveMovilPageState.UNTRUSTED
    surface = settings.external_constants().aeat.clave_movil
    path = urlsplit(url).path
    soup = parse_html(html)
    text = " ".join(soup.get_text(" ", strip=True).casefold().split())
    textual_state = _classify_text_state(path=path, text=text, surface=surface)
    if textual_state is not None:
        return textual_state
    form_state = _classify_form_state(soup=soup, surface=surface)
    if form_state is not None:
        return form_state
    if soup.select_one(surface.non_qr_link_selector) is not None:
        return ClaveMovilPageState.QR
    if is_authenticated_clave_landing(
        landing_url=url,
        target_path=target_path,
        settings=settings,
        clave_path_markers=(
            surface.selector_access_path_marker,
            surface.dialogo_representacion_path_marker,
            surface.obtener_clave_movil_path_marker,
            surface.obtener_clave_movil_qr_path_marker,
            surface.cancelar_clave_movil_path_marker,
        ),
    ):
        return ClaveMovilPageState.AUTHENTICATED
    return ClaveMovilPageState.UNKNOWN
