"""Spatial extraction of declaration casilla values from PDF words."""

from __future__ import annotations

import re
from typing import Any

from ....domain.calculations.registry.schema_extraction import BboxAnchorSpec, ExtractionTargetDefinition
from .errors import DeclaracionParseError

_PdfWord = dict[str, Any]


def _pdf_word_float(word: _PdfWord, key: str) -> float:
    """Return a numeric pdfplumber word coordinate as a concrete float."""
    value = word.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise DeclaracionParseError(f"pdf word field {key!r} is not numeric")


def find_bbox_casilla_hits(
    pages_words: tuple[list[_PdfWord], ...],
    target: ExtractionTargetDefinition,
) -> list[tuple[int, str]]:
    """Find the value word for a ``bbox_anchored`` target using word positions.

    Algorithm:
    1. Scan each page's word list for words matching ``bbox_anchor.box_number_pattern``.
    2. For each anchor-word match, locate the value word using ``value_offset``:
       - ``"right_of_number"``: closest word to the right on the same y-row
         (same ``top`` within ``_BBOX_Y_TOLERANCE`` points, x0 greater than
         the anchor word's x1).
    3. If ``column_anchor`` is set, pre-compute the x-range of the column header
       and constrain the anchor-word search to that x-range.

    Returns a list of ``(1-based page number, raw value text)`` tuples.
    Ambiguous matches (multiple anchors on a page) are returned as multiple
    entries so the caller can detect and report them as ``ambiguous``.
    """
    anchor_spec = _require_bbox_anchor(target)
    box_re = re.compile(anchor_spec.box_number_pattern)

    hits: list[tuple[int, str]] = []

    for page_index, words in enumerate(pages_words, start=1):
        hits.extend(_find_bbox_page_hits(page_index, words, box_re=box_re, anchor_spec=anchor_spec))

    return hits


_BBOX_Y_TOLERANCE: float = 3.0
"""Maximum vertical distance (points) between anchor and value words on the same row."""

_BBOX_X_GAP_TOLERANCE: float = 150.0
"""Maximum horizontal distance (points) to the right for ``right_of_number`` search."""


def _require_bbox_anchor(target: ExtractionTargetDefinition) -> BboxAnchorSpec:
    """Require a bbox target to carry the spatial anchor its strategy names."""
    anchor_spec = target.bbox_anchor
    if anchor_spec is None:
        raise DeclaracionParseError(
            f"extraction target {target.casilla_id!r} takes the bbox-anchored path without a bbox anchor",
        )
    return anchor_spec


def _find_bbox_page_hits(
    page_index: int,
    words: list[_PdfWord],
    *,
    box_re: re.Pattern[str],
    anchor_spec: BboxAnchorSpec,
) -> list[tuple[int, str]]:
    """Resolve every matching bbox anchor on one page into value words."""
    if not words:
        return []
    col_x_min, col_x_max = _bbox_column_bounds(words, anchor_spec)
    anchor_words = _bbox_anchor_words(words, box_re, anchor_spec, col_x_min=col_x_min, col_x_max=col_x_max)
    hits: list[tuple[int, str]] = []
    for anchor_word in anchor_words:
        value_word = _resolve_value_word(
            words,
            anchor_word,
            anchor_spec.value_offset,
            value_x_max=anchor_spec.value_x_max,
        )
        if value_word is not None:
            hits.append((page_index, value_word["text"]))
    return hits


def _bbox_column_bounds(words: list[_PdfWord], anchor_spec: BboxAnchorSpec) -> tuple[float | None, float | None]:
    """Return the optional column constraint for one page's bbox anchors."""
    if anchor_spec.column_anchor is not None and anchor_spec.column_anchor:
        return _find_column_x_range(words, anchor_spec.column_anchor)
    return None, None


def _bbox_anchor_words(
    words: list[_PdfWord],
    box_re: re.Pattern[str],
    anchor_spec: BboxAnchorSpec,
    *,
    col_x_min: float | None,
    col_x_max: float | None,
) -> list[_PdfWord]:
    """Select box-number words inside the target's configured spatial bounds."""
    return [
        word
        for word in words
        if box_re.fullmatch(word["text"])
        and (anchor_spec.anchor_x_min is None or word["x0"] >= anchor_spec.anchor_x_min)
        and (anchor_spec.anchor_x_max is None or word["x0"] <= anchor_spec.anchor_x_max)
        and (col_x_min is None or col_x_max is None or col_x_min <= word["x0"] <= col_x_max)
    ]


def _resolve_value_word(
    words: list[_PdfWord],
    anchor_word: _PdfWord,
    value_offset: str,
    *,
    value_x_max: float | None = None,
) -> _PdfWord | None:
    """Return the value word relative to ``anchor_word`` according to ``value_offset``.

    Args:
        words: All words on the page.
        anchor_word: The located box-number word.
        value_offset: Directional hint — one of ``"right_of_number"``,
            ``"left_of_number"``, or ``"above_number"``.
        value_x_max: When set, restricts ``"right_of_number"`` candidates to
            words whose ``x0`` is at most this value.  Useful in multi-column
            layouts where an empty cell would otherwise match the next column's
            box number.

    Returns:
        The matched value word, or ``None`` if no candidate satisfies the offset
        and proximity constraints.
    """
    if value_offset == "right_of_number":
        return _resolve_right_value_word(words, anchor_word, value_x_max=value_x_max)

    if value_offset == "left_of_number":
        return _resolve_left_value_word(words, anchor_word)

    if value_offset == "above_number":
        return _resolve_above_value_word(words, anchor_word)

    return None  # pragma: no cover — exhaustive via Literal type


def _resolve_right_value_word(
    words: list[_PdfWord],
    anchor_word: _PdfWord,
    *,
    value_x_max: float | None,
) -> _PdfWord | None:
    """Choose the closest same-row word to the right of a box number."""
    anchor_top = anchor_word["top"]
    anchor_x1 = anchor_word["x1"]
    candidates = [
        word
        for word in words
        if abs(word["top"] - anchor_top) <= _BBOX_Y_TOLERANCE
        and word["x0"] > anchor_x1
        and (word["x0"] - anchor_x1) <= _BBOX_X_GAP_TOLERANCE
        and (value_x_max is None or word["x0"] <= value_x_max)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda word: word["x0"])


def _resolve_left_value_word(words: list[_PdfWord], anchor_word: _PdfWord) -> _PdfWord | None:
    """Choose the closest same-row word to the left of a box number."""
    anchor_top = anchor_word["top"]
    anchor_x0 = anchor_word["x0"]
    candidates = [
        word
        for word in words
        if abs(word["top"] - anchor_top) <= _BBOX_Y_TOLERANCE
        and word["x1"] < anchor_x0
        and (anchor_x0 - word["x1"]) <= _BBOX_X_GAP_TOLERANCE
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda word: word["x1"])


def _resolve_above_value_word(words: list[_PdfWord], anchor_word: _PdfWord) -> _PdfWord | None:
    """Choose the nearest vertically preceding word within the anchor column."""
    anchor_top = anchor_word["top"]
    anchor_x0 = anchor_word["x0"]
    anchor_x1 = anchor_word["x1"]
    candidates = [
        word
        for word in words
        if word["bottom"] < anchor_top
        and word["x0"] >= anchor_x0 - _BBOX_Y_TOLERANCE
        and word["x1"] <= anchor_x1 + _BBOX_Y_TOLERANCE
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda word: word["bottom"])


def _find_column_x_range(
    words: list[_PdfWord],
    column_anchor: str,
) -> tuple[float, float]:
    """Return (x_min, x_max) for the column identified by ``column_anchor`` text.

    Finds all words whose text matches ``column_anchor`` (case-insensitive)
    and returns the bounding x-range of those header words.  When no match
    is found, returns ``(0.0, float("inf"))`` (no constraint).
    """
    matches = [w for w in words if w["text"].lower() == column_anchor.lower()]
    if not matches:
        return (0.0, float("inf"))
    x_min = min(_pdf_word_float(w, "x0") for w in matches)
    x_max = max(_pdf_word_float(w, "x1") for w in matches)
    return (x_min, x_max)
