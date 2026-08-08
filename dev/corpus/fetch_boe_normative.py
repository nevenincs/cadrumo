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
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx

_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(_ROOT))

_CORPUS: Final[Path] = _ROOT / "src/cadrumo/_data/corpus/normatives/html"
_ACT_URL: Final[str] = "https://www.boe.es/buscar/act.php"
_ARTICLE_URL: Final[str] = (
    "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{document_id}/texto/bloque/{block}"
)

#: The API refuses with an in-envelope 400 unless a mime type is negotiated.
_ARTICLE_HEADERS: Final[dict[str, str]] = {"Accept": "application/xml"}
_ENVELOPE_CODE = re.compile(r"<code>(?P<code>\d+)</code>")
_ENVELOPE_MESSAGE = re.compile(r"<status>.*?<text>(?P<message>.*?)</text>", re.DOTALL)
_BLOCK_ID = re.compile(r"<bloque\b[^>]*\bid=\"(?P<block>[^\"]+)\"", re.IGNORECASE)
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


class NormativeAcquisitionError(RuntimeError):
    """The payload cannot be shown to be the consolidated text in force."""


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
        data = response.content
    finally:
        if owned:
            http.close()

    payload = data.decode("utf-8", errors="replace")
    assert_serves_the_text_in_force(payload, document_id=document_id)

    missing = [phrase for phrase in required_text if phrase not in payload]
    if missing:
        raise NormativeAcquisitionError(f"fetched {document_id} but these required phrases are absent: {missing}")

    destination = _CORPUS / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    if destination.read_bytes() != data:
        raise NormativeAcquisitionError(f"read-back of {destination} does not match the fetched bytes")
    return destination


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
        response = http.get(
            _ARTICLE_URL.format(document_id=document_id, block=block),
            headers=_ARTICLE_HEADERS,
        )
        response.raise_for_status()
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

    destination = _CORPUS / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    if destination.read_bytes() != data:
        raise NormativeAcquisitionError(f"read-back of {destination} does not match the fetched bytes")
    return destination
