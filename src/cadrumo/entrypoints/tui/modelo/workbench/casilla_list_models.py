"""Item and measurement types for the modelo workbench casilla list.

Mounting one widget per casilla costs seconds at the size of the largest
modelos, so a page is one widget that lays out each visible line on demand.
The cursor is held as a field's semantic address, never a position: rebuilding
the list after an edit, a refresh, a filter or a language switch keeps the same
casilla under the cursor when it is still there.

Each field reads, left to right: the cursor mark, an attention mark (a staged
change or a verification blocker), the official box number, the label, the
value right-aligned with its unit, the origin glyph, and where they fit the
origin in words and a detail column. Every column is measured from the lines
being shown: the box column is as wide as the widest box number, so a number is
never cut, and the label column no wider than the longest label nor than sixty
cells, so the value and its origin sit next to the words they belong to and a
wide terminal leaves the rest of the line empty. Headings carry the strongest
weight and descriptions the weakest. A label too long for its
column wraps onto further lines and is never cut; only the one optional line
under it, the start of the box's description, may be. Every mark comes from
:mod:`.vocabulary`, so the list never invents a state.

An official grid is drawn as the paper form draws it, its rows down the side
and its columns across, when the table fits the width; the cursor then moves
from cell to cell, and the row's left edge carries the most severe mark among
its cells. A grid too wide for the width is stacked instead, each row under a
heading that tells it apart from its neighbours. The records of a repeating
group are a read-only table with an index column.

The list decides nothing. It posts a message naming the address the filer
acted on -- edit, clear, revert, show the source -- and the screen owning the
edit session answers it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    address_key,
)
from .grid import (
    CasillaListRecords,
    GridRowPlace,
    TableGeometry,
)
from .vocabulary import (
    ASKS_FOR_A_VALUE,
    NEEDS_ATTENTION,
    ORIGIN_ROLES,
    Attention,
    ColourRole,
    WorkbenchMark,
    field_needs_filer,
    origin_glyph,
    origin_words,
)

type AddressKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class CasillaListHeading:
    """A section or row heading line; never under the cursor.

    A row heading of an official grid carries its place in the grid, so the
    list can draw the row as a line of the grid's table. A section heading
    carries the most severe thing its section still holds, and takes that
    level's colour: a blocker reads as an error, a missing or assumed value as
    a warning, and a section with nothing to do in the plain text colour.
    """

    text: str
    level: int = 0
    row: GridRowPlace | None = None
    mark: WorkbenchMark | None = None


@dataclass(frozen=True, slots=True)
class CasillaListNote:
    """An informational line, such as a value the official design fixes.

    A note standing in for a repeating group's records carries the group's
    column casillas, so a finding about one of them can be placed on it.
    """

    text: str
    indent: int = 0
    column_casilla_ids: tuple[str | None, ...] = ()


@dataclass(frozen=True, slots=True)
class CasillaListEntry:
    """One field line, with any change the filer has staged but not applied."""

    field: ModeloFormField
    indent: int = 0
    label: str | None = None
    staged_text: str | None = None
    previous_text: str | None = None
    #: A concrete staged SET must not inherit its saved original's absence qualifier.
    staged_concrete_value: bool = False
    #: The one rate box of an official row, which prints the rate the row's base is taxed at.
    rate_of_row: bool = False
    #: On a row's rate box, whether the row's base holds no amount; ``None`` where no base box is known.
    row_base_empty: bool | None = None
    #: The declaration is recorded as filed: its values are facts, and nothing on it asks for the filer.
    recorded: bool = False
    #: ``False`` on a page the read model states does not apply this period, which asks for no value.
    applies: bool = True
    #: In an official grid, the heading of the row the box sits in, and of its column.
    row_label: str | None = None
    column_label: str | None = None

    @property
    def key(self) -> AddressKey:
        """The field's semantic identity."""
        return address_key(self.field.address)

    @property
    def attention(self) -> Attention | None:
        """The mark that draws the eye: a staged change first, then a blocker."""
        if self.staged_text is not None:
            return Attention.STAGED
        if self.field.blockers and not self.recorded:
            return Attention.BLOCKED
        return None

    @property
    def needs_filer(self) -> bool:
        """Whether the filer can act on the field now: a staged change, or what the shared classing says.

        A box waiting on an import or a calculation is not one, and nothing on
        a recorded declaration is; ``n`` visits exactly these.
        """
        if self.staged_text is not None:
            return True
        return field_needs_filer(self.field, recorded=self.recorded, applies=self.applies)

    @property
    def origin_mark(self) -> str:
        """The origin glyph the row draws; a recorded declaration draws no to-do mark, only its words."""
        if self.staged_replaces_absence or (self.recorded and self.field.origin in ASKS_FOR_A_VALUE):
            return " "
        return origin_glyph(self.field)

    @property
    def origin_words(self) -> str:
        """The origin in words, as the row and the box panel say it; a recorded declaration asks nothing."""
        return "" if self.staged_replaces_absence else origin_words(self.field, recorded=self.recorded)

    @property
    def staged_replaces_absence(self) -> bool:
        """Whether a concrete staged value supersedes only the saved empty/missing qualifier."""
        return self.staged_concrete_value and self.field.origin in {
            ModeloFormOrigin.OPTIONAL_EMPTY,
            ModeloFormOrigin.NEEDS_INPUT,
        }

    @property
    def origin_role(self) -> ColourRole:
        """The colour of the origin; a recorded declaration's origins are all plain facts."""
        if self.recorded and self.field.origin in NEEDS_ATTENTION:
            return ColourRole.MUTED
        return ORIGIN_ROLES[self.field.origin]


type CasillaListItem = CasillaListHeading | CasillaListNote | CasillaListEntry | CasillaListRecords
type Density = Literal["comfortable", "compact"]


@dataclass(frozen=True, slots=True)
class _Measures:
    """The widest box number, label, value and origin words among the fields shown, in cells."""

    box: int = 1
    label: int = 0
    value: int = 1
    words: int = 0


@dataclass(frozen=True, slots=True)
class _Columns:
    """The cells each column gets at one width; ``label`` is an unindented field's."""

    box: int
    label: int
    value: int
    words: int
    detail: bool


@dataclass(frozen=True, slots=True)
class _TableRow:
    """One grid row drawn as a line of its table: where its cells are and what its label reads."""

    geometry: TableGeometry
    #: The item index of the field in each column, or ``None`` for an empty slot.
    cells: tuple[int | None, ...]
    literals: tuple[str | None, ...]
    labels: tuple[str, ...]
    #: Whether the column headings are drawn above this row: the first row of its grid on screen.
    header: bool
    level: WorkbenchMark | None

    @property
    def header_height(self) -> int:
        """The lines the column headings take above this row."""
        return self.geometry.header_height if self.header else 0

    def focusable(self) -> tuple[int, ...]:
        """The columns whose cell holds a field the cursor can rest on."""
        return tuple(column for column, index in enumerate(self.cells) if index is not None)
