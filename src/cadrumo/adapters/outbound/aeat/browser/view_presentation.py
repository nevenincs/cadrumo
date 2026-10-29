"""Private-data-safe presentation of browser view state and person input."""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

from pydantic import ValidationError

from cadrumo_client.contracts.view_stream import (
    VIEW_MAX_PATH_LENGTH,
    VIEW_MAX_TITLE_LENGTH,
    PointerAction,
    PointerInput,
    ViewClose,
    ViewInput,
    ViewNavigate,
    ViewPageSecurity,
    ViewPhase,
    ViewSinkInput,
    ViewState,
    WheelInput,
)
from cadrumo_client.contracts.view_transfer import VIEW_MAX_FILENAME_LENGTH

from .....core.remote_authority import canonical_remote_hostname, is_current_aeat_host

_FALLBACK_FILENAME: Final[str] = "download"
_UNSAFE_FILENAME_CHARACTERS: Final[frozenset[str]] = frozenset({"/", "\\", "\x7f"})


def safe_filename(suggested: str) -> str:
    """Return ``suggested`` as a plain file name the save dialog may offer, never a path."""
    name = "".join(
        "_" if character in _UNSAFE_FILENAME_CHARACTERS or ord(character) < 0x20 else character
        for character in suggested
    ).strip()
    name = name[:VIEW_MAX_FILENAME_LENGTH]
    return _FALLBACK_FILENAME if name in {"", ".", ".."} else name


def interrupts_assisted_login(item: ViewSinkInput) -> bool:
    """Whether the person's ``item`` stops an assisted login: anything but a pointer move, a wheel or a resize."""
    if isinstance(item, ViewInput):
        event = item.event
        if isinstance(event, WheelInput):
            return False
        return not (isinstance(event, PointerInput) and event.action is PointerAction.MOVE)
    return isinstance(item, ViewNavigate | ViewClose)


def is_aeat_page(url: str) -> bool:
    """Whether a page belongs to the current AEAT authority."""
    host = canonical_remote_hostname(url)
    return host is not None and is_current_aeat_host(host)


def view_state(url: str, title: str, *, back: bool, forward: bool, loading: bool, phase: ViewPhase) -> ViewState:
    """Return the state of the page at ``url``, whatever page it is.

    An https page is stated by its origin and path, which the toolbar shows.
    The page's whole ``url`` rides along as the host-only address when the
    contract admits it, and is left out otherwise. Any other page is stated by
    its marker alone: ``insecure`` for an ``http:`` page, ``unknown`` for one
    whose origin cannot be stated. Either way the host learns that the person
    left the page it held.
    """

    def state(security: ViewPageSecurity, origin: str | None, path: str | None, address: str | None) -> ViewState:
        return ViewState(
            security=security,
            origin=origin,
            path=path,
            address=address,
            title=title[:VIEW_MAX_TITLE_LENGTH],
            can_go_back=back,
            can_go_forward=forward,
            loading=loading,
            phase=phase,
        )

    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return state(ViewPageSecurity.UNKNOWN, None, None, None)
    if parts.scheme == "http":
        return state(ViewPageSecurity.INSECURE, None, None, None)
    if parts.scheme != "https" or host is None or host == "":
        return state(ViewPageSecurity.UNKNOWN, None, None, None)
    netloc = host if port is None else f"{host}:{port}"
    path = (parts.path or "/")[:VIEW_MAX_PATH_LENGTH]
    for address in (url, None):
        try:
            return state(ViewPageSecurity.SECURE, f"https://{netloc.lower()}", path, address)
        except ValidationError:
            continue
    return state(ViewPageSecurity.UNKNOWN, None, None, None)
