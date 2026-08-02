"""Import-light text normalisation and extracted-unit resolution for corpora."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Final

from .errors import CoreError

__all__ = ["CorpusAnchorResolutionError", "normalise_corpus_text", "resolve_anchored_extracted_unit"]

_HTML_TAG_RE = re.compile(r"<[a-zA-Z!/?][^<>\s]{0,200}>")
_COMBINING_MARK_RE = re.compile(r"[\u0300-\u036f]+")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_ARTICLE_ANCHOR_RE = re.compile(r"^(?:a|art|articulo)(\d+)$")
_ARTICLE_TITLE_RE = re.compile(r"^articulo(\d+)")

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
    without_marks = _COMBINING_MARK_RE.sub("", unicodedata.normalize("NFKD", without_tags))
    return _WHITESPACE_RE.sub(" ", without_marks).strip().lower()


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
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusAnchorResolutionError(f"cannot read extracted sidecar {sidecar_path}") from exc
    raw_units = payload.get("units")
    if not isinstance(raw_units, list):
        raise CorpusAnchorResolutionError(f"extracted sidecar {sidecar_path} has no units list")
    units = [_unit_fields(raw_unit) for raw_unit in raw_units]
    units = [(unit_anchor, title, text) for unit_anchor, title, text in units if text]
    if not units:
        raise CorpusAnchorResolutionError(f"extracted sidecar {sidecar_path} has no readable units")

    exact = [(title, text) for unit_anchor, title, text in units if _canonical_anchor(unit_anchor) == target]
    if len(exact) == 1:
        return _render_unit(*exact[0], include_title=include_title)
    if len(exact) > 1:
        raise CorpusAnchorResolutionError(f"anchor {anchor!r} is duplicated in {sidecar_path}")
    if len(units) == 1:
        return _render_unit(*units[0][1:], include_title=include_title)

    structural = [(title, text) for _unit_anchor, title, text in units if _title_matches_anchor(title, target)]
    if len(structural) == 1:
        return _render_unit(*structural[0], include_title=include_title)
    if len(structural) > 1:
        raise CorpusAnchorResolutionError(f"anchor {anchor!r} is ambiguous in {sidecar_path}")
    raise CorpusAnchorResolutionError(f"anchor {anchor!r} is missing from {sidecar_path}")


def _unit_fields(raw_unit: object) -> tuple[str, str, str]:
    if not isinstance(raw_unit, dict):
        return "", "", ""
    raw_anchor = raw_unit.get("anchor")
    raw_title = raw_unit.get("title")
    raw_text = raw_unit.get("text")
    return (
        raw_anchor if isinstance(raw_anchor, str) else "",
        raw_title if isinstance(raw_title, str) else "",
        raw_text.strip() if isinstance(raw_text, str) else "",
    )


def _render_unit(title: str, text: str, *, include_title: bool) -> str:
    if include_title and title:
        return f"{title}\n{text}"
    return text


def _canonical_anchor(value: str) -> str:
    normalised = _NON_ALNUM_RE.sub("", normalise_corpus_text(value).lstrip("#"))
    for ordinal, number in _SPANISH_ORDINALS.items():
        normalised = normalised.replace(ordinal, number)
    return normalised


def _title_matches_anchor(title: str, target: str) -> bool:
    title_key = _canonical_anchor(title)
    if not title_key:
        return False
    if target.isdigit():
        return title_key == target or (
            title_key.startswith(target) and len(title_key) > len(target) and not title_key[len(target)].isdigit()
        )
    for prefix, replacement in _ANCHOR_PREFIXES.items():
        if target.startswith(prefix):
            expanded = replacement + target.removeprefix(prefix)
            if expanded.startswith("articulo"):
                if not expanded.removeprefix("articulo").isdigit():
                    if title_key.startswith(expanded):
                        return True
                    continue
                if _is_exact_article_title_match(title_key, expanded):
                    return True
            elif expanded.startswith("anexo"):
                if title_key == expanded:
                    return True
            elif expanded.startswith("apartado") and expanded.removeprefix("apartado").isdigit():
                if title_key == expanded.removeprefix("apartado"):
                    return True
            elif title_key.startswith(expanded):
                return True
    anchor_article = _ARTICLE_ANCHOR_RE.match(target)
    title_article = _ARTICLE_TITLE_RE.match(title_key)
    return (
        anchor_article is not None and title_article is not None and anchor_article.group(1) == title_article.group(1)
    )


def _is_exact_article_title_match(title_key: str, expanded_anchor: str) -> bool:
    anchor_article = _ARTICLE_TITLE_RE.match(expanded_anchor)
    title_article = _ARTICLE_TITLE_RE.match(title_key)
    return (
        anchor_article is not None and title_article is not None and anchor_article.group(1) == title_article.group(1)
    )
