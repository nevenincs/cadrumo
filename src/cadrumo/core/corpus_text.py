"""Import-light text normalisation and extracted-unit resolution for corpora."""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Final, NamedTuple

from .errors import CoreError
from .external_constants import UTF_8_ENCODING
from .text_fold import fold_diacritics

__all__ = [
    "CorpusAnchorResolutionError",
    "CorpusRedactionMark",
    "corpus_redaction_marks",
    "extracted_unit_count",
    "normalise_corpus_text",
    "resolve_anchored_extracted_unit",
]

_HTML_TAG_RE = re.compile(r"<[a-zA-Z!/?][^<>\s]{0,200}>")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_ARTICLE_ANCHOR_RE = re.compile(r"^(?:a|art|articulo)(\d+)$")
# ``_canonical_anchor`` folds every ``art``/``articulo`` prefix down to ``a``
# before this pattern ever sees a title, so the canonical form is now the only
# one it will meet in practice; the ``articulo`` alternative stays only for the
# locally-built ``expanded`` strings in ``_title_matches_anchor``, which are
# assembled from the un-canonicalised ``_ANCHOR_PREFIXES`` replacement values.
_ARTICLE_TITLE_RE = re.compile(r"^(?:articulo|a)(\d+)")
_ARTICLE_BASE_ANCHOR_RE = re.compile(r"^(?:a|arts?|articulos?)[\s._-]*(\d+)$")
_ARTICLE_SUBSECTION_ANCHOR_RE = re.compile(r"^(?:a|arts?|articulos?)[\s._-]*(\d+)[\s._-]+\d+(?:$|[\s._-])")

_SPANISH_ORDINALS: Final[dict[str, str]] = {
    "primero": "1",
    "primera": "1",
    "segundo": "2",
    "segunda": "2",
    "tercero": "3",
    "tercera": "3",
    "cuarto": "4",
    "cuarta": "4",
    "quinto": "5",
    "quinta": "5",
    "sexto": "6",
    "sexta": "6",
    "septimo": "7",
    "septima": "7",
    "octavo": "8",
    "octava": "8",
    "noveno": "9",
    "novena": "9",
    "decimo": "10",
    "decima": "10",
    "undecimo": "11",
    "undecima": "11",
    "duodecimo": "12",
    "duodecima": "12",
}

_ANCHOR_PREFIXES: Final[dict[str, str]] = {
    "articulo": "articulo",
    "art": "articulo",
    "a": "articulo",
    "anexo": "anexo",
    "apartado": "apartado",
    "da": "disposicionadicional",
    "dt": "disposiciontransitoria",
    "df": "disposicionfinal",
    "disposicionadicional": "disposicionadicional",
    "disposiciontransitoria": "disposiciontransitoria",
    "disposicionfinal": "disposicionfinal",
}


class CorpusAnchorResolutionError(CoreError):
    """Raised when an extracted corpus sidecar has no unique target unit.

    A core-primitive failure, so it inherits :class:`CoreError` and carries a
    registered error code rather than deriving from a bare
    :class:`ValueError`. Both consumers -- the citation lookup and the registry
    legal-reference reader -- catch it by name and immediately wrap it in their
    own registered error, so nothing depended on the builtin base; what an
    unregistered root did cost was a structured envelope, leaving an operator a
    raw interpreter traceback for a bundled-corpus anchor that cannot resolve.
    """


def normalise_corpus_text(text: str) -> str:
    """Normalise corpus text for citation-presence checks.

    The HTML-tag stripper only matches well-formed tags whose ``<``
    immediately precedes a tag-name character (letter, slash, or
    ``!``/``?``) and whose body is short and contains no spaces — so that
    bare comparison operators (e.g. ``< 500 euros`` and ``< 3 años``
    that AEAT's manuals use as math notation) and other unbalanced
    angle brackets do not inadvertently swallow long spans of prose.
    """
    decoded = html.unescape(text).replace("\xa0", " ")
    without_tags = _HTML_TAG_RE.sub(" ", decoded)
    without_marks = fold_diacritics(without_tags)
    return _WHITESPACE_RE.sub(" ", without_marks).strip().casefold()


class CorpusRedactionMark(NamedTuple):
    """One dated redaction a consolidated BOE payload declares, and where it sits.

    ``amending_norm`` is the norm that PRODUCED this redaction rather than the
    norm being read, so most marks in a much-amended article name a different
    document than the one requested. ``vigencia`` is the ``fecha_vigencia``
    attribute as published, ``YYYYMMDD``; it orders redactions and is NOT the
    effective date a citation should quote.

    ``tag_start`` is the offset of the ``<version>`` opening tag and
    ``body_start`` the offset just past it, so a caller can slice exactly one
    redaction out of a payload that concatenates them all.
    """

    amending_norm: str
    vigencia: str
    tag_start: int
    body_start: int


#: Each redaction of an article, tagged with the norm that produced it and the
#: date it took effect. The single pattern for this markup in the tree: the
#: maintainer-side acquirer and the registry's build-time refusal both read it
#: through :func:`corpus_redaction_marks` rather than carrying a copy, so the
#: two cannot drift into disagreeing about what a redaction boundary is.
_REDACTION_MARK_RE: Final = re.compile(
    r"<version\b[^>]*\bid_norma=\"(?P<amending_norm>BOE-[A-Z]-\d{4}-\d+)\""
    r"[^>]*\bfecha_vigencia=\"(?P<vigencia>\d{8})\"[^>]*>",
    re.IGNORECASE,
)


def corpus_redaction_marks(payload: str) -> tuple[CorpusRedactionMark, ...]:
    """Return every dated redaction ``payload`` declares, in document order.

    Order is reported but deliberately not meaningful. BOE's open-data article
    endpoint concatenates redactions oldest first while the consolidated
    ``act.php`` view lists its version selector newest first, so any consumer
    that inferred "current" from position would be right about one source and
    silently bundle repealed law from the other. Selection therefore reads the
    ``fecha_vigencia`` attribute, and this function only enumerates.

    A payload with no such markup -- a consolidated whole-document page, an
    as-published single-document view, a hand-sliced article -- yields an empty
    tuple, which is the honest answer for a document that declares no redaction
    history rather than a claim that it holds only one redaction.

    Args:
        payload: The decoded corpus document.

    Returns:
        One :class:`CorpusRedactionMark` per ``<version>`` element carrying both
        an ``id_norma`` and a ``fecha_vigencia``.
    """
    return tuple(
        CorpusRedactionMark(
            amending_norm=match.group("amending_norm"),
            vigencia=match.group("vigencia"),
            tag_start=match.start(),
            body_start=match.end(),
        )
        for match in _REDACTION_MARK_RE.finditer(payload)
    )


def extracted_unit_count(sidecar_path: Path) -> int:
    """Return how many readable units an extracted corpus sidecar carries.

    Counts exactly the units :func:`resolve_anchored_extracted_unit` would
    consider -- those carrying non-empty text -- so a caller reasoning about how
    a sidecar partitions its source document reasons about the same partition
    the resolver selects from.

    Args:
        sidecar_path: Path to the ``.extracted.json`` artefact.

    Returns:
        The number of units carrying non-empty text.

    Raises:
        CorpusAnchorResolutionError: If the sidecar cannot be read or declares
            no units list.
    """
    return len(_readable_units(sidecar_path))


def _literal_anchor(value: str) -> str:
    """Return an anchor comparison key that preserves internal punctuation.

    Only case, surrounding whitespace and a leading ``#`` are normalised, so
    ``#a3-3`` and ``#a33`` stay distinct.  This is deliberately weaker than
    :func:`_canonical_anchor`: it exists to tell two real anchors apart, not to
    reconcile spelling variants.
    """
    return value.strip().lstrip("#").strip().casefold()


def resolve_anchored_extracted_unit(
    sidecar_path: Path,
    *,
    anchor: str,
    required_text: tuple[str, ...] = (),
    include_title: bool = False,
) -> str:
    """Return the one extracted unit that safely represents ``anchor``.

    Exact sidecar anchors take precedence.  Legacy article slices without a
    matching persisted fragment remain safe only when their sidecar holds one
    unit; a requested fragment then cannot select unrelated text.  Multi-unit
    records may use only a unique structural heading that matches the requested
    anchor. Missing or duplicate candidates raise instead of silently returning
    a whole document. ``required_text`` verifies the selected unit at the
    legal-reference layer; it cannot select a different one here.
    """
    target = _canonical_anchor(anchor)
    if not target:
        raise CorpusAnchorResolutionError("anchor must be non-empty")
    units = _readable_units(sidecar_path)
    if not units:
        raise CorpusAnchorResolutionError(f"extracted sidecar {sidecar_path} has no readable units")

    # Canonicalisation deletes non-alphanumerics, so a BOE positional anchor
    # like "#a3-3" collapses onto the genuine "#a33" of Articulo 33 and both
    # become undecidable -- 114 such collisions across 12 bundled sidecars,
    # including LIRPF, LIVA and the IVA reglamento, each one a provision that
    # cannot be cited at all.  A verbatim match is tried first because it can
    # only ever NARROW the canonical candidate set: any literal match also
    # canonicalises equal, so this disambiguates without letting a request
    # select a unit canonicalisation would have rejected.
    literal = [
        (title, text) for unit_anchor, title, text in units if _literal_anchor(unit_anchor) == _literal_anchor(anchor)
    ]
    if len(literal) == 1:
        return _render_unit(*literal[0], include_title=include_title)

    exact = [(title, text) for unit_anchor, title, text in units if _canonical_anchor(unit_anchor) == target]
    if len(exact) == 1:
        return _render_unit(*exact[0], include_title=include_title)
    if len(exact) > 1:
        raise CorpusAnchorResolutionError(f"anchor {anchor!r} is duplicated in {sidecar_path}")
    if len(units) == 1:
        unit_anchor, title, text = units[0]
        if not _canonical_anchor(unit_anchor) or _single_unit_covers_subsection(unit_anchor, anchor):
            # A sidecar containing one article is already scoped to that
            # article. It may therefore cover a numeric subsection citation
            # of the same article even when extraction persisted only the
            # article unit. A different article remains a missing anchor.
            return _render_unit(title, text, include_title=include_title)

    structural = [(title, text) for _unit_anchor, title, text in units if _title_matches_anchor(title, target)]
    if len(structural) == 1:
        return _render_unit(*structural[0], include_title=include_title)
    if len(structural) > 1:
        raise CorpusAnchorResolutionError(f"anchor {anchor!r} is ambiguous in {sidecar_path}")
    raise CorpusAnchorResolutionError(f"anchor {anchor!r} is missing from {sidecar_path}")


def _readable_units(sidecar_path: Path) -> list[tuple[str, str, str]]:
    """Return the ``(anchor, title, text)`` triples of every unit carrying text."""
    try:
        payload = json.loads(sidecar_path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusAnchorResolutionError(f"cannot read extracted sidecar {sidecar_path}") from exc
    raw_units = payload.get("units")
    if not isinstance(raw_units, list):
        raise CorpusAnchorResolutionError(f"extracted sidecar {sidecar_path} has no units list")
    units = [_unit_fields(raw_unit) for raw_unit in raw_units]
    return [(unit_anchor, title, text) for unit_anchor, title, text in units if text]


def _unit_fields(raw_unit: object) -> tuple[str, str, str]:
    if not isinstance(raw_unit, dict):
        return "", "", ""
    return (
        _unit_text(raw_unit.get("anchor")),
        _unit_text(raw_unit.get("title")),
        _unit_text(raw_unit.get("text"), strip=True),
    )


def _unit_text(value: object, *, strip: bool = False) -> str:
    """Read one sidecar text field without leaking the decoder's unknown type."""
    if not isinstance(value, str):
        return ""
    return value.strip() if strip else value


def _render_unit(title: str, text: str, *, include_title: bool) -> str:
    if include_title and title:
        return f"{title}\n{text}"
    return text


def _single_unit_covers_subsection(unit_anchor: str, requested_anchor: str) -> bool:
    declared = _ARTICLE_BASE_ANCHOR_RE.fullmatch(normalise_corpus_text(unit_anchor).lstrip("#"))
    requested = _ARTICLE_SUBSECTION_ANCHOR_RE.match(normalise_corpus_text(requested_anchor).lstrip("#"))
    if declared is None or requested is None:
        return False
    declared_number = declared.group(1)
    requested_number = requested.group(1)
    return (
        isinstance(declared_number, str) and isinstance(requested_number, str) and declared_number == requested_number
    )


#: Two notations for the same article anchor coexist in the corpus: the
#: extractor emits ``#aN`` while the convenio entries were authored as
#: ``#art-N``. They name the same provision, so they are folded to one key
#: rather than being treated as a mismatch. Anchored here rather than fixed at
#: 42 call sites because one rule cannot drift out of step the way 42 edits can,
#: and because a genuine collision (a file declaring both forms) still raises
#: through the existing duplicate check instead of resolving silently.
_ARTICLE_PREFIX_RE: Final = re.compile(r"^(?:articulos?|arts?)(?=\d)")


@lru_cache(maxsize=32768)
def _canonical_anchor(value: str) -> str:
    """Return the comparison key for one anchor or heading.

    Memoised because resolving an anchor canonicalises every unit anchor in the
    sidecar, and a catalogue verification resolves many anchors against the same
    few sidecars: one registry load canonicalised 111,088 times over a far
    smaller set of distinct strings.

    Safe to memoise in a way the file-backed caches around it are not. This is a
    pure function of one string -- module-level regexes and a constant ordinal
    table, no filesystem and no state -- so it cannot serve anything stale, and
    it sees anchors and headings from the bundled BOE corpus, never text from a
    taxpayer's documents.

    The bound is measured, not guessed. One registry load canonicalises 111,088
    times over 2,213 distinct strings -- a 98% hit rate -- while the bundled
    sidecars hold 8,432 distinct anchors and titles in total. The bound clears
    both, so neither a load nor a caller that walks the whole corpus evicts
    anything it is about to need again.
    """
    normalised = _NON_ALNUM_RE.sub("", normalise_corpus_text(value).lstrip("#"))
    for ordinal, number in _SPANISH_ORDINALS.items():
        normalised = normalised.replace(ordinal, number)
    return _ARTICLE_PREFIX_RE.sub("a", normalised, count=1)


def _title_matches_anchor(title: str, target: str) -> bool:
    title_key = _canonical_anchor(title)
    if not title_key:
        return False
    return (
        title_key == target
        or _title_heading_matches_anchor(title, target)
        or _numeric_title_matches_anchor(title_key, target)
        or _prefixed_title_matches_anchor(title_key, target)
        or _article_number_matches_anchor(title_key, target)
    )


def _numeric_title_matches_anchor(title_key: str, target: str) -> bool:
    """Match a bare numeric anchor without widening it to a longer number."""
    return target.isdigit() and (
        title_key == target
        or (title_key.startswith(target) and len(title_key) > len(target) and not title_key[len(target)].isdigit())
    )


def _prefixed_title_matches_anchor(title_key: str, target: str) -> bool:
    """Apply every recognised anchor-prefix expansion in its declared order."""
    for prefix, replacement in _ANCHOR_PREFIXES.items():
        if target.startswith(prefix):
            expanded = replacement + target.removeprefix(prefix)
            if _expanded_anchor_matches_title(title_key, expanded):
                return True
    return False


def _expanded_anchor_matches_title(title_key: str, expanded_anchor: str) -> bool:
    """Match one normalized prefix expansion against a structural title key."""
    if expanded_anchor.startswith("articulo"):
        suffix = expanded_anchor.removeprefix("articulo")
        return (
            _is_exact_article_title_match(title_key, expanded_anchor)
            if suffix.isdigit()
            else title_key.startswith(expanded_anchor)
        )
    if expanded_anchor.startswith("anexo"):
        return title_key == expanded_anchor
    if expanded_anchor.startswith("apartado") and expanded_anchor.removeprefix("apartado").isdigit():
        return title_key == expanded_anchor.removeprefix("apartado")
    return title_key.startswith(expanded_anchor)


def _article_number_matches_anchor(title_key: str, target: str) -> bool:
    """Match the shared canonical article number after all stricter routes fail."""
    anchor_article = _ARTICLE_ANCHOR_RE.match(target)
    title_article = _ARTICLE_TITLE_RE.match(title_key)
    if anchor_article is None or title_article is None:
        return False
    anchor_number = anchor_article.group(1)
    title_number = title_article.group(1)
    return isinstance(anchor_number, str) and isinstance(title_number, str) and anchor_number == title_number


def _is_exact_article_title_match(title_key: str, expanded_anchor: str) -> bool:
    anchor_article = _ARTICLE_TITLE_RE.match(expanded_anchor)
    title_article = _ARTICLE_TITLE_RE.match(title_key)
    if anchor_article is None or title_article is None:
        return False
    anchor_number = anchor_article.group(1)
    title_number = title_article.group(1)
    return isinstance(anchor_number, str) and isinstance(title_number, str) and anchor_number == title_number


def _title_heading_matches_anchor(title: str, target: str) -> bool:
    """Match an article anchor against the title's heading, not its prose.

    Legacy sidecars often persist no anchor, or persist a source anchor that
    differs from the registry's citation anchor.  The heading is the
    load-bearing structural evidence in that case.  Limiting the comparison
    to the text before the first heading delimiter keeps ``a1`` distinct from
    ``a1bis`` while still accepting ordinal and qualified article titles.
    """
    normalised = normalise_corpus_text(title)
    heading = re.split(r"[.:]", normalised, maxsplit=1)[0]
    return _canonical_anchor(heading) == target
