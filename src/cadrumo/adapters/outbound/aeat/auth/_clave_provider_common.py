"""Provider-neutral mechanics shared by the two Cl@ve authentication flows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from .....application.auth.protocols import BrowserContextPort, BrowserSessionPort
from .....core.config import Settings
from .....core.remote_authority import canonical_remote_hostname, is_current_aeat_host
from .browser_lifecycle import close_owned_browser_context, close_owned_browser_session

if TYPE_CHECKING:
    from logging import Logger


def default_sede_target_url(settings: Settings) -> str:
    """Return the shared authenticated AEAT Sede target for a Cl@ve flow."""
    external = settings.external_constants()
    return f"{external.aeat.domains.www6}{external.aeat.sede_paths.expedientes_resumen}"


def verification_probe_url(
    *,
    explicit_target_url: str | None,
    resolved_target_url: str | None,
    target_path: str,
    selector_url_for: Callable[[str], str],
) -> str:
    """Choose the probe URL without changing provider-specific selector construction."""
    if explicit_target_url:
        return selector_url_for(target_path)
    if resolved_target_url and target_path in resolved_target_url:
        return resolved_target_url
    return resolved_target_url or selector_url_for(target_path)


def is_authenticated_clave_landing(
    *,
    landing_url: str,
    target_path: str,
    settings: Settings,
    clave_path_markers: Iterable[str],
) -> bool:
    """Return True for a protected AEAT page reached after Cl@ve dispatch.

    The authority is decided by the canonical remote-authority helpers, never
    by ``urlsplit(...).netloc``: that string still ends in the AEAT suffix when
    a credential prefix rides in front of it, so
    ``https://evil@www6.agenciatributaria.gob.es/`` would read as a protected
    landing. Only the current AEAT apex counts. Each provider supplies the
    Cl@ve path markers of its own flow, which are still mid-login rather than
    landed; the auth gate is refused for every provider.
    """
    host = canonical_remote_hostname(landing_url)
    if host is None or not is_current_aeat_host(host):
        return False
    path = urlsplit(landing_url).path.casefold()
    if settings.external_constants().aeat.sede_paths.auth_gate_4033.casefold() in path:
        return False
    if any(marker.casefold() in path for marker in clave_path_markers):
        return False
    if urlsplit(target_path).path.casefold() == path:
        return True
    return same_aeat_application_path(landing_path=path, target_path=target_path)


def same_aeat_application_path(*, landing_path: str, target_path: str) -> bool:
    """Return whether a landing path is inside the target's ``wlpl`` or ``sede`` application.

    The first two segments must match; any other root, or fewer than two
    segments on either side, fails closed.
    """
    target_path_only = urlsplit(target_path).path.casefold()
    landing_parts = tuple(part for part in landing_path.split("/") if part)
    target_parts = tuple(part for part in target_path_only.split("/") if part)
    if len(landing_parts) < 2 or len(target_parts) < 2:
        return False
    if target_parts[0] in {"wlpl", "sede"}:
        return landing_parts[:2] == target_parts[:2]
    return False


# KWARGS-ANY-RATIONALE-LOGGER-DUCK-TYPE: callers pass either a stdlib
# logging.Logger or a structured logger wrapper that is duck-type
# compatible but does not satisfy the Logger protocol statically.
async def close_clave_context(
    context: BrowserContextPort | None,
    *,
    settings: Settings,
    logger: Logger | Any,
    owner: str,
) -> bool:
    """Close one Cl@ve-owned context using its configured bounded timeout."""
    return await close_owned_browser_context(
        context,
        timeout_ms=settings.cadrumo_browser_close_timeout_ms,
        logger=logger,
        owner=owner,
    )


# KWARGS-ANY-RATIONALE-LOGGER-DUCK-TYPE: see close_clave_context above.
async def close_clave_browser_session(
    session: BrowserSessionPort | None,
    *,
    settings: Settings,
    logger: Logger | Any,
    owner: str,
) -> bool:
    """Close one Cl@ve-owned browser session using its configured bounded timeout."""
    return await close_owned_browser_session(
        session,
        timeout_ms=settings.cadrumo_browser_close_timeout_ms,
        logger=logger,
        owner=owner,
    )
