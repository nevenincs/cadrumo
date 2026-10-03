"""Typed page selections over source-bound corpus PDF extractions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.core.corpus_text import CorpusAnchorResolutionError
from cadrumo.core.hashing import sha256_file
from cadrumo.core.hex import HEX_PATTERN_64
from cadrumo.core.type_guards import is_object_dict, is_object_list

CORPUS_PAGE_ANNOTATION_SUFFIX = ".annotation.json"
_PAGE_TITLE = re.compile(r"Pag\. (?P<number>[1-9]\d*)")


class CorpusPageSelection(BaseModel):
    """One stable citation anchor selecting exact PDF extraction pages."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    anchor: str = Field(min_length=1, max_length=160)
    pages: tuple[int, ...] = Field(min_length=1)

    @field_validator("pages")
    @classmethod
    def _pages_are_positive_and_ordered(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(page < 1 for page in value) or tuple(sorted(set(value))) != value:
            raise ValueError("pages must be unique positive integers in document order")
        return value


class CorpusPageAnnotation(BaseModel):
    """Minimal authored selection metadata bound to one immutable PDF."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: Literal[1]
    source_sha256: str = Field(pattern=HEX_PATTERN_64)
    selections: tuple[CorpusPageSelection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _anchors_are_unique(self) -> CorpusPageAnnotation:
        anchors = [selection.anchor.casefold() for selection in self.selections]
        if len(anchors) != len(set(anchors)):
            raise ValueError("selection anchors must be unique")
        return self


def _unique_anchor_selection(annotation: CorpusPageAnnotation, anchor: str, source: Path) -> CorpusPageSelection:
    matches = [selection for selection in annotation.selections if selection.anchor.casefold() == anchor.casefold()]
    if len(matches) != 1:
        raise CorpusAnchorResolutionError(f"PDF annotation anchor {anchor!r} is not unique for {source}")
    return matches[0]


def _page_units(units: list[object], page: int) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for unit in units:
        if not is_object_dict(unit):
            continue
        title = unit.get("title")
        text = unit.get("text")
        if isinstance(title, str) and isinstance(text, str) and text.strip() and _page_number(title) == page:
            matches.append((title, text))
    return matches


def _render_annotated_pages(
    pages: tuple[int, ...],
    units: list[object],
    source: Path,
    include_title: bool,
) -> str:
    rendered: list[str] = []
    for page in pages:
        matches = _page_units(units, page)
        if len(matches) != 1:
            raise CorpusAnchorResolutionError(f"PDF extraction page {page} is not unique for {source}")
        title, text = matches[0]
        rendered.append(f"# {title}\n\n{text}" if include_title else text)
    return "\n\n".join(rendered)


def resolve_annotated_pdf_pages(
    source: Path,
    *,
    anchor: str,
    annotation_path: Path | None = None,
    extracted_path: Path | None = None,
    include_title: bool = False,
) -> str:
    """Resolve one annotation to exact page units from a source-bound extraction.

    ``source`` may be the binary resolved from the companion distribution while
    the small annotation and extraction remain in the command-bearing package.
    Callers therefore may supply those metadata paths independently.
    """
    if annotation_path is None:
        annotation_path = source.with_name(source.name + CORPUS_PAGE_ANNOTATION_SUFFIX)
    if extracted_path is None:
        extracted_path = source.with_name(source.name + ".extracted.json")
    try:
        annotation = CorpusPageAnnotation.model_validate_json(annotation_path.read_text(encoding="utf-8"))
        extracted: object = json.loads(extracted_path.read_text(encoding="utf-8"))
        live_sha256 = sha256_file(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CorpusAnchorResolutionError(f"PDF annotation or extraction is unreadable for {source}") from exc
    if not is_object_dict(extracted):
        raise CorpusAnchorResolutionError(f"PDF extraction is not an object for {source}")
    if annotation.source_sha256 != live_sha256 or extracted.get("source_sha256") != live_sha256:
        raise CorpusAnchorResolutionError(f"PDF annotation or extraction is stale for {source}")
    selection = _unique_anchor_selection(annotation, anchor, source)
    units = extracted.get("units")
    if not is_object_list(units):
        raise CorpusAnchorResolutionError(f"PDF extraction has no units for {source}")
    return _render_annotated_pages(selection.pages, units, source, include_title)


def _page_number(title: str) -> int | None:
    match = _PAGE_TITLE.fullmatch(title)
    return int(match.group("number")) if match is not None else None


__all__ = [
    "CORPUS_PAGE_ANNOTATION_SUFFIX",
    "CorpusPageAnnotation",
    "CorpusPageSelection",
    "resolve_annotated_pdf_pages",
]
