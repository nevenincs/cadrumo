"""The words and doors the grouped profile read serves beside each row it lists.

Every item of the stream says what kind of thing it is, every stored row carries
its edit and remove doors, and a refused page says why, all in the output
language, so a surface renders served words and routes a door by the registered
operation it names without naming one itself.

The doors submit the registered repeatable-row operations that already edit and
remove these rows; their identities are imported from the defining contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ...core.i18n.render import tr
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ..prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from .profile_operation_contracts import (
    PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID,
    PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID,
)
from .record_group_contracts import (
    PENSION_CONTRIBUTION_SECTION_KEY,
    ProfileRecordAction,
    ProfileRecordDoor,
    ProfileRecordGroupKind,
    ProfileRecordGroupsRefusalCode,
)
from .record_row_words import summarised_sections

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage

GROUP_KIND_WORDS_LOCALE_KEYS: Final[Mapping[ProfileRecordGroupKind, str]] = MappingProxyType(
    {
        ProfileRecordGroupKind.RENTAL_PROPERTY: "application.user_profile.record_groups.kind.rental_property",
        ProfileRecordGroupKind.PENSION_CONTRIBUTION: "application.user_profile.record_groups.kind.pension_contribution",
    }
)
"""What each kind of group is."""

SECTION_KIND_WORDS_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        INMUEBLE_SECTION: "application.user_profile.record_groups.kind.renta_inmueble",
        ARRENDAMIENTO_SECTION: "application.user_profile.record_groups.kind.renta_arrendamiento",
        PENSION_CONTRIBUTION_SECTION_KEY: "application.user_profile.record_groups.kind.prevision_social_contribution",
    }
)
"""What a member row of each listed section is."""

LEDGER_ROW_KIND_WORDS_LOCALE_KEY: Final = "application.user_profile.record_groups.kind.ledger_row"
"""What a ledger row naming a group's row is."""

EDIT_DOOR_LABEL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        INMUEBLE_SECTION: "application.user_profile.record_groups.door.renta_inmueble.edit",
        ARRENDAMIENTO_SECTION: "application.user_profile.record_groups.door.renta_arrendamiento.edit",
        PENSION_CONTRIBUTION_SECTION_KEY: (
            "application.user_profile.record_groups.door.prevision_social_contribution.edit"
        ),
    }
)
"""The short label of the edit door of a row of each listed section."""

REMOVE_DOOR_LABEL_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        INMUEBLE_SECTION: "application.user_profile.record_groups.door.renta_inmueble.remove",
        ARRENDAMIENTO_SECTION: "application.user_profile.record_groups.door.renta_arrendamiento.remove",
        PENSION_CONTRIBUTION_SECTION_KEY: (
            "application.user_profile.record_groups.door.prevision_social_contribution.remove"
        ),
    }
)
"""The short label of the remove door of a row of each listed section."""

REFUSAL_WORDS_LOCALE_KEYS: Final[Mapping[ProfileRecordGroupsRefusalCode, str]] = MappingProxyType(
    {
        ProfileRecordGroupsRefusalCode.STALE_REVISION: "application.user_profile.record_groups.refusal.stale_revision",
        ProfileRecordGroupsRefusalCode.ITEM_TOO_LARGE: "application.user_profile.record_groups.refusal.item_too_large",
    }
)
"""Why a page was refused and what the operator does next."""

_PROFILE_ROW_SECTIONS: Final = (INMUEBLE_SECTION, ARRENDAMIENTO_SECTION)


def _door_operations(profile_row_operation: str, pension_operation: str) -> Mapping[str, str]:
    """Map each served section to the registered operation its door submits."""
    return MappingProxyType(
        {
            **dict.fromkeys(_PROFILE_ROW_SECTIONS, profile_row_operation),
            PENSION_CONTRIBUTION_SECTION_KEY: pension_operation,
        }
    )


_DOORS: Final[tuple[tuple[ProfileRecordDoor, Mapping[str, str], Mapping[str, str]], ...]] = (
    (
        ProfileRecordDoor.EDIT,
        _door_operations(
            PROFILE_REPEATABLE_ROW_UPDATE_OPERATION_DEFINITION_ID, PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID
        ),
        EDIT_DOOR_LABEL_LOCALE_KEYS,
    ),
    (
        ProfileRecordDoor.REMOVE,
        _door_operations(
            PROFILE_REPEATABLE_ROW_REMOVE_OPERATION_DEFINITION_ID, PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID
        ),
        REMOVE_DOOR_LABEL_LOCALE_KEYS,
    ),
)
"""Each door, the registered operation it submits and its labels, by section, in the order a surface shows them."""


def group_kind_words(kind: ProfileRecordGroupKind) -> str:
    """Return what a group of ``kind`` is, in the output language."""
    return tr(GROUP_KIND_WORDS_LOCALE_KEYS[kind])


def member_kind_words(section_key: str) -> str:
    """Return what a member row of ``section_key`` is, in the output language."""
    return tr(SECTION_KIND_WORDS_LOCALE_KEYS[section_key])


def ledger_row_kind_words() -> str:
    """Return what a ledger row naming a group's row is, in the output language."""
    return tr(LEDGER_ROW_KIND_WORDS_LOCALE_KEY)


def refusal_words(code: ProfileRecordGroupsRefusalCode) -> str:
    """Return why a page was refused with ``code``, in the output language."""
    return tr(REFUSAL_WORDS_LOCALE_KEYS[code])


def row_actions(section_key: str, language: OutputLanguage) -> tuple[ProfileRecordAction, ...]:
    """Return the edit and remove doors of one stored row of ``section_key``, labelled in the output language."""
    return tuple(
        ProfileRecordAction(
            door=door,
            operation_definition_id=operations[section_key],
            label_words=tr(labels[section_key]),
            label_words_language=language,
        )
        for door, operations, labels in _DOORS
    )


def _require_total_tables() -> None:
    sections = summarised_sections() | {PENSION_CONTRIBUTION_SECTION_KEY}
    if set(SECTION_KIND_WORDS_LOCALE_KEYS) != sections:
        raise ValueError("every listed record section needs its kind words")
    if any(set(labels) != sections or set(operations) != sections for _door, operations, labels in _DOORS):
        raise ValueError("every door of every listed record section needs its operation and label")
    if set(GROUP_KIND_WORDS_LOCALE_KEYS) != set(ProfileRecordGroupKind):
        raise ValueError("every record group kind needs its kind words")
    if set(REFUSAL_WORDS_LOCALE_KEYS) != set(ProfileRecordGroupsRefusalCode):
        raise ValueError("every record group refusal needs its words")
    if {door for door, _operations, _labels in _DOORS} != set(ProfileRecordDoor):
        raise ValueError("every record door needs its registered operation")


_require_total_tables()

__all__ = [
    "EDIT_DOOR_LABEL_LOCALE_KEYS",
    "GROUP_KIND_WORDS_LOCALE_KEYS",
    "LEDGER_ROW_KIND_WORDS_LOCALE_KEY",
    "REFUSAL_WORDS_LOCALE_KEYS",
    "REMOVE_DOOR_LABEL_LOCALE_KEYS",
    "SECTION_KIND_WORDS_LOCALE_KEYS",
    "group_kind_words",
    "ledger_row_kind_words",
    "member_kind_words",
    "refusal_words",
    "row_actions",
]
