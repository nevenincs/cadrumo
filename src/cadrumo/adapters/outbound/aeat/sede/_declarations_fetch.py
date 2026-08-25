"""Sede declarations fetch primitives: URLs, read guards, artefact capture.

The lowest layer of the declarations register adapter — how a URL is built for
the listing and cotejo surfaces, the guards asserting a read stayed a read, the
per-interaction timeouts, and the two artefact captures that pull a row's PDF or
submitted file.

Separated from the register session so that module holds the navigation and
observation flow rather than also owning the primitives it drives. The guards
travel with the URL builders deliberately: a URL and the assertion that fetching
it did not mutate anything are one decision, and splitting them invites a new
fetch path that forgets the guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl

from .....core.config import Settings, load_settings
from .....core.external_constants import BINARY_MIME_TYPE as _BINARY_MIME_TYPE
from .....core.hashing import sha256_hex
from .....core.logging import get_logger
from .....core.time import now

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check with the registry validator. build_snapshot
# of a Modelo 100 revision fails loudly if that check is unregistered, so
# the M100 routing referential-integrity gate runs on this declarations path.
from .....domain.calculations.registry import (
    RemoteStateGuardPolicy,
)
from .._playwright import BrowserContext, Page, PlaywrightError
from ._adapter_utils import assert_pdf_response as _assert_pdf_response
from ._adapter_utils import assert_read_landing
from ._adapter_utils import landed_origin as _landed_origin
from ._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED as _WAIT_DOMCONTENTLOADED,
)
from ._browser_constants import navigation_timeout_ms as _get_navigation_timeout_ms
from ._declarations_remote import assert_read_browser_action as _remote_assert_read_browser_action
from ._declarations_remote import assert_read_http as _remote_assert_read_http
from ._declarations_remote import extract_csv_from_url as _extract_csv_from_url
from ._declarations_schema import Declaracion
from .errors import (
    JustificanteFetchError,
    SedeNavigationError,
)
from ._schema import (
    FiledDeclaracionArtefact,
)

if TYPE_CHECKING:
    pass


log = get_logger(__name__)


_EXTERNAL = Settings.external_constants()
# The one numbered host still named in a live reader, and it is measured
# rather than assumed. AEAT assigns the answering host per session, so a
# named number is normally wrong -- the censal and IVA-wallet readers name
# none. This one stays because the obvious de-pin does not work: requesting
# the declarations listing on the UNNUMBERED sede origin with a valid
# session attached returns a genuine 404, landing on the requested host
# rather than bouncing. Confirmed on a live authenticated session,
# 2026-07-26.
#
# The readers that carry no number reach their surface through the Cl@ve
# access selector and let AEAT dispatch. This module has no selector entry
# and deliberately does not get one, for two measured reasons.
#
# This host is not only a navigation string: it is also a lookup key. The
# capture path resolves its read-guard policy by matching this hostname
# against the registry's declared allowed_hosts for the declarations read
# surface, and requires exactly one match. That lookup never reads the host
# a navigation actually landed on, so routing navigation through the
# selector would change no outcome -- and de-pinning the lookup as well
# matches zero declarations and raises, failing every capture at the
# guard's own resolution step.
#
# The selector's failure path also leads nowhere better than here. Its
# reference implementation refuses outright when the selector does not
# dispatch, rather than degrading to the unnumbered origin, so that path
# reaches no host at all; and a dispatch to a host that does not serve this
# listing reaches a 404 there. Neither failure mode arrives at a host known
# to serve the route, while this constant names one that does.
#
# Recorded URLs do NOT use this constant. They name the host that actually
# answered, because a recorded URL is a claim about where a read happened.
_SEDE_BASE = _EXTERNAL.aeat.domains.www6
_SEDE_HOST = urlsplit(_SEDE_BASE).netloc
_AEAT_HOST_SUFFIX = _EXTERNAL.aeat.domains.host_suffix
_LISTING_URL = f"{_SEDE_BASE}{_EXTERNAL.aeat.sede_paths.declarations_listing}"
_LISTING_PATH = _EXTERNAL.aeat.sede_paths.declarations_listing
_COTEJO_QUERY_PATH = _EXTERNAL.aeat.sede_paths.cotejo_query
_COTEJO_DOCUMENT_PATH = _EXTERNAL.aeat.sede_paths.cotejo_document
_COTEJO_PATH_PREFIX = _EXTERNAL.aeat.sede_paths.cotejo_query


def _origin_of(landed_url: str | None) -> str:
    """Return the scheme and host a read actually landed on.

    AEAT load-balances an authenticated session across its numbered sede
    hosts: the host that answers is ASSIGNED, not chosen, and a session
    minted on one may be refused by another. A URL recorded onto stored
    evidence must therefore name the host the read actually happened on.
    Reconstructing it from a fixed host writes a false provenance claim -
    the same class of defect as a casilla carrying legal refs it was not
    derived from, and for the same reason: the record is what a value is
    defended with later.

    REFUSES when the landing is unusable, rather than falling back to the
    origin the navigation was issued against.

    That fallback used to be defended as "the best true answer available",
    and the defence does not hold. Its truth is guaranteed only in the case
    where it is never needed: AEAT load-balances the authenticated session
    across its numbered pool, so precisely when the landing cannot be read is
    when there is no evidence the read stayed on the requested host. The
    fallback is therefore a guess printed in the same field as a measurement,
    and a downstream reader cannot tell the two apart.

    An origin that cannot be established is missing evidence, and missing
    evidence must read as missing. The censal reader already refused for this
    reason; this conforms to it.

    Raises:
        SedeNavigationError: When the landing carries no usable scheme + host.
    """
    origin = _landed_origin(landed_url)
    if origin is None:
        raise SedeNavigationError(
            "AEAT declarations read landed on no usable origin "
            f"(landed URL: {landed_url!r}); the host that answered cannot be "
            "established, so no source URL can be recorded for this capture",
        )
    return origin


def _listing_url_for(origin: str, *, modelo: str, ejercicio: int) -> str:
    """Return the declarations-listing URL for one query against ``origin``."""
    return f"{origin}{_LISTING_PATH}?MODELO={modelo}&EJERCICIO={ejercicio}"


def _cotejo_view_url(origin: str, csv: str) -> str:
    """Return the cotejo view URL for ``csv`` against ``origin``."""
    return f"{origin}{_COTEJO_QUERY_PATH}?CSV={csv}"


def _cotejo_document_url(origin: str, csv: str) -> str:
    """Return the cotejo document URL for ``csv`` against ``origin``."""
    return f"{origin}{_COTEJO_DOCUMENT_PATH}?CSV={csv}"


def _get_form_interaction_timeout_ms() -> int:
    return load_settings().cadrumo_browser_form_interaction_timeout_ms


def _get_buscar_settle_ms() -> int:
    return load_settings().cadrumo_browser_buscar_settle_ms


def _get_ver_click_timeout_ms() -> int:
    return load_settings().cadrumo_browser_ver_click_timeout_ms


# AEAT dispatches the authenticated sede surface across a ``www{n}``
# load-balancer pool (www1/www2/www6/www12/sede). Pinning the read guard
# to a single host (www6) refuses a live justificante/download URL served
# from a sibling subdomain — a legitimate host-mapping drift, not a write.
# The guard therefore admits any subdomain under the AEAT apex suffix while
# success detection stays on the declarations listing/cotejo PATH prefix.
_READ_GUARD_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-declarations-read",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(_SEDE_HOST,),
    allowed_host_suffixes=(_AEAT_HOST_SUFFIX,),
    allowed_browser_action_patterns=_EXTERNAL.aeat.live_safety.declarations_browser_action_patterns,
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)


# The cotejo view a justificante popup is allowed to open on. Taken as the
# path of the configured cotejo query endpoint, which is the URL this module
# builds its own document fetch from, so the allow-list and the fetch agree
# by construction.
_COTEJO_READ_PATH_PREFIXES: tuple[str, ...] = (urlsplit(_COTEJO_PATH_PREFIX).path,)


def assert_cotejo_read_landing(
    landing_url: str,
    *,
    policy: RemoteStateGuardPolicy = _READ_GUARD_POLICY,
) -> None:
    """Refuse a justificante popup that did not land on the cotejo view.

    The Ver click opens a NEW page, so the landing is chosen entirely by
    AEAT and by whatever the row's control points at. The CSV this module
    then extracts from that URL becomes the identifier it fetches the PDF
    bytes with, and those bytes are stored as filing evidence -- so a
    landing that is not the cotejo view produces evidence attributed to a
    document nobody established.

    Args:
        landing_url: The URL the popup actually served, read off the page.
        policy: The read guard policy; defaults to the module's own.

    Raises:
        SedeNavigationError: When the popup is not on the cotejo view.
    """
    assert_read_landing(
        landing_url,
        surface="justificante cotejo",
        policy=policy,
        allowed_path_prefixes=_COTEJO_READ_PATH_PREFIXES,
    )


async def _capture_row_pdf_artefact(
    *,
    context: BrowserContext,
    row_locator,
    declaration: Declaracion,
    cell_index: int,
    kind: Literal["justificante_pdf", "declaration_pdf"],
    read_policy: RemoteStateGuardPolicy,
) -> tuple[FiledDeclaracionArtefact, bytes]:
    button = row_locator.locator(".z-listcell").nth(cell_index).locator(".z-button").first
    try:
        async with context.expect_page(timeout=_get_ver_click_timeout_ms()) as new_page_info:
            _assert_read_browser_action("open-cotejo-pdf", policy=read_policy)
            await button.click(timeout=_get_form_interaction_timeout_ms())
        cotejo_page = await new_page_info.value
    except PlaywrightError as exc:
        raise SedeNavigationError(
            f"clicking PDF artefact for {declaration.expediente_id!r} failed: {exc}",
        ) from exc

    try:
        await cotejo_page.wait_for_load_state(_WAIT_DOMCONTENTLOADED, timeout=_get_navigation_timeout_ms())
    except PlaywrightError as exc:
        raise SedeNavigationError(
            f"PDF artefact page did not settle for {declaration.expediente_id!r}: {exc}",
        ) from exc

    cotejo_url = cotejo_page.url
    # This module already refused an off-cotejo landing here, which was the
    # right instinct in the wrong shape: a substring test over the whole URL,
    # with no authority check and no answer for an unreadable landing. Routed
    # through the package landing rule it becomes a PATH allow-list, gains the
    # policy's host and write-token refusals, and refuses a popup that opened
    # with no readable URL instead of tolerating it.
    assert_cotejo_read_landing(cotejo_url, policy=read_policy)

    csv = _extract_csv_from_url(cotejo_url)
    pdf_url = AnyHttpUrl(_cotejo_document_url(_origin_of(cotejo_url), csv))
    _assert_read_http("GET", str(pdf_url), policy=read_policy)
    response = await context.request.get(str(pdf_url))
    content_type = response.headers.get("content-type", "")
    body = await response.body()
    _assert_pdf_response(
        status=response.status,
        content_type=content_type,
        body=body,
        subject=f"CSV={csv!r}",
    )
    return (
        FiledDeclaracionArtefact(
            kind=kind,
            source_url=pdf_url,
            content_type=content_type,
            byte_count=len(body),
            sha256=sha256_hex(body),
            captured_at=now(),
        ),
        body,
    )


async def _capture_submitted_file_artefact(
    *,
    context: BrowserContext,
    page: Page,
    row_locator,
    declaration: Declaracion,
    cell_index: int,
    read_policy: RemoteStateGuardPolicy,
) -> tuple[FiledDeclaracionArtefact, bytes]:
    # The click triggers a real browser download (AEAT serves the archive
    # with a Content-Disposition attachment header). Two independent things
    # keep the taxpayer's bytes off disk entirely:
    #  1. `BrowserSession._build_context_kwargs` pins `accept_downloads`
    #     False on this context, so Chromium refuses to persist the
    #     attachment at all -- measured directly:
    #     `browser/tests/test_accept_downloads_disabled.py` proves
    #     `download.path()` raises on the real production context (its own
    #     error names the flag this adapter deliberately does not set).
    #     `download.cancel()` alone would NOT be enough here: Chromium
    #     starts writing bytes to its own temp folder the instant the
    #     download begins, and cancelling only stops an in-flight transfer
    #     -- it does not retroactively un-write what already landed.
    #  2. Even so, this function never reads a download via a filesystem
    #     path (defense in depth, and the honest reason it stays cheap to
    #     re-fetch): `download.url` is read, the transfer is best-effort
    #     cancelled, and the SAME URL is fetched again in-memory through the
    #     authenticated request context -- the identical shape
    #     `_capture_row_pdf_artefact` uses for the cotejo PDF.
    # (sensitive-financial-data-secure-storage-only)
    button = row_locator.locator(".z-listcell").nth(cell_index).locator(".z-button").first
    try:
        async with page.expect_download(timeout=_get_ver_click_timeout_ms()) as download_info:
            _assert_read_browser_action("download-filed-data-file", policy=read_policy)
            await button.click(timeout=_get_form_interaction_timeout_ms())
        download = await download_info.value
    except PlaywrightError as exc:
        raise SedeNavigationError(
            f"submitted-file download for {declaration.expediente_id!r} failed: {exc}",
        ) from exc

    download_url = getattr(download, "url", None)
    try:
        await download.cancel()
    except PlaywrightError as exc:
        # Best-effort: cancellation is safe to call even on a finished or
        # already-cancelled download, so a failure here is diagnostic only
        # and must never mask the real fetch below.
        log.debug(
            "submitted-file download cancel failed for %s: %s",
            declaration.expediente_id,
            exc,
            exc_info=True,
        )

    if not isinstance(download_url, str) or not download_url:
        raise SedeNavigationError(
            f"submitted-file download for {declaration.expediente_id!r} exposed no source URL",
        )
    source_url = AnyHttpUrl(download_url)
    _assert_read_http("GET", str(source_url), policy=read_policy)
    response = await context.request.get(str(source_url))
    body = await response.body()
    if not body:
        raise JustificanteFetchError(
            f"submitted-file download for {declaration.expediente_id!r} returned an empty body",
        )
    return (
        FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=source_url,
            content_type=_BINARY_MIME_TYPE,
            byte_count=len(body),
            sha256=sha256_hex(body),
            captured_at=now(),
        ),
        body,
    )


def _assert_read_http(
    method: str,
    url: str,
    *,
    policy: RemoteStateGuardPolicy = _READ_GUARD_POLICY,
) -> None:
    _remote_assert_read_http(method, url, policy=policy)


def _assert_read_browser_action(
    action: str,
    *,
    policy: RemoteStateGuardPolicy = _READ_GUARD_POLICY,
) -> None:
    _remote_assert_read_browser_action(action, policy=policy)
