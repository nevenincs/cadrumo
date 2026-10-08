"""Canonical legal citations, document paths, and provision anchors."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Final

from .legal_reference_models import LegalProvisionRecord, LegalReferenceError

LEGAL_REFERENCE_DIR: Final[str] = "_generated/legal"


_ANCHOR_PREFIX: Final[str] = "legal-"


_GENERATED_INDEX_SLUG: Final[str] = "index"


#: The authored id stem shape a citation can be derived from: an instrument
#: prefix, the instrument number, and the four-digit year.
_STEM_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(?P<prefix>[a-z][a-z-]*[a-z])-(?P<number>\d+)-(?P<year>\d{4})$")


#: ``id-stem prefix -> (Spanish instrument designation, the ``kind`` that must
#: agree)``.  A citation is derived ONLY when the authored prefix and the
#: authored ``kind`` corroborate each other; disagreement falls back to the
#: verbatim stem rather than asserting an instrument the catalogue does not
#: claim.  The designation is the instrument's conventional Spanish reference
#: form, not a title or a summary of what it says.
_INSTRUMENT_BY_PREFIX: Final[dict[str, tuple[str, str]]] = {
    "ley": ("Ley", "ley"),
    "rd": ("Real Decreto", "real_decreto"),
    "rdleg": ("Real Decreto Legislativo", "real_decreto_legislativo"),
    "real-decreto-ley": ("Real Decreto-ley", "real_decreto_ley"),
}


#: Ministry codes that appear as ``orden-<code>-<number>-<year>`` stems and
#: render as the official ``Orden CODE/number/year`` citation form.
_ORDEN_MINISTRY_CODES: Final[frozenset[str]] = frozenset({"eha", "hac", "hap", "hfp"})


def _legal_id_stem(legal_id: str) -> str:
    """Return the instrument-naming part of a ``<stem>:<provision>`` id."""
    return legal_id.partition(":")[0] or legal_id


def legal_instrument_designation(legal_id: str, kind: str) -> str:
    """Return the reader-facing designation of the instrument a provision sits in.

    ``ley-37-1992`` with ``kind = "ley"`` reads as ``Ley 37/1992``: the
    conventional Spanish citation form, recomposed from two authored catalogue
    fields that corroborate each other.  Nothing is asserted that the catalogue
    does not already state, and no title, subject matter, or meaning is
    invented.  A stem whose shape or ``kind`` is not corroborated falls back to
    the authored stem verbatim, so an unrecognised instrument is shown as
    authored rather than guessed at.
    """
    stem = _legal_id_stem(legal_id)
    match = _STEM_PATTERN.match(stem)
    if match is None:
        return stem
    prefix = match.group("prefix")
    number = match.group("number")
    year = match.group("year")
    ministry = prefix.removeprefix("orden-")
    if ministry != prefix and ministry in _ORDEN_MINISTRY_CODES and kind == "orden":
        return f"Orden {ministry.upper()}/{number}/{year}"
    designation = _INSTRUMENT_BY_PREFIX.get(prefix)
    if designation is not None and designation[1] == kind:
        return f"{designation[0]} {number}/{year}"
    return stem


def legal_citation(
    legal_id: str,
    kind: str,
    *,
    article: str | None = None,
    section: str | None = None,
) -> str:
    """Return the reader-facing citation of one provision.

    The single citation authority for every surface that names a provision:
    the legal pages' own headings and the glossary's grounding links both call
    it, so a reader meets one designation for one provision wherever it
    appears.  A reader arriving on a fragment anchor sees this line first and
    nothing above it, so it names the instrument as well as the provision
    within it.

    The citation is Spanish in every build language, and deliberately so.  It
    is the official designation of a Spanish legal text, not page chrome: this
    layer may not translate it, and an English word spliced into it ("Article
    92") would render a citation that no Spanish source uses.  ``art.`` is the
    abbreviation the catalogue's own authored notes use.  ``section`` is a free
    authored Spanish label (``Anexo I``, ``Modelo 190``), never an ordinal, so
    it is appended verbatim rather than introduced by a word of any language.
    """
    instrument = legal_instrument_designation(legal_id, kind)
    parts = [instrument]
    if article is not None:
        parts.append(f"art. {article}")
    if section is not None:
        parts.append(section)
    return ", ".join(parts)


def legal_provision_designation(record: LegalProvisionRecord) -> str:
    """Return the reader-facing citation for one loaded catalogue record."""
    return legal_citation(record.legal_id, record.kind, article=record.article, section=record.section)


def _slug(value: str) -> str:
    """Fold a value to a deterministic lowercase ``[a-z0-9-]`` slug."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    segments: list[str] = []
    current: list[str] = []
    for char in ascii_text:
        if char.isascii() and char.isalnum():
            current.append(char.lower())
        elif current:
            segments.append("".join(current))
            current = []
    if current:
        segments.append("".join(current))
    return "-".join(segments)


def legal_document_slug(document_id: str) -> str:
    """Return the canonical URL-safe slug for a catalogue document id."""
    slug = _slug(str(document_id))
    if not slug:
        raise LegalReferenceError(f"document id {document_id!r} folds to an empty page slug")
    if slug == _GENERATED_INDEX_SLUG:
        raise LegalReferenceError(
            f"document id {document_id!r} uses the reserved generated page slug {slug!r}",
        )
    return slug


def legal_page_relpath(document_id: str) -> Path:
    """Return the generated RST path for a document, relative to ``docs``."""
    return Path(LEGAL_REFERENCE_DIR) / f"{legal_document_slug(document_id)}.rst"


def legal_reference_page(document_id: str) -> str:
    """Return the built, site-relative HTML page for a catalogue document."""
    return f"{LEGAL_REFERENCE_DIR}/{legal_document_slug(document_id)}.html"


def _has_fragment(value: str | None) -> bool:
    if not value or "#" not in value:
        return False
    return bool(value.partition("#")[2])


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())


def legal_provision_anchor(
    legal_id: str,
    *,
    article: str | None = None,
    section: str | None = None,
    corpus_ref: str | None = None,
    permalink: str | None = None,
) -> str | None:
    """Return the canonical provision anchor, or ``None`` for a law-level row.

    An anchor is emitted only when the authored row carries an article,
    section, or URL/corpus fragment.  In particular, a bare law/document row
    is deliberately targetable only at its page; its id is never used to
    fabricate a provision fragment.
    """
    if not (_has_value(article) or _has_value(section) or _has_fragment(corpus_ref) or _has_fragment(permalink)):
        return None
    slug = _slug(str(legal_id))
    if not slug:
        raise LegalReferenceError(f"legal id {legal_id!r} folds to an empty anchor slug")
    return _ANCHOR_PREFIX + slug


def legal_reference_target(
    document_id: str,
    legal_id: str,
    *,
    article: str | None = None,
    section: str | None = None,
    corpus_ref: str | None = None,
    permalink: str | None = None,
) -> str:
    """Return the D1-conformant target for one catalogue provision.

    The result is a site-relative ``.html`` page with an optional fragment and
    is derived from the same helpers the renderer uses.
    """
    page = legal_reference_page(document_id)
    anchor = legal_provision_anchor(
        legal_id,
        article=article,
        section=section,
        corpus_ref=corpus_ref,
        permalink=permalink,
    )
    return f"{page}#{anchor}" if anchor is not None else page
