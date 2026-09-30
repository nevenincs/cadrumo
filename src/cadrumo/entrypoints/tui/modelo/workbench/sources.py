"""Where every value in the declaration comes from, as one map grouped the way a filer thinks.

Every box sits in exactly one group, so each group counts boxes, never the
bindings behind them: your records, registers you keep, your profile, earlier
declarations, AEAT data, values you entered or confirmed, your values
replacing another origin, assumed values waiting for confirmation, values that
still need you, calculated values, values the form sets, figures shown for
information, and boxes left blank or that do not apply. The group follows the
box's origin and, for a value that comes from elsewhere, the family the form
names for it, so a value the calculation took from imported AEAT data reads as
AEAT data whatever its binding would otherwise fetch; the view reads both from
the form and decides nothing else.

A group fed by sources names each source and whether it produced anything.
"None found" means the last calculation read that source and it gave nothing,
which differs from a source not read yet because nothing has been calculated,
and from a zero the source did give, which the box shows as its value.

The groups are a list; Enter opens one and shows its boxes below with the
workbench's own row vocabulary, staged changes included. Enter on a box returns
to it in the workbench, which opens its editor where the box can be changed.
``o`` asks the workbench to open the product area that owns the source of the
box under the cursor, such as your records.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, Final, override

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.source_policy import SourceFamily, SourcePolicyV1, SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from .....core.aggregation import BindingSourceKind
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.theme import tokenised
from ...navigation import TuiDestinationIdV1, TuiFocusIdentityV1, TuiNavigationTargetV1
from .casilla_list import (
    AddressKey,
    CasillaList,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
)
from .dialog_width import fit_dialog_width
from .keys import describe_bindings
from .page_items import StagedDisplay


class SourceGroupKind(StrEnum):
    """Where a box's value comes from, as the filer thinks of it; one per box."""

    RECORDS = "records"
    REGISTERS = "registers"
    PROFILE = "profile"
    EARLIER_DECLARATIONS = "earlier_declarations"
    AEAT_DATA = "aeat_data"
    YOURS = "yours"
    REPLACED = "replaced"
    ASSUMED = "assumed"
    NEEDS_YOU = "needs_you"
    CALCULATED = "calculated"
    SET_BY_FORM = "set_by_form"
    INFORMATION = "information"
    BLANK = "blank"
    UNNAMED = "unnamed"


class SourceState(StrEnum):
    """What a source gave this declaration."""

    PRODUCED = "produced"
    NONE_FOUND = "none_found"
    NOT_YET = "not_yet"


SOURCE_GROUP_GLYPHS: Final[Mapping[SourceGroupKind, str]] = MappingProxyType(
    {
        SourceGroupKind.RECORDS: "↓",
        SourceGroupKind.REGISTERS: "↓",
        SourceGroupKind.PROFILE: "↓",
        SourceGroupKind.EARLIER_DECLARATIONS: "«",
        SourceGroupKind.AEAT_DATA: "↓",
        SourceGroupKind.YOURS: "●",
        SourceGroupKind.REPLACED: "≠",
        SourceGroupKind.ASSUMED: "◐",
        SourceGroupKind.NEEDS_YOU: "!",
        SourceGroupKind.CALCULATED: "=",
        SourceGroupKind.SET_BY_FORM: "◇",
        SourceGroupKind.INFORMATION: "i",
        SourceGroupKind.BLANK: "─",
        SourceGroupKind.UNNAMED: "↓",
    }
)
"""The mark in front of each group, every one present in the pinned font."""

_GROUP_LOCALE_KEYS: Final[Mapping[SourceGroupKind, str]] = MappingProxyType(
    {
        SourceGroupKind.RECORDS: "tui.modelo.workbench.sources.group.records",
        SourceGroupKind.REGISTERS: "tui.modelo.workbench.sources.group.registers",
        SourceGroupKind.PROFILE: "tui.modelo.workbench.sources.group.profile",
        SourceGroupKind.EARLIER_DECLARATIONS: "tui.modelo.workbench.sources.group.earlier_declarations",
        SourceGroupKind.AEAT_DATA: "tui.modelo.workbench.sources.group.aeat_data",
        SourceGroupKind.YOURS: "tui.modelo.workbench.sources.group.yours",
        SourceGroupKind.REPLACED: "tui.modelo.workbench.sources.group.replaced",
        SourceGroupKind.ASSUMED: "tui.modelo.workbench.sources.group.assumed",
        SourceGroupKind.NEEDS_YOU: "tui.modelo.workbench.sources.group.needs_you",
        SourceGroupKind.CALCULATED: "tui.modelo.workbench.sources.group.calculated",
        SourceGroupKind.SET_BY_FORM: "tui.modelo.workbench.sources.group.set_by_form",
        SourceGroupKind.INFORMATION: "tui.modelo.workbench.sources.group.information",
        SourceGroupKind.BLANK: "tui.modelo.workbench.sources.group.blank",
        SourceGroupKind.UNNAMED: "tui.modelo.workbench.sources.group.unnamed",
    }
)
_STATE_LOCALE_KEYS: Final[Mapping[SourceState, str]] = MappingProxyType(
    {
        SourceState.NONE_FOUND: "tui.modelo.workbench.sources.none_found",
        SourceState.NOT_YET: "tui.modelo.workbench.sources.not_yet",
    }
)
_FAMILY_GROUPS: Final[Mapping[SourceFamily, SourceGroupKind]] = MappingProxyType(
    {
        SourceFamily.RECORDS: SourceGroupKind.RECORDS,
        SourceFamily.REGISTERS: SourceGroupKind.REGISTERS,
        SourceFamily.PROFILE: SourceGroupKind.PROFILE,
        SourceFamily.EARLIER_FILINGS: SourceGroupKind.EARLIER_DECLARATIONS,
        SourceFamily.AEAT_DRAFT: SourceGroupKind.AEAT_DATA,
        SourceFamily.YOUR_ENTRIES: SourceGroupKind.YOURS,
        SourceFamily.FIXED_BY_DESIGN: SourceGroupKind.SET_BY_FORM,
    }
)
_ORIGIN_GROUPS: Final[Mapping[ModeloFormOrigin, SourceGroupKind]] = MappingProxyType(
    {
        ModeloFormOrigin.ENTERED: SourceGroupKind.YOURS,
        ModeloFormOrigin.CLEARED: SourceGroupKind.YOURS,
        ModeloFormOrigin.OVERRIDES_SOURCE: SourceGroupKind.REPLACED,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: SourceGroupKind.ASSUMED,
        ModeloFormOrigin.NEEDS_INPUT: SourceGroupKind.NEEDS_YOU,
        ModeloFormOrigin.CALCULATED: SourceGroupKind.CALCULATED,
        ModeloFormOrigin.NOT_CALCULATED_YET: SourceGroupKind.CALCULATED,
        ModeloFormOrigin.CALCULATION_FAILED: SourceGroupKind.CALCULATED,
        ModeloFormOrigin.NOT_APPLICABLE: SourceGroupKind.BLANK,
        ModeloFormOrigin.OPTIONAL_EMPTY: SourceGroupKind.BLANK,
    }
)
"""Origins that say by themselves who puts the value there; the rest depend on the source."""

#: Origins whose value, when a source feeds the box, comes from that source.
_SOURCED_ORIGINS: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.NOT_IMPORTED_YET, ModeloFormOrigin.INFORMATIONAL}
)
_LISTED_BOXES: Final[int] = 10
_SURFACE_DESTINATIONS: Final[Mapping[SourceSurface, tuple[TuiDestinationIdV1, str]]] = {
    SourceSurface.LEDGER: ("workbench.ledger", "ledger.overview"),
    SourceSurface.WITHHOLDING: ("workbench.withholding", "withholding.overview"),
    SourceSurface.PROFILE: ("workbench.profile", "profile.overview"),
    SourceSurface.DECLARATIONS: ("workbench.declarations", "declarations.work"),
}
_ENTRY_INDENT: Final[int] = 2
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "escape": "tui.modelo.workbench.key.back",
    "o": "tui.modelo.workbench.sources.key.open",
}
_LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {"enter": "tui.modelo.workbench.sources.key.go"}
_GROUPS_LOCALE_KEYS: Final[Mapping[str, str]] = {"enter": "tui.modelo.workbench.sources.key.expand"}
_GROUP_ID_PREFIX: Final[str] = "group-"


@dataclass(frozen=True, slots=True)
class SourceReading:
    """One source feeding a group: what it gave, and the boxes listed under it."""

    policy: SourcePolicyV1
    state: SourceState
    fields: tuple[ModeloFormField, ...]


@dataclass(frozen=True, slots=True)
class SourceGroup:
    """One group of the map: every box whose value comes from there, and the sources that feed them."""

    kind: SourceGroupKind
    fields: tuple[ModeloFormField, ...]
    readings: tuple[SourceReading, ...] = ()

    @property
    def keys(self) -> frozenset[AddressKey]:
        """The boxes in this group."""
        return frozenset(address_key(field.address) for field in self.fields)


@dataclass(frozen=True, slots=True)
class GoToCasilla:
    """The filer chose a box: return to the workbench on it, in its editor where it can be changed."""

    key: AddressKey


@dataclass(frozen=True, slots=True)
class OpenSourceSurface:
    """The filer asked to open the product area that owns a source."""

    surface: SourceSurface


type SourcesChoice = GoToCasilla | OpenSourceSurface


def value_family(field: ModeloFormField) -> SourceFamily | None:
    """The kind of place a box's value comes from, as the form names it, or ``None`` when nothing feeds it."""
    if field.source is not None:
        return field.source.family
    return field.bindings[0].policy.family if field.bindings else None


def source_group_kind(field: ModeloFormField) -> SourceGroupKind:
    """Place one box in the one group its origin and, for a sourced value, its source family name."""
    if field.editability is ModeloFormEditability.DESIGN_CONSTANT:
        return SourceGroupKind.SET_BY_FORM
    by_origin = _ORIGIN_GROUPS.get(field.origin)
    if by_origin is not None:
        return by_origin
    family = value_family(field)
    if family is not None:
        return _FAMILY_GROUPS[family]
    if field.origin is ModeloFormOrigin.INFORMATIONAL:
        return SourceGroupKind.INFORMATION
    return SourceGroupKind.UNNAMED


def _readings(fields: tuple[ModeloFormField, ...], *, calculated: bool) -> tuple[SourceReading, ...]:
    """Each source of the family a box's value comes from, the boxes it leads for and what it gave.

    A box sits under the first of its sources in that family. A value the AEAT
    data supplied names no source of that family, so its box is listed on its
    own rather than under the source its binding would otherwise read.
    """
    policies: dict[BindingSourceKind, SourcePolicyV1] = {}
    produced: dict[BindingSourceKind, bool] = {}
    led: dict[BindingSourceKind, list[ModeloFormField]] = {}
    for field in fields:
        family = value_family(field)
        matching = [binding for binding in field.bindings if binding.policy.family is family]
        for position, binding in enumerate(matching):
            kind = binding.policy.source_kind
            policies.setdefault(kind, binding.policy)
            produced[kind] = produced.get(kind, False) or binding.resolved
            listed = led.setdefault(kind, [])
            if position == 0:
                listed.append(field)
    readings = []
    for kind, policy in policies.items():
        if produced[kind]:
            state = SourceState.PRODUCED
        else:
            state = SourceState.NONE_FOUND if calculated else SourceState.NOT_YET
        readings.append(SourceReading(policy=policy, state=state, fields=tuple(led[kind])))
    return tuple(readings)


def source_groups(form: ModeloWorkForm) -> tuple[SourceGroup, ...]:
    """Every box of the form in exactly one group, groups in the filer's order, boxes in form order."""
    placed: dict[SourceGroupKind, list[ModeloFormField]] = {}
    for field in form.fields():
        placed.setdefault(source_group_kind(field), []).append(field)
    calculated = form.calculation_revision_id is not None
    groups = []
    for kind in SourceGroupKind:
        fields = tuple(placed.get(kind, ()))
        if not fields:
            continue
        sourced = kind in _FAMILY_GROUPS.values() and any(
            field.origin in _SOURCED_ORIGINS and field.bindings for field in fields
        )
        readings = _readings(fields, calculated=calculated) if sourced else ()
        groups.append(SourceGroup(kind=kind, fields=fields, readings=readings))
    return tuple(groups)


def reading_text(reading: SourceReading) -> str:
    """Name one source, saying when it found nothing or has not been read yet."""
    label = tr(reading.policy.label_key)
    state_key = _STATE_LOCALE_KEYS.get(reading.state)
    return label if state_key is None else tr(state_key, source=label)


def _box_list(fields: tuple[ModeloFormField, ...]) -> str:
    numbers = [f"[{field.box}]" for field in fields if field.box]
    shown = " ".join(numbers[:_LISTED_BOXES])
    rest = len(numbers) - _LISTED_BOXES
    if rest <= 0:
        return shown
    more = tr("tui.modelo.workbench.sources.and_more", count=rest)
    return f"{shown} {more}"


def group_summary(group: SourceGroup) -> str:
    """The second line of a group: its sources, or the boxes that ask something of the filer."""
    if group.readings:
        return " · ".join(reading_text(reading) for reading in group.readings)
    if group.kind in {SourceGroupKind.REPLACED, SourceGroupKind.ASSUMED, SourceGroupKind.NEEDS_YOU}:
        return _box_list(group.fields)
    return ""


def group_words(kind: SourceGroupKind) -> str:
    """A group's mark and name."""
    return f"{SOURCE_GROUP_GLYPHS[kind]} {tr(_GROUP_LOCALE_KEYS[kind])}"


def group_prompt(group: SourceGroup, *, expanded: bool) -> RenderableType:
    """One line of the map: open or closed, the group, its box count and its summary."""
    count = tr("tui.modelo.workbench.sources.count", count=len(group.fields))
    head = Text(f"{'▾' if expanded else '▸'} {group_words(group.kind)} · {count}", style="bold")
    summary = group_summary(group)
    return head if not summary else Group(head, Text(f"  {summary}", style="dim"))


def group_items(group: SourceGroup, *, staged: Mapping[AddressKey, StagedDisplay]) -> tuple[CasillaListItem, ...]:
    """The boxes of one group as list lines, under each source when the group has sources."""

    def entry(field: ModeloFormField, indent: int) -> CasillaListEntry:
        change = staged.get(address_key(field.address))
        return CasillaListEntry(
            field=field,
            indent=indent,
            staged_text=None if change is None else change.text,
            previous_text=None if change is None else change.previous_text,
        )

    items: list[CasillaListItem] = [CasillaListHeading(group_words(group.kind))]
    if not group.readings:
        items.extend(entry(field, 0) for field in group.fields)
        return tuple(items)
    listed: set[AddressKey] = set()
    for reading in group.readings:
        items.append(CasillaListHeading(reading_text(reading), level=1))
        for field in reading.fields:
            listed.add(address_key(field.address))
            items.append(entry(field, _ENTRY_INDENT))
    items.extend(entry(field, 0) for field in group.fields if address_key(field.address) not in listed)
    return tuple(items)


def surface_target(surface: SourceSurface) -> TuiNavigationTargetV1 | None:
    """The product area that owns a source's data, or ``None`` when no area owns it."""
    destination = _SURFACE_DESTINATIONS.get(surface)
    if destination is None:
        return None
    destination_id, semantic_key = destination
    return TuiNavigationTargetV1(
        destination=destination_id,
        focus=TuiFocusIdentityV1(destination=destination_id, semantic_key=semantic_key),
    )


class _GroupList(OptionList):
    """The map's groups, able to describe its own Enter key."""

    def describe_keys(self, descriptions: Mapping[str, str]) -> None:
        describe_bindings(self._bindings.key_to_bindings, descriptions)
        self.refresh_bindings()


class WorkbenchSourcesScreen(ModalScreen[SourcesChoice | None]):
    """Where every value comes from, grouped; opening a group lists its boxes, choosing one returns to it."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchSourcesScreen #sources-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        WorkbenchSourcesScreen #sources-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        WorkbenchSourcesScreen.-narrow #sources-panel {
            width: 100%;
        }
        WorkbenchSourcesScreen #sources-title {
            text-style: bold;
            color: $primary;
        }
        WorkbenchSourcesScreen #sources-intro {
            color: $secondary;
        }
        WorkbenchSourcesScreen #sources-notice {
            color: $warning;
            height: auto;
        }
        WorkbenchSourcesScreen #sources-groups {
            height: 1fr;
            margin-bottom: $cadrumo-stack;
        }
        WorkbenchSourcesScreen #sources-list {
            height: 2fr;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape,q", "close", "", show=False),
        Binding("o", "open_source", "", show=False),
    ]

    def __init__(
        self,
        form: ModeloWorkForm,
        *,
        language: OutputLanguage,
        staged: Mapping[AddressKey, StagedDisplay],
        focus: AddressKey | None = None,
    ) -> None:
        """Hold the form to map, the filer's staged changes and the box to start on."""
        super().__init__()
        self._groups = source_groups(form)
        self._boxes = sum(len(group.fields) for group in self._groups)
        self._staged = staged
        self._language = language
        self._focus = focus
        self._expanded = next(
            (index for index, group in enumerate(self._groups) if focus is not None and focus in group.keys), 0
        )

    @override
    def compose(self) -> ComposeResult:
        with Container(id="sources-backdrop"), Vertical(id="sources-panel"):
            title = tr("tui.modelo.workbench.sources.title")
            count = tr("tui.modelo.workbench.sources.count", count=self._boxes)
            yield Static(f"{title} · {count}", id="sources-title", markup=False)
            intro = tr("tui.modelo.workbench.sources.intro" if self._groups else "tui.modelo.workbench.sources.none")
            yield Static(intro, id="sources-intro", markup=False)
            yield Static("", id="sources-notice", markup=False)
            yield _GroupList(
                *(
                    Option(group_prompt(group, expanded=index == self._expanded), id=f"{_GROUP_ID_PREFIX}{index}")
                    for index, group in enumerate(self._groups)
                ),
                id="sources-groups",
            )
            yield CasillaList(self._current_items(), language=self._language, id="sources-list")
        yield Footer(compact=True)

    def _current_items(self) -> tuple[CasillaListItem, ...]:
        if not self._groups:
            return ()
        return group_items(self._groups[self._expanded], staged=self._staged)

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Describe the keys, open the group of the box to start on and put the cursor on it."""
        fit_dialog_width(self, self.app.size.width)
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS)
        self.refresh_bindings()
        groups = self.query_one(_GroupList)
        groups.describe_keys(_GROUPS_LOCALE_KEYS)
        if self._groups:
            groups.highlighted = self._expanded
        casilla_list = self.query_one(CasillaList)
        casilla_list.describe_keys(_LIST_LOCALE_KEYS)
        if self._focus is not None and casilla_list.focus_address(self._focus):
            casilla_list.focus()
        else:
            groups.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Open the chosen group: list its boxes below and move there."""
        event.stop()
        option_id = event.option.id or ""
        if not option_id.startswith(_GROUP_ID_PREFIX):
            return
        index = int(option_id.removeprefix(_GROUP_ID_PREFIX))
        groups = self.query_one(_GroupList)
        previous = self._expanded
        self._expanded = index
        for changed in {previous, index}:
            groups.replace_option_prompt(
                f"{_GROUP_ID_PREFIX}{changed}", group_prompt(self._groups[changed], expanded=changed == index)
            )
        casilla_list = self.query_one(CasillaList)
        casilla_list.set_items(self._current_items(), language=self._language)
        self.query_one("#sources-notice", Static).update("")
        casilla_list.focus()

    def on_casilla_list_edit_requested(self, message: CasillaList.EditRequested) -> None:
        """Return to the workbench on the chosen box, to change it there."""
        message.stop()
        self.dismiss(GoToCasilla(message.entry.key))

    def action_open_source(self) -> None:
        """Ask to open the product area that owns the source of the box under the cursor."""
        entry = self.query_one(CasillaList).highlighted
        if entry is None:
            return
        notice = self.query_one("#sources-notice", Static)
        if not entry.field.bindings:
            notice.update(tr("tui.modelo.workbench.sources.no_source"))
            return
        policy = entry.field.bindings[0].policy
        if surface_target(policy.surface) is None:
            notice.update(tr("tui.modelo.workbench.sources.no_surface", source=tr(policy.label_key)))
            return
        self.dismiss(OpenSourceSurface(policy.surface))

    def action_close(self) -> None:
        """Return to the workbench where it was."""
        self.dismiss(None)


def _require_total_tables() -> None:
    """Refuse a group without a mark or name, or a source family without a group."""
    if set(SOURCE_GROUP_GLYPHS) != set(SourceGroupKind) or set(_GROUP_LOCALE_KEYS) != set(SourceGroupKind):
        raise ValueError("every source group needs one mark and one name")
    if set(_FAMILY_GROUPS) != set(SourceFamily):
        raise ValueError("every source family needs a group")
    if set(_ORIGIN_GROUPS) | _SOURCED_ORIGINS != set(ModeloFormOrigin):
        raise ValueError("every origin needs a group, or a source to take one from")


_require_total_tables()


__all__ = [
    "SOURCE_GROUP_GLYPHS",
    "GoToCasilla",
    "OpenSourceSurface",
    "SourceGroup",
    "SourceGroupKind",
    "SourceReading",
    "SourceState",
    "SourcesChoice",
    "WorkbenchSourcesScreen",
    "group_items",
    "group_prompt",
    "group_summary",
    "group_words",
    "reading_text",
    "source_group_kind",
    "source_groups",
    "surface_target",
    "value_family",
]
