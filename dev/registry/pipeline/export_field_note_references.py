"""Peel official trailing note references while preserving their source order."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from .export_field_derivation import _NOTE_NUMBER_RE, _TRAILING_NOTE_REFERENCE_RE


def _split_official_note_references(content: str) -> tuple[str, tuple[int, ...]]:
    """Peel every trailing ``Nota N`` reference off official content.

    Returns the value-bearing stem and the referenced note numbers in source
    order. A stem that empties out is content consisting only of note
    references, which the numeric derivation treats as its own form.
    """
    stem = content
    notes: list[int] = []
    while (match := _TRAILING_NOTE_REFERENCE_RE.search(stem)) is not None:
        reference = match.group(0)
        number = _NOTE_NUMBER_RE.search(reference)
        if number is None:
            raise RegistryValidationError(
                f"official content {content!r} matched a trailing note reference {reference!r} carrying no note number",
            )
        notes.append(int(number.group("note")))
        stem = stem[: match.start()]
    return stem.strip(), tuple(reversed(notes))
