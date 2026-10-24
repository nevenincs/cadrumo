"""Where every value in the declaration comes from, drawn as one map grouped the way a filer thinks.

The groups, their sources and what each source gave are the application's
(:mod:`cadrumo.application.modelo.work_form_source_groups`); this screen draws
them with the workbench's own marks and row vocabulary and decides nothing
else. A closed group that asks something of the filer lists its box numbers
in at most two lines, then says how many more there are; on a declaration
recorded as filed such a group draws no mark, as its boxes' rows draw none.

The groups are a list; Enter opens one and shows its boxes below with the
workbench's own row vocabulary, staged changes included, and the open group
drops its summary, which the list below already shows. Enter on a box returns
to it in the workbench, which opens its editor where the box can be changed.
``o`` asks the workbench to open the product area that owns the source of the
box under the cursor, such as your records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, override

from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.measure import Measurement
from rich.padding import Padding
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.source_policy import SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormSourceGroupKind,
    ModeloWorkForm,
    address_key,
)
from .....application.modelo.work_form_source_groups import (
    FILED_GROUP_LOCALE_KEYS,
    SourceGroup,
    group_boxes,
    group_name,
    group_summary,
    reading_text,
    source_groups,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.theme import tokenised
from ...navigation import TuiDestinationIdV1, TuiFocusIdentityV1, TuiNavigationTargetV1
from .casilla_list import (
    CasillaList,
)
from .casilla_list_models import (
    AddressKey,
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
)
from .dialog_width import fit_dialog_width
from .keys import describe_bindings
from .page_items import StagedDisplay
from .status_bar import StatusBar
from .vocabulary import (
    COLLAPSED_MARK,
    CONFIRM_MARK,
    EARLIER_FILING_MARK,
    EXPANDED_MARK,
    FORM_SET_MARK,
    MISSING_MARK,
    ORIGIN_MARKS,
    WorkbenchMark,
)

if TYPE_CHECKING:
    from .header import StatusLine


_IMPORTED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.IMPORTED]

SOURCE_GROUP_MARKS: Final[Mapping[ModeloFormSourceGroupKind, WorkbenchMark]] = MappingProxyType(
    {
        ModeloFormSourceGroupKind.RECORDS: _IMPORTED_MARK,
        ModeloFormSourceGroupKind.REGISTERS: _IMPORTED_MARK,
        ModeloFormSourceGroupKind.PROFILE: _IMPORTED_MARK,
        ModeloFormSourceGroupKind.EARLIER_DECLARATIONS: EARLIER_FILING_MARK,
        ModeloFormSourceGroupKind.AEAT_DATA: _IMPORTED_MARK,
        ModeloFormSourceGroupKind.YOURS: ORIGIN_MARKS[ModeloFormOrigin.ENTERED],
        ModeloFormSourceGroupKind.REPLACED: ORIGIN_MARKS[ModeloFormOrigin.OVERRIDES_SOURCE],
        ModeloFormSourceGroupKind.ASSUMED: CONFIRM_MARK,
        ModeloFormSourceGroupKind.NEEDS_YOU: MISSING_MARK,
        ModeloFormSourceGroupKind.CALCULATED: ORIGIN_MARKS[ModeloFormOrigin.CALCULATED],
        ModeloFormSourceGroupKind.SET_BY_FORM: FORM_SET_MARK,
        ModeloFormSourceGroupKind.INFORMATION: ORIGIN_MARKS[ModeloFormOrigin.INFORMATIONAL],
        ModeloFormSourceGroupKind.BLANK: ORIGIN_MARKS[ModeloFormOrigin.NOT_APPLICABLE],
        ModeloFormSourceGroupKind.UNNAMED: _IMPORTED_MARK,
    }
)
"""The mark in front of each group: the one its boxes' rows draw, from the workbench's one vocabulary of marks."""


#: A list of box numbers wraps to at most this many lines, then says how many more there are.
BOX_LIST_LINES: Final[int] = 2
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
class GoToCasilla:
    """The filer chose a box: return to the workbench on it, in its editor where it can be changed."""

    key: AddressKey


@dataclass(frozen=True, slots=True)
class OpenSourceSurface:
    """The filer asked to open the product area that owns a source."""

    surface: SourceSurface


type SourcesChoice = GoToCasilla | OpenSourceSurface


class BoxNumbers:
    """Box numbers in brackets, wrapped to at most a few lines at the width they are drawn at.

    Numbers that do not fit give way, from the end, to a count of how many more
    there are, so a long list never grows into a wall of numbers and never
    loses how many boxes it stands for.
    """

    def __init__(self, boxes: Sequence[str], *, lines: int = BOX_LIST_LINES, style: str = "") -> None:
        """Hold the box numbers, without brackets, and the most lines they may take."""
        self._tokens = tuple(f"[{box}]" for box in boxes)
        self._lines = lines
        self._style = style

    def text(self, console: Console, width: int) -> str:
        """The numbers that fit in the lines at ``width``, followed by how many more there are."""
        width = max(width, 1)
        full = " ".join(self._tokens)
        fitted = self._fitting(width)
        if fitted == len(self._tokens):
            return full
        for shown in range(fitted, -1, -1):
            candidate = self._with_rest(shown)
            if len(Text(candidate).wrap(console, width)) <= self._lines:
                return candidate
        return self._with_rest(0)

    def _fitting(self, width: int) -> int:
        """How many numbers fit in the lines, wrapped between numbers, with nothing after them."""
        line, used = 1, 0
        for fitted, token in enumerate(self._tokens):
            size = cell_len(token)
            if used and used + 1 + size <= width:
                used += 1 + size
            elif not used and size <= width:
                used = size
            elif line < self._lines and size <= width:
                line, used = line + 1, size
            else:
                return fitted
        return len(self._tokens)

    def _with_rest(self, shown: int) -> str:
        more = tr("tui.modelo.workbench.sources.and_more", count=len(self._tokens) - shown)
        return " ".join((*self._tokens[:shown], more))

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Draw the numbers that fit at the width offered."""
        yield Text(self.text(console, options.max_width), style=self._style)

    def __rich_measure__(self, console: Console, options: ConsoleOptions) -> Measurement:
        """Ask for the whole list on one line, and at least the longest number."""
        widest = max((cell_len(token) for token in self._tokens), default=0)
        return Measurement(widest, max(widest, cell_len(" ".join(self._tokens)))).clamp(max_width=options.max_width)


def group_words(
    kind: ModeloFormSourceGroupKind,
    *,
    recorded: bool = False,
    imported_on: date | None = None,
    language: OutputLanguage | None = None,
    none_to_carry: bool = False,
) -> str:
    """A group's mark and name; on a declaration ``recorded`` as filed, a group that would ask names what it holds.

    Such a group draws no mark, as its boxes' rows draw none there.
    """
    name = group_name(kind, language=language, recorded=recorded, imported_on=imported_on, none_to_carry=none_to_carry)
    if recorded and kind in FILED_GROUP_LOCALE_KEYS:
        return f"  {name}"
    return f"{SOURCE_GROUP_MARKS[kind].glyph} {name}"


def _group_words(group: SourceGroup) -> str:
    return group_words(
        group.kind,
        recorded=group.recorded,
        imported_on=group.imported_on,
        none_to_carry=group.none_to_carry,
    )


def group_prompt(group: SourceGroup, *, expanded: bool) -> RenderableType:
    """One entry of the map: open or closed, the group and its box count, and, while closed, its summary.

    An open group lists its sources and boxes below, so its summary would only
    repeat them.
    """
    toggle = EXPANDED_MARK if expanded else COLLAPSED_MARK
    count = tr("tui.modelo.workbench.sources.count", count=len(group.fields))
    head = Text(f"{toggle.glyph} {_group_words(group)} · {count}", style="bold")
    if expanded:
        return head
    summary = group_summary(group)
    boxes = group_boxes(group)
    detail: RenderableType | None = (
        Text(summary, style="dim") if summary else BoxNumbers(boxes, style="dim") if boxes else None
    )
    return head if detail is None else Group(head, Padding(detail, (0, 0, 0, _ENTRY_INDENT)))


def group_items(group: SourceGroup, *, staged: Mapping[AddressKey, StagedDisplay]) -> tuple[CasillaListItem, ...]:
    """The boxes of one group as list lines, under each source when the group has sources."""

    def entry(field: ModeloFormField, indent: int) -> CasillaListEntry:
        change = staged.get(address_key(field.address))
        return CasillaListEntry(
            field=field,
            indent=indent,
            staged_text=None if change is None else change.text,
            previous_text=None if change is None else change.previous_text,
            recorded=group.recorded,
        )

    items: list[CasillaListItem] = [CasillaListHeading(_group_words(group))]
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


def _group_keys(group: SourceGroup) -> frozenset[AddressKey]:
    return frozenset(address_key(field.address) for field in group.fields)


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
        WorkbenchSourcesScreen #sources-status {
            color: $foreground;
            margin-bottom: $cadrumo-stack;
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
        status_line: StatusLine | None = None,
    ) -> None:
        """Hold the form to map, the filer's staged changes and the box to start on.

        ``status_line`` is shown above everything else when given, so the
        declaration's result and deadline stay in view while the map covers the
        workbench's header.
        """
        super().__init__()
        self._status_line = status_line
        self._groups = source_groups(form)
        self._boxes = sum(len(group.fields) for group in self._groups)
        self._staged = staged
        self._language = language
        self._focus = focus
        self._expanded = next(
            (index for index, group in enumerate(self._groups) if focus is not None and focus in _group_keys(group)), 0
        )

    @override
    def compose(self) -> ComposeResult:
        with Container(id="sources-backdrop"), Vertical(id="sources-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="sources-status")
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

    async def refresh_language(self) -> None:
        """Reword the open source map while retaining its group and box cursor."""
        self._language = OutputLanguage(output_language())
        title = tr("tui.modelo.workbench.sources.title")
        count = tr("tui.modelo.workbench.sources.count", count=self._boxes)
        self.query_one("#sources-title", Static).update(f"{title} · {count}")
        self.query_one("#sources-intro", Static).update(
            tr("tui.modelo.workbench.sources.intro" if self._groups else "tui.modelo.workbench.sources.none")
        )
        groups = self.query_one(_GroupList)
        for index, group in enumerate(self._groups):
            groups.replace_option_prompt(
                f"{_GROUP_ID_PREFIX}{index}", group_prompt(group, expanded=index == self._expanded)
            )
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS)
        self.refresh_bindings()
        groups.describe_keys(_GROUPS_LOCALE_KEYS)
        listing = self.query_one(CasillaList)
        listing.describe_keys(_LIST_LOCALE_KEYS)
        listing.set_items(self._current_items(), language=self._language)

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


def _require_total_marks() -> None:
    """Refuse a group without a mark."""
    if set(SOURCE_GROUP_MARKS) != set(ModeloFormSourceGroupKind):
        raise ValueError("every source group needs one mark")


_require_total_marks()


__all__ = [
    "BOX_LIST_LINES",
    "SOURCE_GROUP_MARKS",
    "BoxNumbers",
    "GoToCasilla",
    "OpenSourceSurface",
    "SourcesChoice",
    "WorkbenchSourcesScreen",
    "group_items",
    "group_prompt",
    "group_words",
    "surface_target",
]
