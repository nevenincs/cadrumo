"""Resolve documentation-only reviewed note languages from versioned metadata."""

from __future__ import annotations

from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from typing import Final, cast

from pydantic import ValidationError

from cadrumo.core.toml import TomlDecodeError, parse_toml
from dev._paths import UTF_8

from .legal_reference_models import LegalNoteLanguageSpan, LegalProvisionRecord, LegalReferenceError

LEGAL_NOTE_LANGUAGES_RELPATH: Final[Path] = Path("dev/docs/metadata/legal_note_languages.toml")


def legal_note_language_ranges(
    notes: str | None, spans: tuple[LegalNoteLanguageSpan, ...]
) -> tuple[tuple[int, int, str], ...]:
    """Refuse stale, ambiguous, duplicate or overlapping exact substrings."""
    ranges: list[tuple[int, int, str]] = []
    for span in spans:
        start = -1 if notes is None else notes.find(span.text)
        if not span.text.strip() or notes is None or start < 0 or notes.find(span.text, start + 1) >= 0:
            raise LegalReferenceError("legal note language span must match exactly once in notes")
        ranges.append((start, start + len(span.text), span.language))
    ordered = sorted(ranges)
    if any(left[1] > right[0] for left, right in pairwise(ordered)):
        raise LegalReferenceError("legal note language spans must not overlap (including duplicate spans)")
    return tuple(ordered)


def _read_entries(path: Path) -> dict[str, object]:
    try:
        data = cast(dict[str, object], parse_toml(path.read_text(encoding=UTF_8)))
    except (OSError, TomlDecodeError) as exc:
        raise LegalReferenceError(f"cannot read legal note language metadata {path}: {exc}") from exc
    if set(data) != {"version", "legal"} or type(data.get("version")) is not int or data["version"] != 1:
        raise LegalReferenceError(f"{path}: expected version = 1 and legal tables only")
    raw = data["legal"]
    if not isinstance(raw, dict):
        raise LegalReferenceError(f"{path}: legal must contain annotation arrays keyed by legal_id")
    return cast(dict[str, object], raw)


def _read_annotations(path: Path, known_ids: set[str]) -> dict[str, tuple[LegalNoteLanguageSpan, ...]]:
    entries = _read_entries(path)
    unknown = set(entries) - known_ids
    if unknown:
        raise LegalReferenceError(f"{path}: unknown legal_id(s): {', '.join(sorted(unknown))}")
    annotations: dict[str, tuple[LegalNoteLanguageSpan, ...]] = {}
    for legal_id, value in entries.items():
        if not isinstance(value, list) or not value:
            raise LegalReferenceError(f"{path}: {legal_id!r} requires a non-empty annotation array")
        try:
            annotations[legal_id] = tuple(
                LegalNoteLanguageSpan.model_validate(item) for item in cast(list[object], value)
            )
        except ValidationError as exc:
            raise LegalReferenceError(f"{path}: {legal_id!r}: invalid language annotations: {exc}") from exc
    return annotations


def apply_legal_note_languages(
    repo_root: Path, records: tuple[LegalProvisionRecord, ...]
) -> tuple[LegalProvisionRecord, ...]:
    """Join reviewed docs metadata by legal ID without changing authority records."""
    path = repo_root / LEGAL_NOTE_LANGUAGES_RELPATH
    if not path.exists():
        return records
    annotations = _read_annotations(path, {record.legal_id for record in records})
    result: list[LegalProvisionRecord] = []
    for record in records:
        spans = annotations.get(record.legal_id, ())
        try:
            legal_note_language_ranges(record.notes, spans)
        except LegalReferenceError as exc:
            raise LegalReferenceError(f"{path}: {record.legal_id!r}: {exc}") from exc
        result.append(replace(record, notes_language_spans=spans))
    return tuple(result)
