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


def _declared_floor_widths(columns: Sequence[tuple[ColumnKey, int, int, int]]) -> dict[ColumnKey, int]:
    """Return the widths the owner declared, used when there is none to allocate."""
    return {key: declared_width for key, declared_width, _header_width, _natural_width in columns}


def _header_floor_widths(columns: Sequence[tuple[ColumnKey, int, int, int]]) -> dict[ColumnKey, int]:
    """Raise each declared floor to its header floor."""
    return {key: max(declared_width, header_width) for key, declared_width, header_width, _ in columns}


def _fill_floor_width(columns: Sequence[tuple[ColumnKey, int, int, int]], fill_key: ColumnKey | None) -> int:
    """Return the fill column's floor, or zero when there is no target.

    Its declared width counts as well as its header: a fill column the owner
    sized is not free to be squeezed below that size, and a budget that
    pretends otherwise hands the other columns width the table does not have.
    """
    return next(
        (max(declared_width, header_width) for key, declared_width, header_width, _ in columns if key is fill_key),
        0,
    )


def _grown_non_fill_widths(
    widths: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    fill_key: ColumnKey | None,
) -> dict[ColumnKey, int]:
    """Non-fill columns raised to their natural widths, never below their floor."""
    return {
        key: max(widths[key], natural_width) if key is not fill_key else widths[key]
        for key, _declared, _header, natural_width in columns
    }


def _allocated_non_fill_width(
    widths: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    fill_key: ColumnKey,
    cell_padding: int,
) -> int:
    """Sum rendered non-fill widths, including both cell-padding sides."""
    return sum(widths[key] + cell_padding * 2 for key, _declared, _header, _natural in columns if key is not fill_key)


def _rendered_width(
    widths: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    cell_padding: int,
) -> int:
    """Sum every column's rendered width, including both cell-padding sides."""
    return sum(widths[key] for key, _declared, _header, _natural in columns) + cell_padding * 2 * len(columns)


def _header_floors_fit(
    headers: dict[ColumnKey, int],
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    available: int,
    *,
    fill_key: ColumnKey | None,
    cell_padding: int,
) -> bool:
    """Whether holding every header open still leaves the table inside its row.

    The fill column is measured at one cell rather than at its own header,
    because it is the column that absorbs whatever the others leave.
    """
    candidate = headers if fill_key is None else {**headers, fill_key: 1}
    return _rendered_width(candidate, columns, cell_padding) <= available


def _allocate_column_widths(
    available: int,
    columns: Sequence[tuple[ColumnKey, int, int, int]],
    *,
    fill_key: ColumnKey | None,
    cell_padding: int,
) -> dict[ColumnKey, int]:
    """Apply the table's deterministic header, natural, and surplus width policy.

    Each column tuple carries ``(key, declared_width, header_width,
    natural_width)``. The declared width is the one the table's owner asked
    for, never a width this policy assigned on an earlier pass: a result fed
    back in as a floor would pin the table to the widest terminal it has ever
    been shown at and overflow every narrower one.

    Header widths are floors only while the row can afford all of them at
    once; a terminal too narrow to name every column falls back to the
    declared widths and shortens the headers, which is what the operator can
    still read. Non-fill columns then grow to their natural widths only when
    doing so leaves the fill column its floor, and the remaining width belongs
    to the configured fill column alone.

    Each of those two steps is measured on the widths it would actually
    produce rather than on the inputs it is derived from. A column whose floor
    already exceeds its natural width grows by nothing, and a budget that
    counted the natural width instead would hand the difference away twice.
    """
    if available <= 0:
        return _declared_floor_widths(columns)

    headers = _header_floor_widths(columns)
    widths = (
        headers
        if _header_floors_fit(headers, columns, available, fill_key=fill_key, cell_padding=cell_padding)
        else _declared_floor_widths(columns)
    )
    fill_floor = _fill_floor_width(columns, fill_key)
    grown = _grown_non_fill_widths(widths, columns, fill_key)
    if fill_key is None or _rendered_width({**grown, fill_key: fill_floor}, columns, cell_padding) <= available:
        widths = grown

    if fill_key is not None:
        # Exactly the width the other columns left, even when that is less
        # than the fill column asked for. Taking the larger of the two instead
        # keeps the table wider than the row it is rendered into, and an
        # overflowing table scrolls its right-hand columns out of sight
        # altogether rather than shortening one cell.
        surplus = available - _allocated_non_fill_width(widths, columns, fill_key, cell_padding) - cell_padding * 2
        widths[fill_key] = max(surplus, 1)
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
        self._declared_widths: dict[ColumnKey, int] = {}

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

    def _declared_width(self, key: ColumnKey, column: Column) -> int:
        """The width the owner asked for, remembered before this policy writes one.

        An auto-sized column declares nothing, so its floor is zero and only
        its header holds it open. Recorded on first sight because every later
        pass reads a width this policy itself assigned.
        """
        return self._declared_widths.setdefault(key, 0 if column.auto_width else column.width)

    def _absorb_surplus_width(self) -> None:
        """Apply the deterministic width policy and refresh only after a change."""
        if not self.columns:
            return
        available = self.container_size.width - self.scrollbar_size_vertical
        if available <= 0:
            return

        columns = list(self.columns.items())
        # A rebuilt column set retires its keys; the floors it declared go with it.
        self._declared_widths = {key: width for key, width in self._declared_widths.items() if key in self.columns}
        natural = {key: self._natural_width(key, column) for key, column in columns}
        fill_key = _resolve_fill_column_key([key for key, _column in columns], self.fill_column)
        allocated = _allocate_column_widths(
            available,
            [(key, self._declared_width(key, column), len(str(column.label)), natural[key]) for key, column in columns],
            fill_key=fill_key,
            cell_padding=self.cell_padding,
        )

        changed = False
        for key, column in columns:
            # Textual renders an auto-width column from its measured content and
            # ignores `width` entirely, so assigning the allocation without
            # clearing `auto_width` leaves this whole policy inert: a long cell
            # still sets the column's render width and pushes the table past the
            # row it was given. Taking the width means taking it away from the
            # measurement.
            if column.width != allocated[key] or column.auto_width:
                column.width = allocated[key]
                column.auto_width = False
                changed = True

        if changed:
            # The same signal Textual's own column mutators raise: the table
            # re-measures its virtual size on the next idle, so the scroll
            # extent describes the widths just assigned.
            self._require_update_dimensions = True
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
    """`Vertical`'s own default height expands to fill a container's share,
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
