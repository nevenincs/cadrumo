"""The normative acquirer refuses anything but the consolidated text in force.

Driven against the payloads this repo already bundles, not against synthetic
markup. That matters here more than usual: the defect this module exists to
prevent is bundling repealed law under a current filename, and a hand-written
fixture would encode whatever version-selector shape its author imagined rather
than the one BOE actually emits. A bundled "article fragment" turns out not to
be a fragment at all -- it carries the full ``act.php`` selector markup, the
bloque markers and the hidden document id -- so the ground truth was in the tree.

The two payloads are deliberately different shapes: ``ley-37-1992-art-90`` is
single-block with five versions, and ``boe-a-2024-12944`` is multi-block with
blocks legitimately sitting at DIFFERENT versions. Only the second can
distinguish a per-fieldset invariant from a document-wide one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from http import HTTPStatus
from pathlib import Path
from typing import Final

import httpx
import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT
from ..corpus.fetch_boe_normative import (
    NormativeAcquisitionError,
    assert_boe_holds_no_consolidated_text,
    assert_served_by_the_requested_endpoint,
    assert_serves_the_published_document,
    assert_serves_the_text_in_force,
    canonical_lf_bytes,
    version_selections,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CORPUS: Final[Path] = REPO_ROOT / "src/cadrumo/_data/corpus/normatives/html"
_SINGLE_BLOCK: Final[str] = "ley-37-1992-art-90.html"
_MULTI_BLOCK: Final[str] = "boe-a-2024-12944-rdl-4-2024-iva-alimentos.html"
#: The as-published shape: BOE holds no consolidated text for a corrección
#: de errores, so this is the only view of it that exists.
_AS_PUBLISHED: Final[str] = "correccion-errores-real-decreto-ley-6-2024.html"


def _payload(name: str) -> str:
    path = _CORPUS / name
    if not path.is_file():
        pytest.fail(f"bundled payload {name} is missing; this module's ground truth has moved")
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_bundled_payloads_carry_a_version_selector_at_all() -> None:
    """Anti-vacuity: if nothing parses, every assertion below agrees with everything.

    Scoped to "both payloads", not "at least one", because the multi-block case
    is what makes the per-fieldset invariant testable and a silent regression to
    single-block-only would leave that assertion unexercised while still green.
    """
    single = version_selections(_payload(_SINGLE_BLOCK))
    multi = version_selections(_payload(_MULTI_BLOCK))

    assert single, "no version selector parsed from the single-block payload"
    assert multi, "no version selector parsed from the multi-block payload"
    assert len(multi) > 1, (
        "the multi-block payload now parses as a single bloque, so the per-fieldset invariant "
        "is no longer distinguishable from a document-wide one and this module has stopped "
        "checking the thing it exists for"
    )


def test_the_multi_block_payload_really_does_hold_blocks_at_different_versions() -> None:
    """The property that makes a document-wide maximum wrong, asserted not assumed.

    If every bloque ever sat at the same version, a document-wide check and a
    per-fieldset check would agree forever and the distinction would be
    untestable. This is the fixture-anchor: it fails if the payload is replaced
    by one that no longer discriminates.
    """
    selections = version_selections(_payload(_MULTI_BLOCK))

    checked = {selection.checked for selection in selections}
    assert len(checked) > 1, (
        f"every bloque is checked at the same version {checked}; this payload can no longer "
        "distinguish a per-fieldset invariant from a document-wide maximum"
    )


def test_both_bundled_payloads_are_accepted_as_the_text_in_force() -> None:
    """The positive control: real, correct payloads must pass.

    The multi-block one is the load-bearing half -- a document-wide maximum
    would REFUSE it, because two of its blocks legitimately remain at the
    earlier version the later amendment did not touch.
    """
    assert assert_serves_the_text_in_force(_payload(_SINGLE_BLOCK), document_id="BOE-A-1992-28740")
    assert assert_serves_the_text_in_force(_payload(_MULTI_BLOCK), document_id="BOE-A-2024-12944")


def test_a_payload_serving_a_superseded_redaction_is_refused() -> None:
    """The defect this module exists to prevent, driven from a real payload.

    Rather than inventing markup, the checked marker is moved onto the OLDEST
    offered version of a genuine payload -- which is exactly what "take the last
    listed version" would have selected, since BOE lists newest first.
    """
    payload = _payload(_SINGLE_BLOCK)
    selections = version_selections(payload)
    served, oldest = selections[0].checked, min(selections[0].offered)
    assert served != oldest, "payload's newest and oldest versions coincide; cannot build the case"

    superseded = payload.replace(f'value="{served}" checked', f'value="{served}"').replace(
        f'value="{oldest}"', f'value="{oldest}" checked', 1
    )

    with pytest.raises(NormativeAcquisitionError, match="superseded redaction"):
        assert_serves_the_text_in_force(superseded, document_id="BOE-A-1992-28740")


def test_a_payload_for_a_different_document_is_refused() -> None:
    """A clean 200 from the right host is not evidence it is the right norm."""
    with pytest.raises(NormativeAcquisitionError, match="not the requested"):
        assert_serves_the_text_in_force(_payload(_SINGLE_BLOCK), document_id="BOE-A-2024-12944")


def test_a_payload_with_no_version_selector_is_refused() -> None:
    """A single historical redaction has no selector, and must not pass as consolidated."""
    stripped = _payload(_SINGLE_BLOCK).replace("<fieldset", "<div").replace("</fieldset>", "</div>")

    with pytest.raises(NormativeAcquisitionError, match="no version selector"):
        assert_serves_the_text_in_force(stripped, document_id="BOE-A-1992-28740")


# ── the endpoint that answered, which no payload check can establish ────────


def test_the_requested_endpoint_serving_its_own_payload_is_accepted() -> None:
    """The precision half. A query string legitimately differs and must not refuse.

    BOE echoes and reorders parameters, so a comparison including the query
    would refuse correct responses -- which is how a guard gets switched off
    rather than fixed.
    """
    assert_served_by_the_requested_endpoint(
        final_url="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740&tn=1",
        requested_url="https://www.boe.es/buscar/act.php",
    )


def test_a_redirect_to_the_single_document_view_is_refused() -> None:
    """The measured case, and the reason this check exists at all.

    A live request to the consolidated ``act.php`` endpoint silently redirected
    to ``doc.php``, the single-document view, and the identity check PASSED --
    because ``doc.php`` echoes the requested id in the same form input. An
    identity check that reads the id back out of a response verifies the
    REQUEST, never the SOURCE.

    Only the version-selector check refused that payload, and for an unrelated
    reason: a single-document view offers no versions. It would not have caught
    a redirect landing on something version-bearing.
    """
    with pytest.raises(NormativeAcquisitionError, match="rather than the requested"):
        assert_served_by_the_requested_endpoint(
            final_url="https://www.boe.es/buscar/doc.php?id=BOE-A-1992-28740",
            requested_url="https://www.boe.es/buscar/act.php",
        )


def test_a_different_host_is_refused() -> None:
    """A mirror or an interception answers the same path over a clean 200."""
    with pytest.raises(NormativeAcquisitionError):
        assert_served_by_the_requested_endpoint(
            final_url="https://mirror.example.org/buscar/act.php?id=BOE-A-1992-28740",
            requested_url="https://www.boe.es/buscar/act.php",
        )


def test_a_downgraded_scheme_is_refused() -> None:
    """Legal text acquired over a downgraded scheme is text nobody can vouch for."""
    with pytest.raises(NormativeAcquisitionError):
        assert_served_by_the_requested_endpoint(
            final_url="http://www.boe.es/buscar/act.php",
            requested_url="https://www.boe.es/buscar/act.php",
        )


def test_the_article_endpoint_accepts_its_own_block_path() -> None:
    """The article arm carries the block in the PATH, so the check must not over-refuse."""
    url = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1992-28740/texto/bloque/a90"
    assert_served_by_the_requested_endpoint(final_url=url, requested_url=url)


def test_the_article_endpoint_refuses_a_different_block_path() -> None:
    """And a redirect that moved the block is a different article, not a detail."""
    with pytest.raises(NormativeAcquisitionError):
        assert_served_by_the_requested_endpoint(
            final_url="https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1992-28740/texto/bloque/a91",
            requested_url="https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1992-28740/texto/bloque/a90",
        )


def test_the_as_published_view_is_accepted_as_itself() -> None:
    """The bundled corrección de errores is the ground truth for the doc.php shape."""
    assert_serves_the_published_document(_payload(_AS_PUBLISHED), document_id="BOE-A-2024-24097")


def test_an_as_published_payload_for_a_different_document_is_refused() -> None:
    """Identity rests on the server-emitted canonical link, which names the endpoint too."""
    with pytest.raises(NormativeAcquisitionError, match="canonical URL"):
        assert_serves_the_published_document(_payload(_AS_PUBLISHED), document_id="BOE-A-2024-24096")


def test_a_consolidated_payload_is_refused_by_the_as_published_arm() -> None:
    """A consolidated page declares act.php as its canonical view, so it refuses here.

    Driven against a real consolidated payload rather than a hand-written one.
    Note what this does NOT prove: the refusal fires because the CANONICAL LINK
    names the wrong endpoint, not because the page is consolidated. BOE will
    serve a doc.php view of that same consolidated norm whose canonical link is
    correct, and this function accepts it -- which is exactly why
    ``fetch_published_document`` also probes act.php before writing anything.
    """
    with pytest.raises(NormativeAcquisitionError, match="canonical URL"):
        assert_serves_the_published_document(_payload(_MULTI_BLOCK), document_id="BOE-A-2024-12944")


def _boe_endpoint(routes: Mapping[str, tuple[int, bytes]]) -> Callable[..., list[bytes]]:
    """Return a WSGI endpoint serving ``routes`` keyed by request path.

    A real HTTP endpoint handler, not a test double: it is mounted under a real
    :class:`httpx.Client` and answers real requests, so redirect following,
    status handling and ``response.url`` resolution are httpx's own. That is
    the point -- the guard under test reads the FINAL url after redirects, and
    a substitute that returned a canned response object would assert the
    substitute's redirect logic rather than the client's.

    A ``302`` route's body is the ``Location`` header.
    """

    def endpoint(environ: dict[str, object], start_response: Callable[..., object]) -> list[bytes]:
        path = str(environ["PATH_INFO"])
        status, body = routes[path]
        if status == HTTPStatus.FOUND:
            start_response("302 Found", [("Location", body.decode("ascii"))])
            return [b""]
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [body]

    return endpoint


def _boe_client(routes: Mapping[str, tuple[int, bytes]]) -> httpx.Client:
    """A real httpx client whose transport runs the in-process BOE endpoint."""
    return httpx.Client(
        transport=httpx.WSGITransport(app=_boe_endpoint(routes)),
        follow_redirects=True,
        base_url="https://www.boe.es",
    )


def test_a_redirect_away_from_the_consolidated_endpoint_certifies_no_consolidated_text() -> None:
    """The one answer that positively establishes the absence, so the guard returns.

    This is how BOE says "there is no consolidated text for this id": the
    request for the consolidated view lands somewhere else. Driven with the
    real corrección de errores bytes, which is the document the guard exists
    to let through.
    """
    routes = {
        "/buscar/act.php": (HTTPStatus.FOUND, b"https://www.boe.es/buscar/doc.php?id=BOE-A-2024-24097"),
        "/buscar/doc.php": (HTTPStatus.OK, _payload(_AS_PUBLISHED).encode("utf-8")),
    }
    with _boe_client(routes) as client:
        assert_boe_holds_no_consolidated_text(document_id="BOE-A-2024-24097", client=client)


def test_consolidated_text_served_for_the_id_is_refused() -> None:
    """A version selector at the consolidated endpoint proves consolidated text exists.

    Driven with the real multi-block consolidated payload, so the selector the
    guard reads is BOE's own markup rather than an imagined shape.
    """
    routes = {"/buscar/act.php": (HTTPStatus.OK, _payload(_MULTI_BLOCK).encode("utf-8"))}
    with _boe_client(routes) as client, pytest.raises(NormativeAcquisitionError, match="serves consolidated text"):
        assert_boe_holds_no_consolidated_text(document_id="BOE-A-2024-12944", client=client)


def test_an_unredirected_answer_with_no_version_selector_is_refused_rather_than_passed() -> None:
    """The ambiguous shape must refuse: this guard's unrecognised case is not a pass.

    ``act.php`` answering for itself with no selector is equally the shape of a
    BOE error page returned at 200 and of a selector markup change this parser
    no longer recognises. Passing it would hand the caller an as-published
    redaction of an amended norm, which is the whole defect the guard prevents.
    """
    routes = {"/buscar/act.php": (HTTPStatus.OK, _payload(_AS_PUBLISHED).encode("utf-8"))}
    with _boe_client(routes) as client, pytest.raises(NormativeAcquisitionError, match="cannot establish"):
        assert_boe_holds_no_consolidated_text(document_id="BOE-A-2024-24097", client=client)


def test_canonicalisation_normalises_crlf_and_leaves_legal_text_alone() -> None:
    """Line terminators are the only thing the writers rewrite."""
    assert canonical_lf_bytes(b"art\xc3\xadculo 11\r\n25 por ciento\r\n") == b"art\xc3\xadculo 11\n25 por ciento\n"
    assert canonical_lf_bytes(b"already\nlf\n") == b"already\nlf\n"
    assert canonical_lf_bytes(b"a lone \r stays") == b"a lone \r stays"


#: Below this the normative walk has stopped covering the corpus. A floor
#: rather than a pinned count: 476 bundled normatives ship today.
_MINIMUM_BUNDLED_NORMATIVES = 100


def test_every_bundled_normative_is_already_canonical() -> None:
    """The corpus the registry pins hashes identically on Windows and Unix."""
    assert _CORPUS.is_dir(), (
        f"the bundled normative corpus is not at {_CORPUS}; a relocated root walks nothing "
        "and this gate would report every normative canonical"
    )

    walked = tuple(scan_directory(_CORPUS, pattern="*.html"))

    assert len(walked) >= _MINIMUM_BUNDLED_NORMATIVES, (
        f"only {len(walked)} bundled normative(s) were walked; below this an empty finding "
        "list says nothing about whether the corpus still hashes identically across platforms"
    )

    noncanonical = [
        path.name
        for path in walked
        if canonical_lf_bytes(payload := path.read_bytes()) != payload
    ]

    assert not noncanonical, f"bundled normatives carry CRLF line endings: {noncanonical!r}"
