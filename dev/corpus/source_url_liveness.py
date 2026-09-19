"""Probe whether each registered ``source_url`` still resolves at its publisher.

Every ``SourceReference`` names the address its bytes came from. Nothing reads
that address after the capture, so a URL the publisher has since withdrawn goes
on looking exactly like a live one: the digest still verifies, the corpus file
is still there, and the row still reads as though a reviewer could open it.

What a withdrawal is NOT is a reason to rewrite the row. The retrieval happened,
the bytes are pinned, and the sibling gate in
``dev/registry/tests/test_bundled_artifact_facts_agree_across_sources.py`` binds
that URL to the canonical link inside the captured document itself. Editing
``source_url`` because the address 404s today would replace an observation with
a guess. Withdrawal is a fact to record beside the evidence, which is what
:data:`WITHDRAWN_SOURCE_URLS` is.

==========================================================
A naive probe reports live endpoints as dead
==========================================================

Seven registered URLs address BOE's consolidated-text open-data API, which
answers HTTP 400 to any request that does not negotiate ``application/xml`` --
``*/*`` included, which is what most clients send by default. Probing them
without that header classifies seven working endpoints as withdrawn. The header
is not restated here: :data:`~dev.corpus.fetch_boe_normative.CONSOLIDATED_TEXT_API_HEADERS`
is the acquirer's own declaration of how that API must be addressed, and this
module selects it by the same base URL the acquirer formats its requests from,
so the two cannot drift into disagreeing about one API.

``HEAD`` is tried first and ``GET`` only where the server rejects the method
itself, so a static corpus artefact is not re-downloaded to learn that it is
still there.

Run the live census with::

    uv run --no-sync pytest dev/corpus/tests/test_source_url_liveness.py -q -m aeat_live
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Final

from .fetch_boe_normative import CONSOLIDATED_TEXT_API_HEADERS, CONSOLIDATED_TEXT_API_URL

__all__ = [
    "WITHDRAWN_SOURCE_URLS",
    "LivenessOutcome",
    "UrlLiveness",
    "classify_response",
    "probe_source_urls",
    "request_headers_for",
]

_USER_AGENT: Final[str] = "cadrumo-corpus-liveness/1.0"
_CONSOLIDATED_TEXT_API_BASE: Final[str] = CONSOLIDATED_TEXT_API_URL.split("{", 1)[0]
#: Method-level refusals. The resource may be perfectly reachable by ``GET``.
_METHOD_REFUSALS: Final[frozenset[int]] = frozenset({403, 405, 501})


class UrlLiveness(Enum):
    """What one probe established about one address."""

    REACHABLE = "reachable"
    WITHDRAWN = "withdrawn"
    """The publisher answered that nothing is served there (404 / 410)."""
    REFUSED = "refused"
    """The publisher answered, but neither served nor disclaimed the resource."""
    UNREACHABLE = "unreachable"
    """No answer at all: DNS, TLS, timeout. Says nothing about the resource."""


@dataclass(frozen=True, slots=True)
class LivenessOutcome:
    """One address, what the publisher answered, and how that was read."""

    url: str
    liveness: UrlLiveness
    status: int | None
    detail: str = ""


def request_headers_for(url: str) -> Mapping[str, str]:
    """Return the headers this publisher requires to answer at all."""
    headers = {"User-Agent": _USER_AGENT}
    if url.startswith(_CONSOLIDATED_TEXT_API_BASE):
        headers.update(CONSOLIDATED_TEXT_API_HEADERS)
    return headers


def classify_response(status: int | None) -> UrlLiveness:
    """Map one answered status onto what it proves about the resource.

    Only 404 and 410 are the publisher stating that nothing is served at the
    address. Every other refusal -- a bot wall, a rate limit, a method
    rejection -- is the publisher declining to answer the question, and reading
    it as a withdrawal would invent a retirement out of a transport condition.
    """
    if status is None:
        return UrlLiveness.UNREACHABLE
    if 200 <= status < 400:
        return UrlLiveness.REACHABLE
    if status in {404, 410}:
        return UrlLiveness.WITHDRAWN
    return UrlLiveness.REFUSED


def _open(url: str, *, method: str, timeout: float) -> tuple[int | None, str]:
    request = urllib.request.Request(  # noqa: S310 - registry URLs are https publisher addresses
        url,
        method=method,
        headers=dict(request_headers_for(url)),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - as above
            return response.status, ""
    except urllib.error.HTTPError as error:
        return error.code, ""
    except OSError as error:
        return None, f"{type(error).__name__}: {error}"


def probe_source_url(url: str, *, timeout: float = 30.0) -> LivenessOutcome:
    """Ask the publisher whether it still serves ``url``."""
    status, detail = _open(url, method="HEAD", timeout=timeout)
    if status is None or status in _METHOD_REFUSALS:
        status, detail = _open(url, method="GET", timeout=timeout)
    return LivenessOutcome(url=url, liveness=classify_response(status), status=status, detail=detail)


def probe_source_urls(
    urls: Iterable[str],
    *,
    probe: Callable[[str], LivenessOutcome] = probe_source_url,
    workers: int = 6,
) -> tuple[LivenessOutcome, ...]:
    """Probe every address once, in declaration order.

    ``probe`` is injectable so the classification and census checks can be
    exercised offline; only the opt-in live test supplies the real network.
    """
    ordered = list(dict.fromkeys(urls))
    if not ordered:
        return ()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(ordered)))) as pool:
        return tuple(pool.map(probe, ordered))


WITHDRAWN_SOURCE_URLS: Final[Mapping[str, str]] = {
    "https://sede.agenciatributaria.gob.es/Sede/en_gb/todas-gestiones/impuestos-tasas/"
    "declaraciones-informativas/modelo-289-decla_informativa-anual-cuentas-financieras_/"
    "gestiones/servicio-web-presentacion-modelo-289.html": (
        "AEAT retired the English-language modelo 289 web-service page after capture"
    ),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/"
    "archivos_20/126v01e2020_v1.07.xlsx": (
        "AEAT withdrew the modelo 126 design workbook from its static file tree after capture"
    ),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/"
    "archivos_20/128v01e2020_v1.07.xlsx": (
        "AEAT withdrew the modelo 128 design workbook from its static file tree after capture"
    ),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/"
    "DR202e25.xlsx": ("AEAT replaced the modelo 202 ejercicio-2025 workbook at a different address"),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/"
    "archivos/303_2025.xlsx": ("AEAT replaced the modelo 303 ejercicio-2025 workbook at a different address"),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/"
    "archivos/390_2025.xlsx": ("AEAT replaced the modelo 390 ejercicio-2025 workbook at a different address"),
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Tema/Procedimientos_tributarios/"
    "Declaraciones_informativas/Modelos_200_299/289/XSD/289_XSD_2.0_WSDL_2.0.1.zip": (
        "AEAT withdrew the modelo 289 XSD/WSDL bundle at this version-pinned address"
    ),
    "https://www.boe.es/datos/imagenes/disp/2008/277/18497_11330375_image3.png": (
        "BOE withdrew the scanned annex image the modelo 296 text was transcribed from"
    ),
}
"""Addresses whose publisher answered that nothing is served there any more.

This is a CENSUS, checked for equality by the opt-in live test, not an
allowlist that suppresses a class. An address that starts 404ing fails that
test until it is entered here with a reason; an address that comes back fails
it until the entry is removed. Every member is held in the bundled corpus under
a hash-pinned source row, which is what makes the withdrawal recordable rather
than a loss -- a withdrawn address with no bytes behind it would be an
acquisition task, not a census entry.
"""
