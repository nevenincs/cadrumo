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

A group fed by sources names each source and whether it produced anything; a
value carried from an earlier declaration names that declaration when the form
does, and the AEAT data by the day it was imported when the form knows it. A
carry with no earlier declaration to read from names none: the group says
there is none, and its source reads as having found nothing.
"None found" means the last calculation read that source and it gave
nothing, which differs from a source not read yet because nothing has been
calculated, and from a zero the source did give, which the box shows as its
value. A closed group that asks something of the filer lists its box numbers
in at most two lines, then says how many more there are. A declaration
recorded as filed asks nothing more, so its assumed values and the values it
was filed without keep their own groups, named for what they hold rather than
for what they ask, without the mark that asks.

The groups are a list; Enter opens one and shows its boxes below with the
workbench's own row vocabulary, staged changes included, and the open group
drops its summary, which the list below already shows. Enter on a box returns
to it in the workbench, which opens its editor where the box can be changed.
``o`` asks the workbench to open the product area that owns the source of the
box under the cursor, such as your records.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
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

from .....application.modelo.source_policy import SourceFamily, SourcePolicyV1, SourceSurface
from .....application.modelo.work_form_models import (
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from .....core.aggregation import BindingSourceKind
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
    aeat_imported_on,
    no_earlier_filing,
)
from .wording import date_text, modelo_number, period_words

if TYPE_CHECKING:
    from .header import StatusLine


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


_IMPORTED_MARK: Final[WorkbenchMark] = ORIGIN_MARKS[ModeloFormOrigin.IMPORTED]

SOURCE_GROUP_MARKS: Final[Mapping[SourceGroupKind, WorkbenchMark]] = MappingProxyType(
    {
        SourceGroupKind.RECORDS: _IMPORTED_MARK,
        SourceGroupKind.REGISTERS: _IMPORTED_MARK,
        SourceGroupKind.PROFILE: _IMPORTED_MARK,
        SourceGroupKind.EARLIER_DECLARATIONS: EARLIER_FILING_MARK,
        SourceGroupKind.AEAT_DATA: _IMPORTED_MARK,
        SourceGroupKind.YOURS: ORIGIN_MARKS[ModeloFormOrigin.ENTERED],
        SourceGroupKind.REPLACED: ORIGIN_MARKS[ModeloFormOrigin.OVERRIDES_SOURCE],
        SourceGroupKind.ASSUMED: CONFIRM_MARK,
        SourceGroupKind.NEEDS_YOU: MISSING_MARK,
        SourceGroupKind.CALCULATED: ORIGIN_MARKS[ModeloFormOrigin.CALCULATED],
        SourceGroupKind.SET_BY_FORM: FORM_SET_MARK,
        SourceGroupKind.INFORMATION: ORIGIN_MARKS[ModeloFormOrigin.INFORMATIONAL],
        SourceGroupKind.BLANK: ORIGIN_MARKS[ModeloFormOrigin.NOT_APPLICABLE],
        SourceGroupKind.UNNAMED: _IMPORTED_MARK,
    }
)
"""The mark in front of each group: the one its boxes' rows draw, from the workbench's one vocabulary of marks."""

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
_FILED_GROUP_LOCALE_KEYS: Final[Mapping[SourceGroupKind, str]] = MappingProxyType(
    {
        SourceGroupKind.ASSUMED: "tui.modelo.workbench.sources.group_filed.assumed",
        SourceGroupKind.NEEDS_YOU: "tui.modelo.workbench.sources.group_filed.needs_you",
    }
)
"""Names for the groups that ask for a value, on a declaration recorded as filed: what they hold, not a request."""
_AEAT_IMPORTED_ON_LOCALE_KEY: Final[str] = "tui.modelo.workbench.sources.group.aeat_data_imported_on"
_NO_EARLIER_GROUP_LOCALE_KEY: Final[str] = "tui.modelo.workbench.sources.group.earlier_declarations_none"
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
#: Groups that ask something of the filer, so a closed group lists their box numbers.
_BOX_LISTING_GROUPS: Final[frozenset[SourceGroupKind]] = frozenset(
    {SourceGroupKind.REPLACED, SourceGroupKind.ASSUMED, SourceGroupKind.NEEDS_YOU}
)
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
class SourceReading:
    """One source feeding a group: what it gave, and the boxes listed under it."""

    policy: SourcePolicyV1
    state: SourceState
    fields: tuple[ModeloFormField, ...]
    #: The earlier declarations its boxes are carried from, when the form names them.
    earlier_filings: tuple[ModeloFormEarlierFiling, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceGroup:
    """One group of the map: every box whose value comes from there, and the sources that feed them."""

    kind: SourceGroupKind
    fields: tuple[ModeloFormField, ...]
    readings: tuple[SourceReading, ...] = ()
    #: The declaration is recorded as filed, so the group asks nothing of the filer.
    recorded: bool = False
    #: For the AEAT data group, the day the data was imported, when the form knows it.
    imported_on: date | None = None

    @property
    def keys(self) -> frozenset[AddressKey]:
        """The boxes in this group."""
        return frozenset(address_key(field.address) for field in self.fields)

    @property
    def none_to_carry(self) -> bool:
        """Whether this is the earlier-declarations group and none of its boxes has an earlier declaration to read."""
        return self.kind is SourceGroupKind.EARLIER_DECLARATIONS and all(
            no_earlier_filing(field) for field in self.fields
        )


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
    """Place one box in the one group its origin and, for a sourced value, its source family name.

    A value nobody entered stays in its own group on a declaration recorded as
    filed too: it was never calculated, only held, and the group's name then
    says so without asking for a confirmation.
    """
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


def _collect_field_sources(
    field: ModeloFormField,
    family: SourceFamily | None,
    policies: dict[BindingSourceKind, SourcePolicyV1],
    produced: dict[BindingSourceKind, bool],
    led: dict[BindingSourceKind, list[ModeloFormField]],
) -> None:
    matching = [binding for binding in field.bindings if binding.policy.family is family]
    for position, binding in enumerate(matching):
        kind = binding.policy.source_kind
        policies.setdefault(kind, binding.policy)
        produced[kind] = produced.get(kind, False) or binding.resolved
        listed = led.setdefault(kind, [])
        if position == 0:
            listed.append(field)


def _reading_state(
    kind: BindingSourceKind,
    fields: list[ModeloFormField],
    produced: Mapping[BindingSourceKind, bool],
    *,
    calculated: bool,
) -> SourceState:
    if fields and all(no_earlier_filing(field) for field in fields):
        # A carry with no earlier declaration to read produced nothing, whatever zero it resolved to.
        return SourceState.NONE_FOUND
    if produced[kind]:
        return SourceState.PRODUCED
    return SourceState.NONE_FOUND if calculated else SourceState.NOT_YET


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
        _collect_field_sources(field, family, policies, produced, led)
    readings = []
    for kind, policy in policies.items():
        state = _reading_state(kind, led[kind], produced, calculated=calculated)
        readings.append(
            SourceReading(
                policy=policy, state=state, fields=tuple(led[kind]), earlier_filings=earlier_filings(led[kind])
            )
        )
    return tuple(readings)


def earlier_filings(fields: Iterable[ModeloFormField]) -> tuple[ModeloFormEarlierFiling, ...]:
    """The earlier declarations the form names as the origin of these boxes, each once, in form order."""
    named: dict[ModeloFormEarlierFiling, None] = {}
    for field in fields:
        source = field.source
        if source is not None and source.family is SourceFamily.EARLIER_FILINGS:
            named.update(dict.fromkeys(source.earlier_filings))
    return tuple(named)


def earlier_filing_text(filings: Sequence[ModeloFormEarlierFiling]) -> str:
    """Name earlier declarations by their modelo and period in words."""
    return ", ".join(f"{modelo_number(filing.modelo)} · {period_words(filing.period)}" for filing in filings)


def source_groups(form: ModeloWorkForm) -> tuple[SourceGroup, ...]:
    """Every box of the form in exactly one group, groups in the filer's order, boxes in form order."""
    recorded = form.filing is not None
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
        imported_on = aeat_imported_on(form) if kind is SourceGroupKind.AEAT_DATA else None
        groups.append(
            SourceGroup(kind=kind, fields=fields, readings=readings, recorded=recorded, imported_on=imported_on)
        )
    return tuple(groups)


def reading_text(reading: SourceReading) -> str:
    """Name one source, by the earlier declaration when the form names it, saying when it found nothing yet."""
    label = earlier_filing_text(reading.earlier_filings) if reading.earlier_filings else tr(reading.policy.label_key)
    state_key = _STATE_LOCALE_KEYS.get(reading.state)
    return label if state_key is None else tr(state_key, source=label)


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


def group_boxes(group: SourceGroup) -> tuple[str, ...]:
    """The box numbers a closed group lists, for the groups that ask something of the filer."""
    if group.kind not in _BOX_LISTING_GROUPS:
        return ()
    return tuple(field.box for field in group.fields if field.box)


def group_summary(group: SourceGroup) -> str:
    """The sources of a group in words, or the earlier declarations its boxes are carried from."""
    if group.readings:
        return " · ".join(reading_text(reading) for reading in group.readings)
    if group.kind is SourceGroupKind.EARLIER_DECLARATIONS:
        return earlier_filing_text(earlier_filings(group.fields))
    return ""


def group_words(
    kind: SourceGroupKind,
    *,
    recorded: bool = False,
    imported_on: date | None = None,
    language: OutputLanguage | None = None,
    none_to_carry: bool = False,
) -> str:
    """A group's mark and name; on a declaration ``recorded`` as filed, a group that would ask names what it holds.

    Such a group draws no mark, as its boxes' rows draw none there. The AEAT
    data group names the day ``imported_on`` the data was imported, written
    for ``language``, the active output language when not given. An
    earlier-declarations group with ``none_to_carry`` says there is no earlier
    declaration to read.
    """
    if recorded and kind in _FILED_GROUP_LOCALE_KEYS:
        return f"  {tr(_FILED_GROUP_LOCALE_KEYS[kind])}"
    glyph = SOURCE_GROUP_MARKS[kind].glyph
    if kind is SourceGroupKind.EARLIER_DECLARATIONS and none_to_carry:
        return f"{glyph} {tr(_NO_EARLIER_GROUP_LOCALE_KEY)}"
    if kind is SourceGroupKind.AEAT_DATA and imported_on is not None:
        written = date_text(imported_on, OutputLanguage(output_language()) if language is None else language)
        return f"{glyph} {tr(_AEAT_IMPORTED_ON_LOCALE_KEY, date=written)}"
    return f"{glyph} {tr(_GROUP_LOCALE_KEYS[kind])}"


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
            (index for index, group in enumerate(self._groups) if focus is not None and focus in group.keys), 0
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
    if set(SOURCE_GROUP_MARKS) != set(SourceGroupKind) or set(_GROUP_LOCALE_KEYS) != set(SourceGroupKind):
        raise ValueError("every source group needs one mark and one name")
    if set(_FAMILY_GROUPS) != set(SourceFamily):
        raise ValueError("every source family needs a group")
    if set(_ORIGIN_GROUPS) | _SOURCED_ORIGINS != set(ModeloFormOrigin):
        raise ValueError("every origin needs a group, or a source to take one from")


_require_total_tables()


__all__ = [
    "BOX_LIST_LINES",
    "SOURCE_GROUP_MARKS",
    "BoxNumbers",
    "GoToCasilla",
    "OpenSourceSurface",
    "SourceGroup",
    "SourceGroupKind",
    "SourceReading",
    "SourceState",
    "SourcesChoice",
    "WorkbenchSourcesScreen",
    "earlier_filing_text",
    "earlier_filings",
    "group_boxes",
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
