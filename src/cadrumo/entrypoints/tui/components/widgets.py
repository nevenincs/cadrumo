"""Reusable, state-free Textual widgets for Cadrumo surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, override

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import Button, Collapsible, DataTable, Static
from textual.widgets.data_table import Column, ColumnKey

from ....core.presentation import NoticePresentation
from .theme import CADRUMO_CSS_TOKENS, tokenised


def _resolve_fill_column_key(keys: Sequence[ColumnKey], fill_column: int | None) -> ColumnKey | None:
    """Resolve the configured fill index without making a missing column fatal."""
    if fill_column is None:
        return None
    try:
        return keys[fill_column]
    except IndexError:  # pragma: no cover - a table without that column
        return None


def _current_column_widths(columns: Sequence[tuple[ColumnKey, int, int, int]]) -> dict[ColumnKey, int]:
    """Return current widths, preserving the no-shrink part of the policy."""
    return {key: current_width for key, current_width, _header_width, _natural_width in columns}


def _header_floor_widths(columns: Sequence[tuple[ColumnKey, int, int, int]]) -> dict[ColumnKey, int]:
    """Raise each current width to its header floor."""
    return {key: max(current_width, header_width) for key, current_width, header_width, _ in columns}


def _natural_non_fill_width(columns: Sequence[tuple[ColumnKey, int, int, int]], fill_key: ColumnKey | None) -> int:
    """Sum natural widths for every column except the fill target."""
    return sum(natural_width for key, _current, _header, natural_width in columns if key is not fill_key)


def _fill_header_width(columns: Sequence[tuple[ColumnKey, int, int, int]], fill_key: ColumnKey | None) -> int:
    """Return the fill column's header floor, or zero when there is no target."""
    return next(
        (header_width for key, _current, header_width, _natural in columns if key is fill_key),
        0,
    )


def _grow_non_fill_widths(
    widths: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    fill_key: ColumnKey | None,
) -> None:
    """Grow non-fill columns to natural widths without shrinking any column."""
    for key, _current, _header, natural_width in columns:
        if key is not fill_key and widths[key] < natural_width:
            widths[key] = natural_width


def _current_non_fill_width(
    widths: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    fill_key: ColumnKey,
    cell_padding: int,
) -> int:
    """Sum rendered non-fill widths, including both cell-padding sides."""
    return sum(widths[key] + cell_padding * 2 for key, _current, _header, _natural in columns if key is not fill_key)


def _allocate_column_widths(
    available: int,
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    *,
    fill_key: ColumnKey | None,
    cell_padding: int,
) -> dict[ColumnKey, int]:
    """Apply the table's deterministic header, natural, and surplus width policy.

    Each column tuple carries ``(key, current_width, header_width,
    natural_width)``. Header widths are floors for every column. Non-fill
    columns grow to their natural widths only when doing so leaves the fill
    column's header visible; remaining width then belongs to the configured
    fill column alone. The returned mapping never shrinks a current width.
    """
    if available <= 0:
        return _current_column_widths(columns)

    widths = _header_floor_widths(columns)
    padding = cell_padding * 2 * len(columns)
    natural_non_fill_width = _natural_non_fill_width(columns, fill_key)
    fill_floor = _fill_header_width(columns, fill_key)
    if fill_key is None or available - natural_non_fill_width - padding >= fill_floor:
        _grow_non_fill_widths(widths, columns, fill_key)

    if fill_key is not None:
        surplus = available - _current_non_fill_width(widths, columns, fill_key, cell_padding) - cell_padding * 2
        if surplus > widths[fill_key]:
            widths[fill_key] = surplus
    return widths


class ContentScroll(VerticalScroll, can_focus=False):
    """The scroll host every Cadrumo surface puts its content column in."""


class ContentDataTable[CellType](DataTable[CellType]):
    """A table that expands to its rows, and to the width it is given.

    Textual's own ``add_column`` offers a fixed cell count or shrink-to-fit and
    nothing between, so a table built from fixed widths keeps them however wide
    the terminal is: it clips its own headers and identifiers while the rest of
    the row sits empty. The height side of that problem was already solved here
    by ``watch_virtual_size``; this is its missing counterpart.

    The surplus goes to ONE column -- ``fill_column``, defaulting to the last --
    rather than being spread across all of them, because widening an identifier
    or a state word past its content buys nothing while a truncated description
    is exactly what the space is for.
    """

    fill_column: int | None = -1
    """Index of the column that absorbs surplus width; ``None`` disables it."""

    DEFAULT_CELL_PADDING: Final = int(CADRUMO_CSS_TOKENS["cadrumo-cell-padding"])
    """The product's one table density, so no call site names a number."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Apply the shared density unless a caller states its own."""
        kwargs.setdefault("cell_padding", self.DEFAULT_CELL_PADDING)
        super().__init__(*args, **kwargs)

    def watch_virtual_size(self, size: Size) -> None:
        """Keep the layout box equal to the current rows and header."""
        self.styles.height = max(1, size.height)

    def on_resize(self) -> None:
        """Give the surplus width to the fill column."""
        self._absorb_surplus_width()

    def absorb_surplus_width(self) -> None:
        """Re-apply the width policy after an owner rebuilds the columns.

        A screen that rebuilds its column set (responsive tables do) replaces
        the columns this widget already corrected, and the resize that would
        correct them again has been and gone. Such an owner calls this itself.
        """
        self._absorb_surplus_width()

    def _absorb_surplus_width(self) -> None:
        """Apply the deterministic width policy and refresh only after growth."""
        if not self.columns:
            return
        available = self.container_size.width - self.scrollbar_size_vertical
        if available <= 0:
            return

        columns = list(self.columns.items())
        natural = {key: self._natural_width(key, column) for key, column in columns}
        fill_key = _resolve_fill_column_key([key for key, _column in columns], self.fill_column)
        allocated = _allocate_column_widths(
            available,
            [(key, column.width, len(str(column.label)), natural[key]) for key, column in columns],
            fill_key=fill_key,
            cell_padding=self.cell_padding,
        )

        widened = False
        for key, column in columns:
            if column.width < allocated[key]:
                column.width = allocated[key]
                widened = True

        if widened:
            self.refresh()

    def _natural_width(self, key: ColumnKey, column: Column) -> int:
        """The width at which this column stops hiding anything."""
        widest = len(str(column.label))
        for index in range(self.row_count):
            row = self.get_row_at(index)
            for position, cell_key in enumerate(self.columns):
                if cell_key is key and position < len(row):
                    for line in str(row[position]).splitlines():
                        widest = max(widest, len(line))
        return widest


_NOTICE_GLYPH: Final[dict[str, str]] = {
    "info": "ⓘ",
    "warning": "⚠",
}


class NoticeBand(Vertical, can_focus=False):
    """Render already-resolved notices without adding interaction state."""

    def __init__(self, notices: Sequence[NoticePresentation], *, id: str | None = None) -> None:
        """Store the immutable notice projection for rendering."""
        super().__init__(id=id)
        self._notices = tuple(notices)

    @override
    def compose(self) -> ComposeResult:
        for index, notice in enumerate(self._notices):
            glyph = _NOTICE_GLYPH.get(notice.severity, "•")
            yield Static(
                f"{glyph} {notice.message}",
                classes=f"cadrumo-notice cadrumo-notice-{notice.severity}",
                id=f"notice-{index}",
                markup=False,
            )
            action_target = notice.action_target
            if action_target is not None:
                yield Static(
                    action_target,
                    classes="cadrumo-notice-action",
                    id=f"notice-{index}-action",
                    markup=False,
                )


class DisclosureGroup(Collapsible):
    """A titled, collapsible task section -- the shared `Show optional` primitive.

    A thin, named extension of Textual's own `Collapsible` rather than a
    parallel reimplementation: every Cadrumo surface that needs a collapsed
    optional-detail or completed-group section (the `Required` stage's task
    sections, `Show optional`, `Show not applicable`) composes this one
    widget instead of each host reaching for `Collapsible` under its own
    title and defaults.
    """

    DEFAULT_CSS = tokenised(
        """
        DisclosureGroup {
            /* The SAME section gap a panel and a heading take. A disclosure
               group is the third way this product marks a logical group, and
               it was the only one inheriting Textual's default spacing: two
               groups a single row apart read as one smeared list however
               correctly each is titled. Grouping mechanisms may differ in
               affordance -- a panel is static, this collapses -- but the
               distance that says "new group" has to be one distance. */
            margin-bottom: $cadrumo-section;
        }
        """
    )

    def __init__(self, *children: Widget, title: str, collapsed: bool = True, id: str | None = None) -> None:
        """Store the group's already-localized title and initial disclosure state."""
        super().__init__(*children, title=title, collapsed=collapsed, id=id)


class RequirementStatus(StrEnum):
    """The non-colour-safe requirement states a badge can render.

    Named for the reader, not the palette: two operators comparing a
    screenshot in greyscale and one in colour must reach the same
    conclusion, so every state carries its own glyph and label rather than
    only a colour class.
    """

    REQUIRED_MISSING = "required_missing"
    REQUIRED_PRESENT = "required_present"
    NEEDS_APPLICABILITY = "needs_applicability"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


_REQUIREMENT_GLYPH: Final[dict[RequirementStatus, str]] = {
    RequirementStatus.REQUIRED_MISSING: "✖",
    RequirementStatus.REQUIRED_PRESENT: "✓",
    RequirementStatus.NEEDS_APPLICABILITY: "?",
    RequirementStatus.OPTIONAL: "○",
    RequirementStatus.NOT_APPLICABLE: "—",
}


class RequirementBadge(Static, can_focus=False):
    """One field's requirement state, rendered by glyph and label together.

    Never colour alone: `_REQUIREMENT_GLYPH` gives every
    :class:`RequirementStatus` its own distinguishing mark, so a non-colour
    terminal or a colour-blind operator reads the same state a sighted
    colour-terminal operator does.
    """

    def __init__(self, label: str, status: RequirementStatus, *, id: str | None = None) -> None:
        """Store the already-localized field label and its settled status."""
        glyph = _REQUIREMENT_GLYPH[status]
        super().__init__(
            f"{glyph} {label}",
            classes=f"cadrumo-requirement cadrumo-requirement-{status.value}",
            id=id,
            markup=False,
        )
        self._status = status

    @property
    def status(self) -> RequirementStatus:
        """Return the settled requirement status this badge renders."""
        return self._status


@dataclass(frozen=True, slots=True)
class CredentialRequirement:
    """One resolved credential-requirement fact, present or absent as a unit.

    A label without a status, or a status without a label, is not a weaker
    fact -- it is not a fact at all, and the card cannot render half of one.
    Carrying the pair in one record makes that state unexpressible instead
    of relying on callers to honour it: the previous shape was two
    independent optional fields whose dependency lived only in prose, so a
    half-populated descriptor silently rendered NO badge and raised nothing,
    dropping a resolved requirement on an operator-facing surface with no
    signal at all.
    """

    label: str
    status: RequirementStatus


@dataclass(frozen=True, slots=True)
class SourceActionDescriptor:
    """One `Get data` source: what it is, and the action that starts it.

    ``credential_requirement`` is an optional pre-resolved requirement fact;
    this widget classifies nothing itself. When present, the card renders it
    through the shared :class:`RequirementBadge`, the same primitive
    `Required` uses, rather than inventing a second requirement
    presentation for sources.
    """

    title: str
    description: str
    action_label: str
    credential_requirement: CredentialRequirement | None = None


class SourceActionCard(Vertical):
    """A focusable card for one disclosed data source and its start action.

    Renders only; starting the described operation is the host screen's
    concern; the card is not what dispatches. Composes a real `Button` so
    the card is reachable and actionable by keyboard alone, per this
    Wave's focus-order proof.
    """

    DEFAULT_CSS = """
    SourceActionCard {
        height: auto;
    }
    """
    """`Vertical`'s own default is `height: 1fr` (an expanding container),
    which is fine standing alone but stretches a card to fill whatever
    space several 1fr siblings divide -- overriding to `auto` sizes the
    card to its own three children instead."""

    def __init__(self, descriptor: SourceActionDescriptor, *, id: str | None = None) -> None:
        """Store the already-localized source description."""
        super().__init__(id=id, classes="cadrumo-source-card")
        self._descriptor = descriptor

    @override
    def compose(self) -> ComposeResult:
        # The card title IS this group's heading, so it takes the shared rhythm
        # rather than a private one: the section gap above separates each source
        # from the previous card's action button, which they were running
        # straight into, and the stack gap below binds the title to its own
        # description.
        yield Static(
            self._descriptor.title,
            classes="cadrumo-source-card-title cadrumo-heading",
            markup=False,
        )
        yield Static(self._descriptor.description, classes="cadrumo-source-card-description", markup=False)
        requirement = self._descriptor.credential_requirement
        if requirement is not None:
            yield RequirementBadge(requirement.label, requirement.status, id="source-credential-requirement")
        yield Button(self._descriptor.action_label, id="btn-source-action", classes="cadrumo-source-card-action")


__all__ = [
    "ContentDataTable",
    "ContentScroll",
    "CredentialRequirement",
    "DisclosureGroup",
    "NoticeBand",
    "RequirementBadge",
    "RequirementStatus",
    "SourceActionCard",
    "SourceActionDescriptor",
]
