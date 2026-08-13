"""Acquire a consolidated BOE normative into the bundled corpus.

The `corpus/normatives/html/` subtree had an extractor and no acquirer: nothing
in `src/` or `dev/` could state how `ley-37-1992-art-90.html` got there. This is
the missing half, and it deliberately mirrors
`sync_aeat_record_design_corpus.py` -- maintainer-invoked, repo-relative, no CLI
surface. `test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry`
forbids an operator verb for exactly this behaviour, so a verb here would be a
defect rather than an ergonomic gain.

Reaching the corpus by repo-relative path rather than through the
``aeat_normatives_root`` setting is load-bearing, not incidental: that setting
is declared ``BUNDLED_RESOURCE`` in ``cadrumo.core`` on the grounds that the
APPLICATION only ever reads it. Maintainer tooling writing through the setting
would falsify that declaration, which is precisely what happened once already
with ``aeat_manuals_root``. Writing repo-relatively keeps the declaration true.

==========================================================
Why version selection is not positional
==========================================================

A consolidated payload carries every historical version of the norm. Choosing
the wrong one bundles repealed law under a current filename, and the resulting
file looks authoritative: it is well-formed, it comes from the right URL over a
clean 200, and it still contains the phrases a ``required_text`` gate searches
for. Only the *number* is wrong, which is the one thing a filing cares about.

Position cannot decide it. Measured against the payloads this repo already
bundles, BOE lists versions **newest first** -- ``ley-37-1992-art-90.html`` runs
``20120714, 20091224, 19951230, 19941231, 19921229``, so "take the last" takes
the 1992 original. And ``boe-a-2024-12944`` is not monotonic across the document
at all, because the selector repeats once per *bloque* and blocks amended at
different times legitimately sit at different versions.

So the served version is read from the payload rather than inferred from order:
BOE marks it ``checked``, and the invariant is asserted **per fieldset**, since
a document-wide maximum would refuse a correct multi-block payload.

==========================================================
The article endpoint is a SECOND source with an OPPOSITE rule
==========================================================

``fetch_article`` reads the open-data API instead of ``act.php``. It exists
because the whole-document view does not carry the per-article modification
notes -- the block that names the amending norm, its article, its ``Ref. BOE``
identifier and its effective date. Measured on consolidated LIVA: 411
``Se modifica`` and 609 ``Ref. BOE`` across the document, and zero notes naming
``artículo 91``. The article endpoint returns those notes; it is the only way to
answer "which norm fixed this number", which the grounding rules require before
a regulatory value may ship.

**Its version rule is the INVERSE of the one above, and the two must never be
swapped.** ``act.php`` lists version radios newest first. The article endpoint
concatenates every redaction oldest first -- art. 90 carries both
``15 por 100`` and ``21 por ciento`` -- so "take the last" is right here and
wrong there. Neither is inferred: each redaction is wrapped in its own
``<version fecha_vigencia=...>`` element, so selection reads the attribute and
takes the maximum rather than trusting order at all.

Two further hazards, both measured rather than anticipated:

* **The endpoint refuses unless a mime type it serves is negotiated.** Anything
  but ``application/xml`` -- including httpx's default ``*/*`` -- returns a
  187-byte envelope carrying ``<code>400</code>`` and an empty ``<data/>``.
  Measured: ``*/*``, an explicit ``*/*`` and ``text/csv`` all answer HTTP 400,
  so ``raise_for_status`` does catch them; the envelope code is asserted anyway
  because it, not the transport status, is what the API documents as its result,
  and a body that says 400 must never reach the corpus whatever the status line
  said. Sending the header is the actual fix; the assertion is the backstop.
* **Article-scoped is not always small.** Art. 90 is 8 KB; art. 91 is 952 KB
  across 41 redactions, because payload size tracks amendment history rather
  than article length.

==========================================================
The THIRD endpoint: as-published text BOE never consolidated
==========================================================

``fetch_published_document`` reads ``doc.php``, the single-document view. It
exists because a class of BOE instruments has no consolidated text at all -- a
``corrección de errores`` is published once and never amended, so ``act.php``
redirects to ``doc.php`` and every consolidated-shape invariant above refuses
it correctly.

**Bilateral tax conventions are NOT that class, and this docstring said they
were.** The corrected claim is measured over the bundled corpus rather than
inferred from a permalink: of the nine conventions the legal catalogue cites,
eight are consolidated and their articles were acquired through the endpoint
above -- Belgium (``BOE-A-2003-13375``), Germany (``BOE-A-2012-10212``),
France (``BOE-A-1997-12729``), the United Kingdom (``BOE-A-2014-5171``),
Morocco (``BOE-A-1985-9280``), the Netherlands (``BOE-A-1972-1469``),
Portugal (``BOE-A-1995-24001``) and the United States (``BOE-A-1990-30940``).
Only Argentina 1992 (``BOE-A-1994-20084``) has none. A bundled excerpt whose
permalink points at ``doc.php`` therefore evidences how that excerpt was
acquired, never that BOE holds no consolidated text -- and reading it as the
latter is what left eight conventions unmeasurable. The class that genuinely
has no consolidated text is the annual modelo-approval orden.

**Its invariants are the mirror image of the consolidated ones, and the danger
is the mirror image too.** ``act.php`` can serve a superseded redaction, so the
guard there is "serve each bloque's latest version". ``doc.php`` always serves
the text exactly as first published, so the guard here is "prove BOE holds no
consolidated text for this id" -- otherwise the as-published copy of an amended
norm lands in the corpus as authoritative, which is the very defect the
consolidated guards exist to prevent, reached through the other door. That
proof cannot be read off the payload, so it costs one extra request.

==========================================================
Line endings are canonicalised on write, deliberately
==========================================================

BOE's response line endings are not stable: measured, the consolidated pages
for RDL 6/2024 and RDL 7/2024 carry 181 CRLF pairs each, all inside the
``<script>`` chrome, while ``boe-a-2024-12944`` carries none. The bundled
corpus is hashed and those hashes are pinned in the registry's source
catalogue, so a payload whose line endings vary by fetch (or by a checkout's
autocrlf) produces a different digest for identical legal text. Every writer
here therefore normalises CRLF to LF before writing. It is a line-terminator
canonicalisation and nothing else -- no character of legal text is touched --
and it is what makes ``sha256`` a stable identity for the document rather than
for one fetch of it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import httpx

_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_ROOT))

_CORPUS: Final[Path] = _ROOT / "src/cadrumo/_data/corpus/normatives/html"
_ACT_URL: Final[str] = "https://www.boe.es/buscar/act.php"
_DOC_URL: Final[str] = "https://www.boe.es/buscar/doc.php"
_ARTICLE_URL: Final[str] = (
    "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{document_id}/texto/bloque/{block}"
)

#: The API refuses with an in-envelope 400 unless a mime type is negotiated.
_ARTICLE_HEADERS: Final[dict[str, str]] = {"Accept": "application/xml"}
_ENVELOPE_CODE = re.compile(r"<code>(?P<code>\d+)</code>")
_ENVELOPE_MESSAGE = re.compile(r"<status>.*?<text>(?P<message>.*?)</text>", re.DOTALL)
_BLOCK_ID = re.compile(r"<bloque\b[^>]*\bid=\"(?P<block>[^\"]+)\"", re.IGNORECASE)
#: BOE's own title for the block. Semantic where the id is positional.
_BLOCK_TITLE = re.compile(r"<bloque\b[^>]*\btitulo=\"(?P<titulo>[^\"]*)\"", re.IGNORECASE)
#: Each redaction of the article, tagged with the norm and the date it took effect.
_ARTICLE_VERSION = re.compile(
    r"<version\b[^>]*\bid_norma=\"(?P<document_id>BOE-[A-Z]-\d{4}-\d+)\""
    r"[^>]*\bfecha_vigencia=\"(?P<vigencia>\d{8})\"[^>]*>",
    re.IGNORECASE,
)

#: One ``<fieldset>`` per bloque; the version radios repeat inside each.
_FIELDSET = re.compile(r"<fieldset\b.*?</fieldset>", re.DOTALL | re.IGNORECASE)
_VERSION_RADIO = re.compile(
    r"<input[^>]*\btype=\"radio\"[^>]*\bvalue=\"(?P<version>\d{8})\"[^>]*>",
    re.IGNORECASE,
)
_CHECKED = re.compile(r"\bchecked\b", re.IGNORECASE)
_DOCUMENT_ID = re.compile(
    r"<input[^>]*\bname=\"id\"[^>]*\bvalue=\"(?P<document_id>BOE-[A-Z]-\d{4}-\d+)\"|"
    r"<input[^>]*\bvalue=\"(?P<alt>BOE-[A-Z]-\d{4}-\d+)\"[^>]*\bname=\"id\"",
    re.IGNORECASE,
)

#: The single-document view's server-emitted self-identification. Preferred
#: over the id echoed into the page body because it names the ENDPOINT as well
#: as the id, so it cannot be satisfied by a consolidated page that merely
#: mentions the same document.
_CANONICAL_LINK = re.compile(
    r"<link\b[^>]*\brel=\"canonical\"[^>]*\bhref=\"(?P<href>[^\"]+)\"",
    re.IGNORECASE,
)

_CRLF: Final[bytes] = b"\r\n"
_LF: Final[bytes] = b"\n"


class NormativeAcquisitionError(RuntimeError):
    """The payload cannot be shown to be the consolidated text in force."""


def canonical_lf_bytes(data: bytes) -> bytes:
    """Return ``data`` with CRLF line terminators normalised to LF.

    Applied by every writer in this module so a document's ``sha256`` is an
    identity for the document rather than for one fetch of it. See the module
    docstring for the measurement that motivates it.

    Args:
        data: The fetched payload bytes.

    Returns:
        The same bytes with every CRLF replaced by a bare LF.
    """
    return data.replace(_CRLF, _LF)


def _write_verified(destination: Path, data: bytes) -> Path:
    """Write canonicalised bytes and read them back before returning the path.

    Args:
        destination: Path under the bundled corpus to write.
        data: The fetched payload bytes, pre-canonicalisation.

    Returns:
        The written path.

    Raises:
        NormativeAcquisitionError: If the read-back does not match.
    """
    canonical = canonical_lf_bytes(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical)
    if destination.read_bytes() != canonical:
        raise NormativeAcquisitionError(f"read-back of {destination} does not match the fetched bytes")
    return destination


@dataclass(frozen=True)
class VersionSelection:
    """What one bloque's selector says, and what it served."""

    checked: str
    offered: tuple[str, ...]


def version_selections(payload: str) -> tuple[VersionSelection, ...]:
    """Return the checked and offered versions for every bloque in ``payload``.

    A bloque with no version radios contributes nothing: BOE emits fieldsets for
    unrelated form controls too, and treating those as blocks with no versions
    would make the invariant below trivially unsatisfiable.
    """
    selections: list[VersionSelection] = []
    for block in _FIELDSET.findall(payload):
        offered: list[str] = []
        checked: str | None = None
        for radio in _VERSION_RADIO.finditer(block):
            version = radio.group("version")
            offered.append(version)
            if _CHECKED.search(radio.group(0)):
                checked = version
        if not offered:
            continue
        if checked is None:
            raise NormativeAcquisitionError(
                f"a bloque offers versions {offered} but marks none of them checked, so the payload "
                "does not say which text BOE served"
            )
        selections.append(VersionSelection(checked=checked, offered=tuple(offered)))
    return tuple(selections)


def assert_served_by_the_requested_endpoint(*, final_url: str, requested_url: str) -> None:
    """Refuse a payload the requested endpoint did not actually serve.

    Every other check here reads the PAYLOAD, and a payload cannot say which
    endpoint produced it. That gap is not theoretical: measured on a live
    probe, a request to the consolidated ``act.php`` endpoint silently
    redirected to ``doc.php``, the single-document view, and the identity check
    passed because ``doc.php`` echoes the requested id in the same form input.
    An identity check that reads the id back out of a response is satisfied by
    ANY endpoint that echoes it, so it verifies the REQUEST rather than the
    SOURCE.

    Only the version-selector check refused that payload, and it refused for an
    unrelated reason -- a single-document view offers no versions. It would NOT
    have caught a redirect landing on something version-bearing, and this
    acquirer is the only thing standing between the fleet and hand-fetching.

    The structural fact behind the live case, worth keeping because it explains
    the shape rather than the incident: BOE holds no consolidated text for
    bilateral tax conventions at all. Each convention excerpt's own permalink
    had already recorded that by pointing at ``doc.php`` rather than ``act.php``
    -- a provenance marker sitting in plain sight, unread because nobody was
    looking for a SHAPE difference in a URL.

    Compared on scheme, host and path only. The query string legitimately
    differs -- BOE echoes and reorders parameters -- and a comparison that
    included it would refuse correct responses, which is how a guard gets
    switched off.

    Args:
        final_url: The URL the response actually came from, after redirects.
        requested_url: The endpoint this acquirer meant to read.

    Raises:
        NormativeAcquisitionError: If the response came from a different
            scheme, host or path than the one requested.
    """
    served = urlsplit(final_url)
    wanted = urlsplit(requested_url)
    if (served.scheme, served.netloc, served.path) != (wanted.scheme, wanted.netloc, wanted.path):
        raise NormativeAcquisitionError(
            f"the response came from {served.scheme}://{served.netloc}{served.path} rather than the requested "
            f"{wanted.scheme}://{wanted.netloc}{wanted.path}; a redirect to a different endpoint can echo the "
            f"requested id and satisfy every payload check while serving something other than the "
            f"consolidated text"
        )


def assert_serves_the_text_in_force(payload: str, *, document_id: str) -> tuple[VersionSelection, ...]:
    """Refuse a payload that is not the consolidated text currently in force.

    Raises:
        NormativeAcquisitionError: If the payload names a different document, or
            offers no version selector at all, or serves a bloque at anything
            other than that bloque's own latest version.

    Returns:
        The per-bloque selections, so a caller can record what it accepted.
    """
    found = _DOCUMENT_ID.search(payload)
    served_id = (found.group("document_id") or found.group("alt")) if found else None
    if served_id != document_id:
        raise NormativeAcquisitionError(
            f"payload declares document id {served_id!r}, not the requested {document_id!r}"
        )

    selections = version_selections(payload)
    if not selections:
        raise NormativeAcquisitionError(
            "payload carries no version selector, so it cannot be shown to be the consolidated text "
            "rather than a single historical redaction"
        )

    # Per fieldset, never document-wide: blocks amended at different times sit at
    # different versions legitimately, so a global maximum refuses correct text.
    stale = [s for s in selections if s.checked != max(s.offered)]
    if stale:
        raise NormativeAcquisitionError(
            "payload serves a superseded redaction: "
            + "; ".join(f"bloque checked {s.checked} while offering up to {max(s.offered)}" for s in stale)
        )
    return selections


def fetch_normative(
    *,
    document_id: str,
    destination_name: str,
    required_text: tuple[str, ...] = (),
    client: httpx.Client | None = None,
) -> Path:
    """Fetch one consolidated BOE norm and write it under the bundled corpus.

    Requests ``act.php`` with no version parameter, so BOE serves the text in
    force rather than one this caller guessed at, then refuses the payload
    unless it can be shown to BE that text. The bytes are written binary and
    read back before the path is returned: an encoding round trip through text
    mangles the accented characters legal text is full of.

    Args:
        document_id: The BOE identifier, e.g. ``BOE-A-2012-9364``.
        destination_name: Filename under ``corpus/normatives/html/``.
        required_text: Phrases that must appear in the fetched bytes -- the
            amending norm's identifier belongs here, so a payload that parses
            cleanly but is the wrong norm still refuses.
        client: Injected for testing; a real client is created when omitted.

    Returns:
        The written path.

    Raises:
        NormativeAcquisitionError: If the payload is not the text in force, or a
            ``required_text`` phrase is absent, or the read-back does not match.
    """
    owned = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0"},
    )
    try:
        response = http.get(_ACT_URL, params={"id": document_id})
        response.raise_for_status()
        assert_served_by_the_requested_endpoint(final_url=str(response.url), requested_url=_ACT_URL)
        data = response.content
    finally:
        if owned:
            http.close()

    payload = data.decode("utf-8", errors="replace")
    assert_serves_the_text_in_force(payload, document_id=document_id)

    missing = [phrase for phrase in required_text if phrase not in payload]
    if missing:
        raise NormativeAcquisitionError(f"fetched {document_id} but these required phrases are absent: {missing}")

    return _write_verified(_CORPUS / destination_name, data)


@dataclass(frozen=True)
class ArticleRedaction:
    """One historical redaction of a single article, and when it took effect.

    ``amending_norm`` is the norm that PRODUCED this redaction, not the norm
    being read. Art. 90 of LIVA carries five redactions attributed to
    ``BOE-A-1992-28740`` (the original enactment), then Ley 41/1994, RDL 12/1995,
    Ley 26/2009 and RDL 20/2012 -- so four of the five name a different document
    than the one requested, and that is correct rather than a mismatch.

    This is the field that makes the endpoint worth using. "Which norm fixed
    this value, and from when" is exactly the pair
    ``(amending_norm, vigencia)``, available structurally here instead of by
    parsing the prose notes.
    """

    amending_norm: str
    vigencia: str


def article_redactions(payload: str) -> tuple[ArticleRedaction, ...]:
    """Return every redaction the article payload carries, in document order.

    Order is reported but deliberately not relied on. This endpoint happens to
    emit oldest first, which is the opposite of ``act.php``; encoding that
    direction anywhere would make the two sources' rules look swappable, and
    swapping them silently selects repealed law.
    """
    return tuple(
        ArticleRedaction(amending_norm=match.group("document_id"), vigencia=match.group("vigencia"))
        for match in _ARTICLE_VERSION.finditer(payload)
    )


def article_block_title(payload: str) -> str:
    """Return BOE's own title for the block an article payload describes.

    The block ID is POSITIONAL and its title is SEMANTIC, and the two disagree
    often enough that only the title identifies the provision. Measured across
    the bundled article payloads: block ``a1-3`` of the Spain-Netherlands
    convention is titled "Artículo 11", and block ``ar-10`` of the
    Spain-Morocco convention is titled "Artículo 11" too. A consumer matching
    an entry to a payload by article number therefore has to read this, not the
    id.

    Args:
        payload: The decoded API response.

    Returns:
        The ``titulo`` attribute, or the empty string when the payload declares
        none. Never a value derived from the block id.
    """
    found = _BLOCK_TITLE.search(payload)
    return found.group("titulo") if found else ""


def article_redaction_markup(payload: str, redaction: ArticleRedaction) -> str:
    """Return the markup of exactly one redaction of the article.

    The article endpoint concatenates every redaction into one ``<bloque>``,
    so any consumer reading the payload as a single document is reading
    repealed law mixed with law in force. Slicing to one ``<version>`` element
    is what makes the payload usable as an oracle, and it is deliberately a
    LOOKUP rather than a selection: pass the redaction
    :func:`assert_serves_the_article_in_force` returned, which is the only
    function here that decides which redaction is in force and the only one
    that refuses a tie.

    Args:
        payload: The decoded API response.
        redaction: The redaction to slice out, obtained from
            :func:`assert_serves_the_article_in_force` or
            :func:`article_redactions`.

    Returns:
        The markup between that ``<version>`` element's opening tag and the
        next redaction's opening tag (or the end of the payload).

    Raises:
        NormativeAcquisitionError: If the payload does not carry exactly one
            ``<version>`` matching this redaction. Zero means the redaction did
            not come from this payload; more than one means the slice is
            ambiguous, which is the tie hazard reached from the other side.
    """
    opens = [
        match
        for match in _ARTICLE_VERSION.finditer(payload)
        if match.group("document_id") == redaction.amending_norm and match.group("vigencia") == redaction.vigencia
    ]
    if len(opens) != 1:
        raise NormativeAcquisitionError(
            f"payload carries {len(opens)} <version> elements for {redaction.amending_norm} "
            f"at fecha_vigencia {redaction.vigencia!r}, so the redaction cannot be sliced unambiguously"
        )
    start = opens[0].end()
    following = [match.start() for match in _ARTICLE_VERSION.finditer(payload) if match.start() >= start]
    return payload[start : following[0]] if following else payload[start:]


def assert_serves_the_article_in_force(payload: str, *, document_id: str, block: str) -> ArticleRedaction:
    """Refuse the payload unless it is this article, and return the redaction in force.

    Three refusals, each closing a way the fetch can succeed and still be unfit.

    Identity rests on the BLOCK id, not on the norm ids the redactions carry.
    Those name the AMENDING norms, so most of them differ from the document
    requested; an identity check written against them refuses every
    much-amended article, which is every article worth fetching. The first
    draft here did exactly that and the art. 90 fixture caught it.

    * the envelope reports a non-200 code -- the API's own result lives in the
      body, and a payload saying 400 must not reach the corpus regardless of the
      status line. Measured, the failing mime negotiations all answer HTTP 400
      too, so this duplicates ``raise_for_status`` today rather than replacing
      it; it is kept because the envelope is the documented result channel and
      the transport status is not guaranteed to track it;
    * the payload describes a different block than the one requested;
    * it carries no ``<version>`` at all, so nothing establishes which redaction
      it is;
    * two or more redactions TIE on the latest ``fecha_vigencia``. Art. 91
      carries two dated ``19950120``, one reading 3 % and one 4 %, so picking
      arbitrarily between tied dates can return the superseded text -- which is
      the exact defect this module exists to prevent. Refused rather than
      guessed.

    ``fecha_vigencia`` is also NOT the effective date a citation should quote.
    Those two art. 91 redactions are both stamped ``19950120`` while the norm
    that produced them, Ley 41/1994 art. 78.2, states effects from 1 January
    1995. Use the attribute to order redactions; read the date to cite off the
    note.

    Args:
        payload: The decoded API response.
        document_id: The BOE identifier the caller asked for.
        block: The article anchor the caller asked for, e.g. ``a90``.

    Returns:
        The redaction with the latest ``fecha_vigencia`` -- the text in force.

    Raises:
        NormativeAcquisitionError: On any of the four refusals above.
    """
    found_code = _ENVELOPE_CODE.search(payload)
    code = found_code.group("code") if found_code else None
    if code != "200":
        found_message = _ENVELOPE_MESSAGE.search(payload)
        message = found_message.group("message").strip() if found_message else "no status text"
        raise NormativeAcquisitionError(
            f"the API envelope reports code {code!r}, not 200: {message}. The HTTP status is 200 either way, "
            "so this is asserted on the envelope rather than on the transport"
        )

    found_block = _BLOCK_ID.search(payload)
    served_block = found_block.group("block") if found_block else None
    if served_block != block:
        raise NormativeAcquisitionError(f"payload describes block {served_block!r}, not the requested {block!r}")

    redactions = article_redactions(payload)
    if not redactions:
        raise NormativeAcquisitionError(
            "payload carries no <version> element, so no redaction can be shown to be the one in force"
        )

    latest = max(redaction.vigencia for redaction in redactions)
    tied = [redaction for redaction in redactions if redaction.vigencia == latest]
    if len(tied) > 1:
        raise NormativeAcquisitionError(
            f"{len(tied)} redactions share the latest fecha_vigencia {latest!r} "
            f"({', '.join(r.amending_norm for r in tied)}), so the payload does not say which is in force. "
            "Refused rather than picked: art. 91 carries two redactions dated 19950120, one reading 3 % and "
            "one reading 4 %, so an arbitrary pick between tied dates can silently return the SUPERSEDED text"
        )
    return tied[0]


def fetch_article(
    *,
    document_id: str,
    block: str,
    destination_name: str,
    required_text: tuple[str, ...] = (),
    client: httpx.Client | None = None,
) -> Path:
    """Fetch one consolidated ARTICLE, with its amending-norm notes, into the corpus.

    The whole-document companion above cannot answer which norm fixed a value;
    this can, because the article view carries the modification notes and the
    document view does not.

    Args:
        document_id: The BOE identifier, e.g. ``BOE-A-1992-28740``.
        block: The article anchor, e.g. ``a90``.
        destination_name: Filename under ``corpus/normatives/html/``.
        required_text: Phrases that must appear in the fetched bytes.
        client: Injected for testing; a real client is created when omitted.

    Returns:
        The written path.

    Raises:
        NormativeAcquisitionError: If the payload is not this article in force,
            or a ``required_text`` phrase is absent, or the read-back differs.
    """
    owned = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0", **_ARTICLE_HEADERS},
    )
    try:
        article_url = _ARTICLE_URL.format(document_id=document_id, block=block)
        response = http.get(article_url, headers=_ARTICLE_HEADERS)
        response.raise_for_status()
        assert_served_by_the_requested_endpoint(final_url=str(response.url), requested_url=article_url)
        data = response.content
    finally:
        if owned:
            http.close()

    payload = data.decode("utf-8", errors="replace")
    assert_serves_the_article_in_force(payload, document_id=document_id, block=block)

    missing = [phrase for phrase in required_text if phrase not in payload]
    if missing:
        raise NormativeAcquisitionError(
            f"fetched {document_id} block {block} but these required phrases are absent: {missing}"
        )

    return _write_verified(_CORPUS / destination_name, data)


def assert_serves_the_published_document(payload: str, *, document_id: str) -> None:
    """Refuse a payload that is not this document's own single-document view.

    One refusal, and deliberately only one: the server-emitted ``rel="canonical"``
    link must name this endpoint and this id. It is preferred over the id echoed
    into the page body, which any view of the document satisfies, and it is the
    whole of what a payload can establish here.

    **It does NOT establish that the document is un-consolidated, and no payload
    check can.** Measured against live BOE: ``doc.php?id=BOE-A-2024-23422`` --
    a norm BOE does consolidate -- returns a 618 KB as-published page whose
    canonical link names ``doc.php`` and which carries no version selector at
    all, so it is shape-identical to the corrección de errores this function was
    written for. That is why :func:`assert_boe_holds_no_consolidated_text` costs
    a second request instead of reading a flag off these bytes: it is the only
    thing standing between the corpus and an as-published redaction of an
    amended norm.

    Args:
        payload: The decoded response body.
        document_id: The BOE identifier the caller asked for.

    Raises:
        NormativeAcquisitionError: If the payload is not this document's own
            single-document view.
    """
    found = _CANONICAL_LINK.search(payload)
    canonical = found.group("href").strip() if found else None
    expected = f"{_DOC_URL}?id={document_id}"
    if canonical != expected:
        raise NormativeAcquisitionError(f"payload declares canonical URL {canonical!r}, not the requested {expected!r}")


def assert_boe_holds_no_consolidated_text(*, document_id: str, client: httpx.Client) -> None:
    """Refuse an as-published fetch of a document BOE also consolidates.

    This is the guard that makes :func:`fetch_published_document` safe. The
    single-document view serves the text exactly as first published and never
    reflects a later amendment, so bundling it for a norm that HAS been amended
    stores repealed law under a current filename -- the same defect the
    consolidated fetcher's redaction invariant exists to prevent, reached
    through the other endpoint. No payload can state its own absence from the
    consolidated collection -- and, measured, the single-document view of a
    consolidated norm is indistinguishable in shape from that of an
    un-consolidated one -- so the fact is established by asking for it: a
    request for the consolidated view that is still served BY the consolidated
    view, and that carries a version selector, proves consolidated text exists.

    A redirect away from ``act.php`` is the expected, accepted answer -- and it
    is the ONLY accepted answer. It is exactly how BOE says "there is no
    consolidated text for this id", and it is the single observation that
    positively establishes the absence this function is asked to certify.

    Every other outcome refuses, including the case where ``act.php`` answers
    for itself and the payload carries no version selector. That combination
    says nothing: it is equally the shape of an id with no consolidated text
    served through an unredirected route, of a BOE error or maintenance page
    returned at 200, and of a selector markup change this parser no longer
    recognises. Returning on it would let the third case silently hand the
    caller an as-published redaction of an amended norm -- the exact defect
    this guard exists to prevent -- so the ambiguity is refused and the
    operator re-checks the id by hand. A guard whose unrecognised case is a
    pass is not a guard.

    Args:
        document_id: The BOE identifier being acquired as-published.
        client: The HTTP client to probe with, shared with the caller's fetch.

    Raises:
        NormativeAcquisitionError: If BOE serves consolidated text for the id,
            or if the probe cannot positively establish that it does not.
    """
    response = client.get(_ACT_URL, params={"id": document_id})
    response.raise_for_status()
    served = urlsplit(str(response.url))
    wanted = urlsplit(_ACT_URL)
    if (served.scheme, served.netloc, served.path) != (wanted.scheme, wanted.netloc, wanted.path):
        return
    if version_selections(response.content.decode("utf-8", errors="replace")):
        raise NormativeAcquisitionError(
            f"BOE serves consolidated text for {document_id}, so the as-published view would bundle the "
            "original redaction of a norm that may since have been amended; use fetch_normative instead"
        )
    raise NormativeAcquisitionError(
        f"the consolidated endpoint answered for {document_id} without redirecting away and without a "
        "version selector, so this probe cannot establish that BOE holds no consolidated text for it; "
        "only a redirect away from the consolidated endpoint establishes that. Re-check the id by hand "
        "before bundling the as-published view"
    )


def fetch_published_document(
    *,
    document_id: str,
    destination_name: str,
    required_text: tuple[str, ...] = (),
    client: httpx.Client | None = None,
) -> Path:
    """Fetch one as-published BOE document BOE holds no consolidated text for.

    The shape for instruments that are published once and never amended -- a
    ``corrección de errores`` is the canonical case, and a bilateral tax
    convention is the other. For anything BOE consolidates, this refuses and
    directs the caller to :func:`fetch_normative`.

    Args:
        document_id: The BOE identifier, e.g. ``BOE-A-2024-24097``.
        destination_name: Filename under ``corpus/normatives/html/``.
        required_text: Phrases that must appear in the fetched bytes.
        client: Injected for testing; a real client is created when omitted.

    Returns:
        The written path.

    Raises:
        NormativeAcquisitionError: If the response came from another endpoint,
            the payload is not this document's single-document view, BOE also
            consolidates the id, a ``required_text`` phrase is absent, or the
            read-back does not match.
    """
    owned = client is None
    http = client or httpx.Client(
        follow_redirects=True,
        timeout=90,
        headers={"User-Agent": "cadrumo-corpus-hydration/1.0"},
    )
    try:
        response = http.get(_DOC_URL, params={"id": document_id})
        response.raise_for_status()
        assert_served_by_the_requested_endpoint(final_url=str(response.url), requested_url=_DOC_URL)
        data = response.content
        assert_boe_holds_no_consolidated_text(document_id=document_id, client=http)
    finally:
        if owned:
            http.close()

    payload = data.decode("utf-8", errors="replace")
    assert_serves_the_published_document(payload, document_id=document_id)

    missing = [phrase for phrase in required_text if phrase not in payload]
    if missing:
        raise NormativeAcquisitionError(f"fetched {document_id} but these required phrases are absent: {missing}")

    return _write_verified(_CORPUS / destination_name, data)
