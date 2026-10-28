"""The NIF of the person signed in to an AEAT session, read from *Mis Expedientes*.

*Mis Expedientes* (``/wlpl/TEWV-CORE/ResumenVlt``) is the protected page every
provider's landing probe already targets. Requested with no parameters, it
heads the page with *Persona consultada: <NIF> - <name>*. The request names no
taxpayer, so the NIF AEAT shows there is the one its session belongs to, not one
the caller asked for. That is what the other Sede readers rely on as well: none
of them names a taxpayer, so each reads the signed-in person's own data.

The censal consulta cannot answer this question. It takes the taxpayer to show
as ``nifRepresentado``, and a representative holding a power of attorney for
that taxpayer may be served the taxpayer's consulta.

The page is requested in a page of a Cadrumo-owned context, under this module's
read guard, and every landing that is not *Mis Expedientes* is refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from .....core.async_cleanup import close_async_resources
from .....core.config import Settings
from .....domain.calculations.registry.remote_state_guard import RemoteStateGuardPolicy
from .....domain.calculations.registry.schema_base import EvidenceTier
from .._html import parse_html
from .._playwright import PlaywrightError
from ._adapter_utils import (
    assert_landed_url_readable,
    assert_read_http_for,
    assert_read_landing,
    redacted_url,
    require_playwright_page,
)
from ._browser_constants import PLAYWRIGHT_WAIT_DOMCONTENTLOADED
from .errors import SedeFailureMode, SedeNavigationError

if TYPE_CHECKING:
    from .....application.auth.protocols import BrowserContextPort

EXTERNAL = Settings.external_constants()
_EXPEDIENTES_ORIGIN = EXTERNAL.aeat.domains.www6
_EXPEDIENTES_PATH = EXTERNAL.aeat.sede_paths.expedientes_resumen
_EXPEDIENTES_URL: Final = f"{_EXPEDIENTES_ORIGIN}{_EXPEDIENTES_PATH}"
_SURFACE: Final = "Mis Expedientes"
# The label AEAT puts before the NIF and name of the person the page is about.
_PERSONA_CONSULTADA_LABEL: Final = "persona consultada:"

# AEAT may move the session across its ``www{n}`` pool, as it does for the
# censal and notifications reads, so the host is widened to the AEAT apex. The
# path stays exact: only *Mis Expedientes* itself is a read this module makes.
READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-signed-in-identity-read",
    evidence_tier=EvidenceTier.OFFICIAL_SOURCE_GUIDANCE,
    classification="authenticated_read_surface",
    allowed_hosts=(urlsplit(_EXPEDIENTES_ORIGIN).netloc,),
    allowed_host_suffixes=(EXTERNAL.aeat.domains.host_suffix,),
    allowed_read_paths=(_EXPEDIENTES_PATH,),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)


def parse_signed_in_nif(html: str) -> str | None:
    """Return the NIF *Mis Expedientes* shows as *Persona consultada*, or ``None`` when it shows none.

    Args:
        html: The page AEAT served.

    Returns:
        The first token after the label, which AEAT renders as ``<NIF> - <name>``.
    """
    document = parse_html(html)
    for label in document.find_all("strong"):
        if label.get_text(" ", strip=True).casefold() != _PERSONA_CONSULTADA_LABEL:
            continue
        value = label.find_next_sibling("span")
        if value is None:
            return None
        tokens = value.get_text(" ", strip=True).split()
        return tokens[0] if tokens else None
    return None


async def read_signed_in_nif(context: BrowserContextPort) -> str | None:
    """Return the NIF of the person the session in ``context`` belongs to.

    The page is opened and closed by this call. Any landing other than *Mis
    Expedientes*, such as the access selector, a Cl@ve login, the 4033 gate or
    the representation dialog, raises :class:`SedeNavigationError`.

    Args:
        context: A Cadrumo-owned browser context seeded with the session to read.

    Returns:
        The NIF AEAT shows as *Persona consultada*, or ``None`` when it shows none.
    """
    assert_read_http_for(READ_GUARD_POLICY, "GET", _EXPEDIENTES_URL)
    page = require_playwright_page(await context.new_page())
    try:
        try:
            await page.goto(_EXPEDIENTES_URL, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)
        except PlaywrightError as exc:
            raise SedeNavigationError(
                f"{_SURFACE} navigation failed ({type(exc).__name__}) for {redacted_url(_EXPEDIENTES_URL)}",
                failure_mode=SedeFailureMode.LIVE_NAVIGATION_FAILED,
            ) from exc
        landing_url = assert_landed_url_readable(page.url, requested_url=_EXPEDIENTES_URL)
        assert_read_landing(
            landing_url,
            surface=_SURFACE,
            policy=READ_GUARD_POLICY,
            allowed_path_prefixes=(_EXPEDIENTES_PATH,),
        )
        html = await page.content()
    finally:
        await close_async_resources(page, task_name="cadrumo-signed-in-identity-page-close")
    return parse_signed_in_nif(html)


__all__ = ["READ_GUARD_POLICY", "parse_signed_in_nif", "read_signed_in_nif"]
