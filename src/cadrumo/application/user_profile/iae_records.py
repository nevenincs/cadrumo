"""Admitting an IAE premises, surface-class or tax-element row before it reaches the profile write door.

The profile write door judges each fact's shape; it cannot judge whether a row
coheres as the record Modelo 840 reads. This module does, for the three IAE
sections, and the repeatable-row operation runs it inside add and update so a
row the export could not read is never stored:

* a row must cohere as its typed record;
* a local states each Regla 14 surface class once;
* an activity states each Apartado VI A line once;
* a row reference names a row that exists, and a row an IAE row still names
  cannot be removed.

The canonical form returned is the one stored. Every refusal names the leaf and
the generic row command that resolves it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from pydantic import BaseModel

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...domain.contribuyente.iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
    iae_elemento_from_row,
    iae_elemento_row_values,
    iae_local_from_row,
    iae_local_row_values,
    iae_superficie_from_row,
    iae_superficie_row_values,
)
from ...domain.contribuyente.inmueble_facts import rows_from_facts
from ...domain.user_profile.errors import UserProfileValidationError
from .completeness import profile_section_rows
from .rental_records import ProfileRecordRowMutation

_ROW_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.iae_row_invalid"
_ROW_REPEATED_LOCALE_KEY: Final = "application.user_profile.errors.iae_row_repeated"
_REFERENCE_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.iae_row_reference_missing"
_ROW_REFERENCED_LOCALE_KEY: Final = "application.user_profile.errors.iae_row_referenced"

#: The schema's row references, ``(section, field, referenced section)``.
type RowReferences = tuple[tuple[str, str, str], ...]

type _Reader = Callable[[int, Mapping[str, str]], BaseModel]
type _Writer = Callable[..., dict[str, str]]

#: Each section's reader, writer, and the leaves no two of its rows may share.
_SECTIONS: Final[dict[str, tuple[_Reader, _Writer, tuple[str, ...]]]] = {
    IAE_LOCAL_SECTION: (iae_local_from_row, iae_local_row_values, ()),
    IAE_LOCAL_SUPERFICIE_SECTION: (iae_superficie_from_row, iae_superficie_row_values, ("local", "clase")),
    IAE_ELEMENTO_TRIBUTARIO_SECTION: (iae_elemento_from_row, iae_elemento_row_values, ("actividad", "linea")),
}

_DOOR_VERB: Final = {
    ProfileRecordRowMutation.ADD: "add-row",
    ProfileRecordRowMutation.EDIT: "edit-row",
    ProfileRecordRowMutation.REMOVE: "remove-row",
}


def _door(section_key: str, mutation: ProfileRecordRowMutation) -> str:
    return f"aeat config profile {_DOOR_VERB[mutation]} {section_key}"


def is_iae_section(section_key: str) -> bool:
    """Report whether a repeatable section is one of the IAE record sections."""
    return section_key in _SECTIONS


def admit_iae_row(
    section_key: str,
    *,
    row_key: int,
    row: Mapping[str, str],
    path_values: Mapping[str, object],
    references: RowReferences,
    mutation: ProfileRecordRowMutation,
) -> dict[str, str]:
    """Return the stored form of an IAE row, refusing a row the profile cannot hold.

    ``row`` is the complete row as it will stand after the mutation,
    ``path_values`` the profile's facts before it and ``references`` the
    schema's row references.
    """
    reader, writer, unique_leaves = _SECTIONS[section_key]
    try:
        record = reader(row_key, row)
    except ProfileAnswerTypeError as error:
        leaf = (error.context or {}).get("key", "row")
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY,
            context={"leaf": str(leaf), "door": _door(section_key, mutation)},
        ) from error
    stored = writer(record)
    _require_referenced_rows(
        section_key, stored=stored, path_values=path_values, references=references, mutation=mutation
    )
    if unique_leaves:
        _require_unique(section_key, row_key=row_key, stored=stored, leaves=unique_leaves, path_values=path_values)
    return stored


def _require_unique(
    section_key: str,
    *,
    row_key: int,
    stored: Mapping[str, str],
    leaves: tuple[str, ...],
    path_values: Mapping[str, object],
) -> None:
    """Refuse a row whose ``leaves`` repeat those of another stored row of the section."""
    key = tuple(stored.get(leaf) for leaf in leaves)
    for other_key, other in rows_from_facts(section_key, path_values).items():
        if other_key != row_key and tuple(other.get(leaf) for leaf in leaves) == key:
            raise UserProfileValidationError(
                translated_message=_ROW_REPEATED_LOCALE_KEY,
                context={
                    "leaf": leaves[-1],
                    "row": other_key,
                    "door": _door(section_key, ProfileRecordRowMutation.EDIT),
                },
            )


def _require_referenced_rows(
    section_key: str,
    *,
    stored: Mapping[str, str],
    path_values: Mapping[str, object],
    references: RowReferences,
    mutation: ProfileRecordRowMutation,
) -> None:
    """Refuse a row whose reference names no stored row of the referenced section."""
    for source, leaf, target in references:
        if source != section_key or leaf not in stored:
            continue
        if int(stored[leaf]) not in _stored_row_numbers(target, path_values):
            raise UserProfileValidationError(
                translated_message=_REFERENCE_MISSING_LOCALE_KEY,
                context={"leaf": leaf, "row": stored[leaf], "section": target, "door": _door(section_key, mutation)},
            )


def _stored_row_numbers(section_key: str, path_values: Mapping[str, object]) -> set[int]:
    """The row numbers a reference may name: each indexed row, and ``0`` for the unindexed row.

    The setup wizard writes a section's first row without an index
    (``activities.description``), and the row operation reserves slot ``0`` for
    that implicit row, so a reference to ``0`` names it.
    """
    present = (path for path, value in path_values.items() if value is not None and str(value) != "")
    return {int(row) if row else 0 for row in profile_section_rows(section_key, present)}


def require_iae_rows_unreferencing(
    section_key: str, *, row_key: int, path_values: Mapping[str, object], references: RowReferences
) -> None:
    """Refuse removing a row of ``section_key`` that an IAE row still names."""
    for source, leaf, target in references:
        if target != section_key or not is_iae_section(source):
            continue
        naming = sorted(
            key for key, row in rows_from_facts(source, path_values).items() if row.get(leaf) == str(row_key)
        )
        if naming:
            raise UserProfileValidationError(
                translated_message=_ROW_REFERENCED_LOCALE_KEY,
                context={
                    "row": row_key,
                    "section": source,
                    "rows": ", ".join(str(key) for key in naming),
                    "door": _door(source, ProfileRecordRowMutation.REMOVE),
                },
            )


__all__ = ["RowReferences", "admit_iae_row", "is_iae_section", "require_iae_rows_unreferencing"]
