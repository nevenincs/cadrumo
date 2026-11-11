"""The household rows the declaration reads, as typed groups of stated facts.

Descendants are stored as ``renta_family.descendiente.{n}.{leaf}`` facts, which
is the shape the setup wizard, the profile commands and the calculation all use.
The leaves, their wording and their closed answer sets come from the setup
wizard's descendant group, so a surface shows the words the wizard asks with and
keeps none of its own.

The schema also declares ``renta_family.descendants`` and
``renta_family.ascendants`` arrays, but nothing in production writes them, so
they are not a source: reading them would serve an empty list to a filer whose
household is stored in the objects above. Both groups are headed by the label of
their canonical object, never by an array's label.

Ascendants are stored as ``renta_family.ascendiente.{n}.{leaf}`` facts with
``renta_family.ascendientes_count``. The ``user-profile.ascendants`` operation
writes them, and the schema names no leaves, so the leaves served are the ones the
Modelo 100 household bindings read from that object and that a row can state.
The one leaf those bindings read but nothing can store (the official disability
clave) is not offered. A filer with no stored ascendant therefore reads as unknown,
never as an empty household.

A group says what is known about its rows, never more. ``unknown`` means nothing
was stated and no row is stored; ``none_declared`` means the profile states a
count of zero; ``incomplete`` means the profile states more people than it
records (three stated, one recorded), so the stored rows are served but the group
is not complete. ``stated_count`` and ``row_count`` stay visible beside it, and
``incomplete_words`` says the two numbers in the output language. None of these
may be drawn alike. ``max_rows`` is the most rows the declaration's design holds for the group,
so a surface offers no more people than the declaration can carry.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field

from ...core.flows import FlowWidgetKind
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.user_profile.labels import profile_field_label_key
from ...domain.user_profile.schema import ProfileFieldType
from ..flows.copy import resolve_copy, resolve_optional_copy
from ..wizard.descendant_group import build_descendant_group
from .completeness import profile_value_is_present
from .household_row_limit import declared_household_row_limit
from .overview import ProfileFieldChoice, mask_profile_field

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.user_profile.schema import ProfileFieldDefinition, ProfileSchemaDefinition
    from ..flows.definition import FlowPage

_SECTION_KEY: Final = "renta_family"
_DESCENDANT_FIELD_KEY: Final = "descendiente"
_DESCENDANT_COUNT_PATH: Final = "renta_family.descendientes_count"
_ASCENDANT_FIELD_KEY: Final = "ascendiente"
_ASCENDANT_COUNT_PATH: Final = "renta_family.ascendientes_count"

_ASCENDANT_NIF_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.nif.label"
_ASCENDANT_NAME_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.apellidos_nombre.label"
_ASCENDANT_BIRTH_DATE_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.birth_date.label"
_ASCENDANT_FALLECIMIENTO_LABEL_LOCALE_KEY: Final = (
    "application.user_profile.family_rows.ascendiente.fallecimiento.label"
)
_ASCENDANT_FALLECIMIENTO_HELP_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.fallecimiento.help"
_ASCENDANT_CONVIVIENTES_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.convivientes.label"
_INCOMPLETE_WORDS_LOCALE_KEY: Final = "application.user_profile.family_rows.incomplete"

_WIDGET_FIELD_TYPES: Final[Mapping[FlowWidgetKind, ProfileFieldType]] = {
    FlowWidgetKind.DATE: ProfileFieldType.DATE,
    FlowWidgetKind.CONFIRM: ProfileFieldType.BOOLEAN,
    FlowWidgetKind.INTEGER: ProfileFieldType.INTEGER,
    FlowWidgetKind.DECIMAL: ProfileFieldType.DECIMAL,
    FlowWidgetKind.SELECT: ProfileFieldType.ENUM,
    FlowWidgetKind.TEXT: ProfileFieldType.STRING,
}


class ProfileFamilyGroupState(StrEnum):
    """What the profile says about one group of household rows."""

    ROWS = "rows"
    INCOMPLETE = "incomplete"
    NONE_DECLARED = "none_declared"
    UNKNOWN = "unknown"
    NOT_SERVED = "not_served"


class ProfileFamilyLeaf(BaseModel):
    """One fact a row can state: its stored key, its words and its answer set."""

    model_config = STRICT_FROZEN_CONFIG

    leaf: str
    label: str
    help: str | None
    field_type: ProfileFieldType
    required: bool
    choices: tuple[ProfileFieldChoice, ...]


class ProfileFamilyRowFact(BaseModel):
    """One stored fact of a row; a leaf the row does not state is absent, not zero."""

    model_config = STRICT_FROZEN_CONFIG

    leaf: str
    path: str
    value: str
    masked: bool


class ProfileViewFamilyGroupItem(BaseModel):
    """One group of household rows and the leaves its rows can state."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["family_group"] = "family_group"
    group_key: str
    label: str
    state: ProfileFamilyGroupState
    stated_count: str | None = None
    row_count: int = Field(ge=0)
    #: "N stated, M recorded" in the output language; served only for an incomplete group.
    incomplete_words: str | None = None
    #: The most rows the declaration's own design lets the group hold; ``None`` when the design declares none.
    max_rows: int | None = Field(default=None, ge=1)
    leaves: tuple[ProfileFamilyLeaf, ...] = ()


class ProfileViewFamilyRowItem(BaseModel):
    """One stored row of a group, holding only the facts it states."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["family_row"] = "family_row"
    group_key: str
    row_index: str
    facts: tuple[ProfileFamilyRowFact, ...]


type ProfileFamilyItem = ProfileViewFamilyGroupItem | ProfileViewFamilyRowItem


def _leaf_key(page_id: str) -> str:
    return page_id.replace("-", "_")


def _leaf(page: FlowPage) -> ProfileFamilyLeaf:
    field_type = _WIDGET_FIELD_TYPES[page.widget]
    if field_type is ProfileFieldType.BOOLEAN:
        choices = (
            ProfileFieldChoice(value="true", label=tr("flows.confirm.yes")),
            ProfileFieldChoice(value="false", label=tr("flows.confirm.no")),
        )
    else:
        choices = tuple(ProfileFieldChoice(value=c.value, label=resolve_copy(c.label)) for c in page.choices)
    return ProfileFamilyLeaf(
        leaf=_leaf_key(page.id),
        label=resolve_copy(page.prompt),
        help=resolve_optional_copy(page.help),
        field_type=field_type,
        required=page.required,
        choices=choices,
    )


def _declared_field(schema: ProfileSchemaDefinition, field_key: str) -> ProfileFieldDefinition | None:
    for section in schema.sections:
        if section.key == _SECTION_KEY:
            return next((field for field in section.fields if field.key == field_key), None)
    return None


def _stored_rows(values: Mapping[str, str], *, prefix: str, leaves: frozenset[str]) -> dict[int, dict[str, str]]:
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)\.([a-z0-9_]+)$")
    rows: dict[int, dict[str, str]] = {}
    for path, value in values.items():
        match = pattern.match(path)
        if match is not None and match.group(2) in leaves and profile_value_is_present(value):
            rows.setdefault(int(match.group(1)), {})[match.group(2)] = path
    return rows


def _stated_exceeds_rows(stated: str | None, rows: int) -> bool:
    """Whether the stated count is a number larger than the rows stored."""
    if stated is None:
        return False
    try:
        count = Decimal(stated.strip())
    except InvalidOperation:
        return False
    return count.is_finite() and count > rows


def _ascendant_leaves() -> tuple[ProfileFamilyLeaf, ...]:
    return (
        ProfileFamilyLeaf(
            leaf="nif",
            label=tr(_ASCENDANT_NIF_LABEL_LOCALE_KEY),
            help=None,
            field_type=ProfileFieldType.STRING,
            required=False,
            choices=(),
        ),
        ProfileFamilyLeaf(
            leaf="apellidos_nombre",
            label=tr(_ASCENDANT_NAME_LABEL_LOCALE_KEY),
            help=None,
            field_type=ProfileFieldType.STRING,
            required=False,
            choices=(),
        ),
        ProfileFamilyLeaf(
            leaf="birth_date",
            label=tr(_ASCENDANT_BIRTH_DATE_LABEL_LOCALE_KEY),
            help=None,
            field_type=ProfileFieldType.DATE,
            required=True,
            choices=(),
        ),
        ProfileFamilyLeaf(
            leaf="fallecimiento",
            label=tr(_ASCENDANT_FALLECIMIENTO_LABEL_LOCALE_KEY),
            help=tr(_ASCENDANT_FALLECIMIENTO_HELP_LOCALE_KEY),
            field_type=ProfileFieldType.DATE,
            required=False,
            choices=(),
        ),
        ProfileFamilyLeaf(
            leaf="convivientes",
            label=tr(_ASCENDANT_CONVIVIENTES_LABEL_LOCALE_KEY),
            help=None,
            field_type=ProfileFieldType.INTEGER,
            required=False,
            choices=(),
        ),
    )


def _group_state(
    stored: Mapping[int, Mapping[str, str]], count: str | None, *, incomplete: bool
) -> ProfileFamilyGroupState:
    if incomplete:
        return ProfileFamilyGroupState.INCOMPLETE
    if stored:
        return ProfileFamilyGroupState.ROWS
    if count is not None and count.strip() == "0":
        return ProfileFamilyGroupState.NONE_DECLARED
    return ProfileFamilyGroupState.UNKNOWN


def _row_items(
    values: Mapping[str, str],
    stored: Mapping[int, Mapping[str, str]],
    *,
    group_key: str,
    leaves: tuple[ProfileFamilyLeaf, ...],
    declared: ProfileFieldDefinition,
) -> tuple[ProfileViewFamilyRowItem, ...]:
    order = [leaf.leaf for leaf in leaves]
    return tuple(
        ProfileViewFamilyRowItem(
            group_key=group_key,
            row_index=str(index),
            facts=tuple(
                ProfileFamilyRowFact(
                    leaf=leaf,
                    path=row[leaf],
                    value=values[row[leaf]],
                    masked=mask_profile_field(
                        path=row[leaf], label=declared.description, sensitivity=declared.sensitivity
                    ),
                )
                for leaf in order
                if leaf in row
            ),
        )
        for index, row in sorted(stored.items())
    )


def _group_items(
    values: Mapping[str, str],
    schema: ProfileSchemaDefinition,
    *,
    field_key: str,
    count_path: str,
    leaves: tuple[ProfileFamilyLeaf, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[ProfileFamilyItem, ...]:
    declared = _declared_field(schema, field_key)
    if declared is None:
        return ()
    prefix = f"{_SECTION_KEY}.{field_key}."
    stored = _stored_rows(values, prefix=prefix, leaves=frozenset(leaf.leaf for leaf in leaves))
    stated = values.get(count_path)
    count = stated if profile_value_is_present(stated) else None
    incomplete = _stated_exceeds_rows(count, len(stored))
    state = _group_state(stored, count, incomplete=incomplete)
    group = ProfileViewFamilyGroupItem(
        group_key=f"{_SECTION_KEY}.{field_key}",
        label=tr(profile_field_label_key(_SECTION_KEY, field_key)),
        state=state,
        stated_count=count,
        row_count=len(stored),
        incomplete_words=(
            tr(_INCOMPLETE_WORDS_LOCALE_KEY, stated=count.strip(), recorded=len(stored))
            if incomplete and count is not None
            else None
        ),
        max_rows=declared_household_row_limit(operation, object_path=f"{_SECTION_KEY}.{field_key}"),
        leaves=leaves,
    )
    rows = _row_items(values, stored, group_key=group.group_key, leaves=leaves, declared=declared)
    return (group, *rows)


def family_row_items(
    values: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
    operation: PinnedAuthorityOperation,
) -> tuple[ProfileFamilyItem, ...]:
    """Return every household group, each followed by its stored rows, in a fixed order."""
    return (
        *_group_items(
            values,
            schema,
            field_key=_DESCENDANT_FIELD_KEY,
            count_path=_DESCENDANT_COUNT_PATH,
            leaves=tuple(_leaf(page) for page in build_descendant_group(operation).pages),
            operation=operation,
        ),
        *_group_items(
            values,
            schema,
            field_key=_ASCENDANT_FIELD_KEY,
            count_path=_ASCENDANT_COUNT_PATH,
            leaves=_ascendant_leaves(),
            operation=operation,
        ),
    )
