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
Modelo 100 household bindings read from that object and that a row can state, and
the three the mínimo por ascendientes reads: the ascendant's annual rentas, whether
it files its own return and its disability grade. The one leaf the bindings read
but nothing can store (the official disability clave) is not offered. A filer with
no stored ascendant therefore reads as unknown, never as an empty household.

A group says what is known about its rows, never more. ``unknown`` means nothing
was stated and no row is stored; ``none_declared`` means the profile states a
count of zero; ``incomplete`` means the profile states more people than it
records (three stated, one recorded), so the stored rows are served but the group
is not complete. ``stated_count`` and ``row_count`` stay visible beside it, and
``incomplete_words`` says the two numbers in the output language. None of these
may be drawn alike. ``max_rows`` is the most rows the declaration's design holds for the group,
so a surface offers no more people than the declaration can carry.

``leaves`` is also the form of a new row: a surface adding a person offers exactly
those leaves, with their words, types, answer sets and the answers of other leaves
each one is asked after (``shown_when``). ``new_row_leaves`` and each row's ``leaf_asks``
say, per leaf, whether that row is asked it now: the flow engine's own visibility rule
resolved on the row's stated answers, where a leaf whose governing leaf is itself not asked
is never asked, so a surface renders the answer and evaluates no condition. ``add_row_action`` and ``remove_row_action``
serve the words of the two controls and the registered operation that composes the
change against the read's revision: the group's replacement operation takes one new
row (``add_row``) or the ``row_index`` of a served row to remove (``remove_row_index``),
so a surface never resends, and never needs to see, the facts of the people it leaves
alone. A group already holding the most rows its design admits, or whose design
declares no limit, offers no add; a group with no stored row offers no remove.

The descendant leaves are the setup wizard's pages plus the mother's Social Security
contributions after the child's birth, which a descendant row stores and the Modelo
100 calculation reads but the wizard does not ask.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field

from ...core.flows import FlowWidgetKind
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.descendant_disability_catalogue import accepted_descendant_disability_grades
from ...domain.user_profile.labels import profile_field_label_key
from ...domain.user_profile.schema import ProfileFieldType
from ..flows.copy import resolve_copy, resolve_optional_copy
from ..flows.definition import FlowCondition, FlowPage, FlowVisibility, iter_flow_conditions
from ..flows.engine import page_visible
from ..wizard.descendant_group import build_descendant_group
from .completeness import profile_value_is_present
from .household_row_limit import declared_household_row_limit
from .overview import ProfileFieldChoice, mask_profile_field
from .profile_operation_contracts import (
    PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
    PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.user_profile.schema import ProfileFieldDefinition, ProfileSchemaDefinition

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
_ASCENDANT_RENTAS_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.rentas_anuales.label"
_ASCENDANT_RENTAS_HELP_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.rentas_anuales.help"
_ASCENDANT_DECLARACION_PROPIA_LABEL_LOCALE_KEY: Final = (
    "application.user_profile.family_rows.ascendiente.declaracion_propia.label"
)
_ASCENDANT_DECLARACION_PROPIA_HELP_LOCALE_KEY: Final = (
    "application.user_profile.family_rows.ascendiente.declaracion_propia.help"
)
_ASCENDANT_DISCAPACIDAD_LABEL_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.discapacidad.label"
_ASCENDANT_DISCAPACIDAD_HELP_LOCALE_KEY: Final = "application.user_profile.family_rows.ascendiente.discapacidad.help"
_ASCENDANT_ANSWER_LEAVES: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "convivencia_mitad_periodo",
        "application.user_profile.family_rows.ascendiente.convivencia_mitad_periodo.label",
        "application.user_profile.family_rows.ascendiente.convivencia_mitad_periodo.help",
    ),
    (
        "discapacidad_asistencia",
        "application.user_profile.family_rows.ascendiente.discapacidad_asistencia.label",
        "application.user_profile.family_rows.ascendiente.discapacidad_asistencia.help",
    ),
    (
        "incapacidad_judicial",
        "application.user_profile.family_rows.ascendiente.incapacidad_judicial.label",
        "application.user_profile.family_rows.ascendiente.incapacidad_judicial.help",
    ),
)
"""The yes-or-no ascendant leaves served after the grade, with the locale keys of their label and help."""
# The art. 60.3 grade bands are the same for every family member, so their words are shared.
_DISABILITY_GRADE_CHOICE_LOCALE_KEY: Final = "wizard.setup.descendientes.discapacidad.choices.{grade}.label"
_INCOMPLETE_WORDS_LOCALE_KEY: Final = "application.user_profile.family_rows.incomplete"
_DESCENDANT_COTIZACIONES_LEAF: Final = "cotizaciones_ss_madre"
_DESCENDANT_COTIZACIONES_AFTER_LEAF: Final = "gastos_guarderia_mensuales"
_DESCENDANT_COTIZACIONES_LABEL_LOCALE_KEY: Final = (
    "application.user_profile.family_rows.descendiente.cotizaciones_ss_madre.label"
)
_DESCENDANT_COTIZACIONES_HELP_LOCALE_KEY: Final = (
    "application.user_profile.family_rows.descendiente.cotizaciones_ss_madre.help"
)
_ADD_ASCENDANT_LOCALE_KEY: Final = "application.user_profile.family_rows.actions.add_ascendiente"
_REMOVE_ASCENDANT_LOCALE_KEY: Final = "application.user_profile.family_rows.actions.remove_ascendiente"
_ADD_DESCENDANT_LOCALE_KEY: Final = "application.user_profile.family_rows.actions.add_descendiente"
_REMOVE_DESCENDANT_LOCALE_KEY: Final = "application.user_profile.family_rows.actions.remove_descendiente"

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


class ProfileFamilyLeafCondition(BaseModel):
    """One answer of another leaf of the same row; exactly one of ``equals`` and ``contains`` is set.

    ``equals`` holds when that leaf's answer is the token; ``contains`` when the token is
    one of the comma-joined tokens of that answer.
    """

    model_config = STRICT_FROZEN_CONFIG

    leaf: str
    equals: str | None = None
    contains: str | None = None


class ProfileFamilyLeafAsk(StrEnum):
    """Whether a row is asked one leaf now.

    ``asked``: the leaf has no condition, or its condition holds and its governing leaves
    are asked. ``not_asked``: every governing leaf is answered and the condition fails, or a
    governing leaf is not asked. ``awaits_answer``: the condition does not hold and a
    governing leaf has no answer yet. A fact stored on a ``not_asked`` leaf stays stored.
    """

    ASKED = "asked"
    NOT_ASKED = "not_asked"
    AWAITS_ANSWER = "awaits_answer"


class ProfileFamilyLeafAskEntry(BaseModel):
    """The ask resolved for one leaf of a row."""

    model_config = STRICT_FROZEN_CONFIG

    leaf: str
    ask: ProfileFamilyLeafAsk


class ProfileFamilyLeaf(BaseModel):
    """One fact a row can state: its stored key, its words and its answer set."""

    model_config = STRICT_FROZEN_CONFIG

    leaf: str
    label: str
    help: str | None
    field_type: ProfileFieldType
    required: bool
    choices: tuple[ProfileFieldChoice, ...]
    #: The leaf is asked only when one of these holds; empty means it is always asked.
    shown_when: tuple[ProfileFamilyLeafCondition, ...] = ()


class ProfileFamilyRowAction(BaseModel):
    """A control that changes a group's rows: its words and the registered operation it submits."""

    model_config = STRICT_FROZEN_CONFIG

    action_words: str
    target_operation_ids: tuple[str, ...]


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
    #: Adds one row built from ``leaves``; absent when the group takes no more rows.
    add_row_action: ProfileFamilyRowAction | None = None
    #: Removes one served row named by its ``row_index``; absent when no row is stored.
    remove_row_action: ProfileFamilyRowAction | None = None
    #: The ask of every leaf for a blank new row, in ``leaves`` order.
    new_row_leaves: tuple[ProfileFamilyLeafAskEntry, ...] = ()


class ProfileViewFamilyRowItem(BaseModel):
    """One stored row of a group, holding only the facts it states."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["family_row"] = "family_row"
    group_key: str
    row_index: str
    facts: tuple[ProfileFamilyRowFact, ...]
    #: The ask of every leaf of the group for this row's stored answers, in ``leaves`` order.
    leaf_asks: tuple[ProfileFamilyLeafAskEntry, ...] = ()


class ProfileViewFamilyDraftItem(BaseModel):
    """The asks of one row as an unsaved edit states it; no value the edit holds is served back."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["family_draft"] = "family_draft"
    group_key: str
    leaf_asks: tuple[ProfileFamilyLeafAskEntry, ...]


type ProfileFamilyItem = ProfileViewFamilyGroupItem | ProfileViewFamilyRowItem


def _leaf_key(page_id: str) -> str:
    return page_id.replace("-", "_")


def _shown_when(visible_when: FlowCondition | FlowVisibility | None) -> tuple[ProfileFamilyLeafCondition, ...]:
    if visible_when is None:
        return ()
    clauses = visible_when.any_of if isinstance(visible_when, FlowVisibility) else (visible_when,)
    return tuple(
        ProfileFamilyLeafCondition(leaf=_leaf_key(clause.page_id), equals=clause.equals, contains=clause.contains)
        for clause in clauses
    )


def _leaf(page: FlowPage) -> ProfileFamilyLeaf:
    field_type = _WIDGET_FIELD_TYPES[page.widget]
    if field_type is ProfileFieldType.BOOLEAN:
        choices = _yes_no_choices()
    else:
        choices = tuple(ProfileFieldChoice(value=c.value, label=resolve_copy(c.label)) for c in page.choices)
    return ProfileFamilyLeaf(
        leaf=_leaf_key(page.id),
        label=resolve_copy(page.prompt),
        help=resolve_optional_copy(page.help),
        field_type=field_type,
        required=page.required,
        choices=choices,
        shown_when=_shown_when(page.visible_when),
    )


def _parent_unanswered(page_id: str, answers: Mapping[str, str], asks: Mapping[str, ProfileFamilyLeafAsk]) -> bool:
    ask = asks.get(page_id)
    return ask is ProfileFamilyLeafAsk.AWAITS_ANSWER or (ask is ProfileFamilyLeafAsk.ASKED and page_id not in answers)


def _page_ask(
    page: FlowPage, answers: Mapping[str, str], asks: Mapping[str, ProfileFamilyLeafAsk]
) -> ProfileFamilyLeafAsk:
    """One page's ask: the engine's gate over the answers of the leaves that are themselves asked."""
    if page.visible_when is None:
        return ProfileFamilyLeafAsk.ASKED
    asked_answers = {
        page_id: value for page_id, value in answers.items() if asks.get(page_id) is ProfileFamilyLeafAsk.ASKED
    }
    if page_visible(page, asked_answers, instance_prefix=None):
        return ProfileFamilyLeafAsk.ASKED
    parents = {clause.page_id for clause in iter_flow_conditions(page.visible_when)}
    if any(_parent_unanswered(parent, answers, asks) for parent in parents):
        return ProfileFamilyLeafAsk.AWAITS_ANSWER
    return ProfileFamilyLeafAsk.NOT_ASKED


def resolve_leaf_asks(
    pages: tuple[FlowPage, ...], leaf_keys: Sequence[str], row: Mapping[str, str]
) -> tuple[ProfileFamilyLeafAskEntry, ...]:
    """Resolve the ask of each of ``leaf_keys`` for one row's answers; a page with no page is always asked.

    ``pages`` come in dependency order: a page is resolved after the pages it is gated on.
    """
    answers = {
        page.id: row[_leaf_key(page.id)]
        for page in pages
        if _leaf_key(page.id) in row and profile_value_is_present(row[_leaf_key(page.id)])
    }
    asks: dict[str, ProfileFamilyLeafAsk] = {}
    for page in pages:
        asks[page.id] = _page_ask(page, answers, asks)
    by_leaf = {_leaf_key(page_id): ask for page_id, ask in asks.items()}
    return tuple(
        ProfileFamilyLeafAskEntry(leaf=leaf, ask=by_leaf.get(leaf, ProfileFamilyLeafAsk.ASKED)) for leaf in leaf_keys
    )


def _descendant_leaves(pages: tuple[FlowPage, ...]) -> tuple[ProfileFamilyLeaf, ...]:
    """The wizard's descendant pages, with the stored contributions leaf after the nursery spend."""
    wizard = [_leaf(page) for page in pages]
    cotizaciones = ProfileFamilyLeaf(
        leaf=_DESCENDANT_COTIZACIONES_LEAF,
        label=tr(_DESCENDANT_COTIZACIONES_LABEL_LOCALE_KEY),
        help=tr(_DESCENDANT_COTIZACIONES_HELP_LOCALE_KEY),
        field_type=ProfileFieldType.DECIMAL,
        required=False,
        choices=(),
    )
    at = [leaf.leaf for leaf in wizard].index(_DESCENDANT_COTIZACIONES_AFTER_LEAF) + 1
    return (*wizard[:at], cotizaciones, *wizard[at:])


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


def _yes_no_choices() -> tuple[ProfileFieldChoice, ...]:
    return (
        ProfileFieldChoice(value="true", label=tr("flows.confirm.yes")),
        ProfileFieldChoice(value="false", label=tr("flows.confirm.no")),
    )


def _ascendant_leaves(operation: PinnedAuthorityOperation) -> tuple[ProfileFamilyLeaf, ...]:
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
        ProfileFamilyLeaf(
            leaf="rentas_anuales",
            label=tr(_ASCENDANT_RENTAS_LABEL_LOCALE_KEY),
            help=tr(_ASCENDANT_RENTAS_HELP_LOCALE_KEY),
            field_type=ProfileFieldType.DECIMAL,
            required=False,
            choices=(),
        ),
        ProfileFamilyLeaf(
            leaf="declaracion_propia",
            label=tr(_ASCENDANT_DECLARACION_PROPIA_LABEL_LOCALE_KEY),
            help=tr(_ASCENDANT_DECLARACION_PROPIA_HELP_LOCALE_KEY),
            field_type=ProfileFieldType.BOOLEAN,
            required=False,
            choices=_yes_no_choices(),
        ),
        ProfileFamilyLeaf(
            leaf="discapacidad",
            label=tr(_ASCENDANT_DISCAPACIDAD_LABEL_LOCALE_KEY),
            help=tr(_ASCENDANT_DISCAPACIDAD_HELP_LOCALE_KEY),
            field_type=ProfileFieldType.ENUM,
            required=False,
            choices=tuple(
                ProfileFieldChoice(value=str(grade), label=tr(_DISABILITY_GRADE_CHOICE_LOCALE_KEY.format(grade=grade)))
                for grade in sorted(accepted_descendant_disability_grades(authority=operation))
            ),
        ),
        *(
            ProfileFamilyLeaf(
                leaf=leaf,
                label=tr(label),
                help=tr(help_text),
                field_type=ProfileFieldType.BOOLEAN,
                required=False,
                choices=_yes_no_choices(),
            )
            for leaf, label, help_text in _ASCENDANT_ANSWER_LEAVES
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
    pages: tuple[FlowPage, ...],
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
            leaf_asks=resolve_leaf_asks(pages, order, {leaf: values[path] for leaf, path in row.items()}),
        )
        for index, row in sorted(stored.items())
    )


def _row_actions(
    *, row_count: int, max_rows: int | None, actions: tuple[str, str, str]
) -> tuple[ProfileFamilyRowAction | None, ProfileFamilyRowAction | None]:
    """The add and remove controls of a group, each only where the replacement can accept it."""
    operation_id, add_key, remove_key = actions
    can_add = max_rows is not None and row_count < max_rows
    return (
        ProfileFamilyRowAction(action_words=tr(add_key), target_operation_ids=(operation_id,)) if can_add else None,
        ProfileFamilyRowAction(action_words=tr(remove_key), target_operation_ids=(operation_id,))
        if row_count
        else None,
    )


def _group_items(
    values: Mapping[str, str],
    schema: ProfileSchemaDefinition,
    *,
    field_key: str,
    count_path: str,
    pages: tuple[FlowPage, ...],
    leaves: tuple[ProfileFamilyLeaf, ...],
    operation: PinnedAuthorityOperation,
    actions: tuple[str, str, str],
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
    max_rows = declared_household_row_limit(operation, object_path=f"{_SECTION_KEY}.{field_key}")
    add_row_action, remove_row_action = _row_actions(row_count=len(stored), max_rows=max_rows, actions=actions)
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
        max_rows=max_rows,
        leaves=leaves,
        add_row_action=add_row_action,
        remove_row_action=remove_row_action,
        new_row_leaves=resolve_leaf_asks(pages, [leaf.leaf for leaf in leaves], {}),
    )
    rows = _row_items(values, stored, group_key=group.group_key, pages=pages, leaves=leaves, declared=declared)
    return (group, *rows)


def family_row_items(
    values: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
    operation: PinnedAuthorityOperation,
) -> tuple[ProfileFamilyItem, ...]:
    """Return every household group, each followed by its stored rows, in a fixed order."""
    descendant_pages = build_descendant_group(operation).pages
    return (
        *_group_items(
            values,
            schema,
            field_key=_DESCENDANT_FIELD_KEY,
            count_path=_DESCENDANT_COUNT_PATH,
            pages=descendant_pages,
            leaves=_descendant_leaves(descendant_pages),
            operation=operation,
            actions=(
                PROFILE_DESCENDANTS_OPERATION_DEFINITION_ID,
                _ADD_DESCENDANT_LOCALE_KEY,
                _REMOVE_DESCENDANT_LOCALE_KEY,
            ),
        ),
        *_group_items(
            values,
            schema,
            field_key=_ASCENDANT_FIELD_KEY,
            count_path=_ASCENDANT_COUNT_PATH,
            pages=(),
            leaves=_ascendant_leaves(operation),
            operation=operation,
            actions=(
                PROFILE_ASCENDANTS_OPERATION_DEFINITION_ID,
                _ADD_ASCENDANT_LOCALE_KEY,
                _REMOVE_ASCENDANT_LOCALE_KEY,
            ),
        ),
    )


def family_draft_item(
    group_key: str, answers: Mapping[str, str], *, operation: PinnedAuthorityOperation
) -> ProfileViewFamilyDraftItem | None:
    """Resolve the asks of one row as an unsaved edit states it; ``None`` for a group or leaf not served.

    ``answers`` maps leaf keys to the values the edit holds. No stored profile is read or
    written, and no value is returned: only the asks the values resolve to.
    """
    descendant_pages = build_descendant_group(operation).pages
    served: dict[str, tuple[tuple[FlowPage, ...], tuple[ProfileFamilyLeaf, ...]]] = {
        f"{_SECTION_KEY}.{_DESCENDANT_FIELD_KEY}": (descendant_pages, _descendant_leaves(descendant_pages)),
        f"{_SECTION_KEY}.{_ASCENDANT_FIELD_KEY}": ((), _ascendant_leaves(operation)),
    }
    group = served.get(group_key)
    if group is None or not set(answers) <= {leaf.leaf for leaf in group[1]}:
        return None
    pages, leaves = group
    return ProfileViewFamilyDraftItem(
        group_key=group_key, leaf_asks=resolve_leaf_asks(pages, [leaf.leaf for leaf in leaves], answers)
    )
