"""Provider-neutral mechanics shared by the two Cl@ve authentication flows."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .....application.auth.protocols import BrowserContextPort, BrowserSessionPort
from .....core.config import Settings
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
