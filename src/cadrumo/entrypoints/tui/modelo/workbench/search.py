"""Find a box anywhere in the declaration: by its number, by words, or straight to a number.

A filer copying from the AEAT form or a letter knows a box by its number; one
looking for a concept knows its words. Search reads every page, matches a box
number exactly first and then by its start, and matches words against the
label and the description without regard to case or accents, so "retencion"
finds "Retenciones". A query of digits alone is a box number and nothing else:
1, 01 and 0001 name the same box, then come the boxes whose number starts with
what was typed, and a number is never found inside another. The first hit is
selected as soon as there is one, and the help band explains the hit
selected. Each hit reads as the list would show it: the box, the label, the
page, the value and where it comes from. Go to box takes a number
and lands on it, or says the form has no such box.

The panel opens under the header in place of the list, so the result and the
deadline stay in view while the filer searches.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, override

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.theme import tokenised
from .casilla_list import AddressKey, CasillaListEntry, description_text, value_text
from .navigator import readable_text
from .page_items import StagedDisplay, WorkbenchPage, page_items
from .vocabulary import origin_text

_BOX_QUERY: Final[re.Pattern[str]] = re.compile(r"\d{1,4}[A-Za-z]?")
_DIGITS: Final[re.Pattern[str]] = re.compile(r"\d+")
_SEPARATOR: Final[str] = " · "
_EXACT: Final[int] = 0
_PREFIX: Final[int] = 1
_WORDS: Final[int] = 2


class SearchMode(StrEnum):
    """What the panel was opened for."""

    SEARCH = "search"
    GO_TO = "go_to"


def folded(text: str) -> str:
    """Text as search compares it: lower case, without accents."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _box_number(box: str) -> str:
    return box.lstrip("0").casefold() or "0"


@dataclass(frozen=True, slots=True)
class SearchEntry:
    """One box as search reads and shows it."""

    key: AddressKey
    box: str | None
    label: str
    description: str
    page: str
    value: str
    origin: str

    def text(self) -> str:
        """The hit as the results show it: box and label, page, value and where it comes from."""
        named = " ".join(part for part in (f"[{self.box}]" if self.box else "", self.label) if part)
        return _SEPARATOR.join(part for part in (named, self.page, self.value, self.origin) if part)


def search_entries(
    pages: tuple[WorkbenchPage, ...], *, staged: Mapping[AddressKey, StagedDisplay], language: OutputLanguage
) -> tuple[SearchEntry, ...]:
    """Every box of every page, in form order, with the value it shows now, staged changes included."""
    entries: list[SearchEntry] = []
    for page in pages:
        for item in page_items(page, staged=staged):
            if not isinstance(item, CasillaListEntry):
                continue
            field = item.field
            description = description_text(field) or ""
            entries.append(
                SearchEntry(
                    key=item.key,
                    box=field.box,
                    label=readable_text(field.label) or description,
                    description=description,
                    page=page.heading.text,
                    value=value_text(item, language),
                    origin=origin_text(field),
                )
            )
    return tuple(entries)


def search(entries: tuple[SearchEntry, ...], query: str) -> tuple[SearchEntry, ...]:
    """The boxes a query finds: the box with that number, then boxes whose number starts so, then by words."""
    wanted = query.strip()
    if not wanted:
        return ()
    tokens = folded(wanted).split()
    number = _box_number(wanted) if _BOX_QUERY.fullmatch(wanted) else None
    digits_only = _DIGITS.fullmatch(wanted) is not None
    ranked: list[tuple[int, int, SearchEntry]] = []
    for position, entry in enumerate(entries):
        rank = None
        if number is not None and entry.box is not None:
            box = _box_number(entry.box)
            if box == number:
                rank = _EXACT
            elif _starts_with(entry.box, wanted):
                rank = _PREFIX
        if rank is None and not digits_only:
            haystack = folded(f"{entry.box or ''} {entry.label} {entry.description}")
            if all(token in haystack for token in tokens):
                rank = _WORDS
        if rank is not None:
            ranked.append((rank, position, entry))
    ranked.sort(key=lambda hit: (hit[0], hit[1]))
    return tuple(entry for _, _, entry in ranked)


def _starts_with(box: str, typed: str) -> bool:
    """Whether a box's number starts with what was typed: as the box is written, or without its leading zeros.

    Typed leading zeros are kept, so "01" finds "0100" but never "10".
    """
    written = box.casefold()
    typed = typed.casefold()
    if written.startswith(typed):
        return True
    return not typed.startswith("0") and _box_number(box).startswith(typed)


def find_box(entries: tuple[SearchEntry, ...], number: str) -> SearchEntry | None:
    """The box with exactly this number, leading zeros aside, or ``None`` when the form has none."""
    wanted = number.strip()
    if not _BOX_QUERY.fullmatch(wanted):
        return None
    target = _box_number(wanted)
    return next((entry for entry in entries if entry.box is not None and _box_number(entry.box) == target), None)


class WorkbenchSearchPanel(Vertical):
    """A query line over its hits, docked in place of the casilla list."""

    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        WorkbenchSearchPanel {
            height: 1fr;
            padding: $cadrumo-space-0 $cadrumo-space-1;
        }
        WorkbenchSearchPanel #wb-search-prompt {
            color: $secondary;
        }
        WorkbenchSearchPanel #wb-search-status {
            color: $warning;
            height: auto;
        }
        WorkbenchSearchPanel #wb-search-results {
            height: 1fr;
            border: none;
            background: $background;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("down", "results", "", show=False)]

    class Highlighted(Message):
        """The hit the filer is on changed, so the help band can explain it."""

        def __init__(self, key: AddressKey) -> None:
            """Carry the highlighted box's address."""
            super().__init__()
            self.key = key

    class Chosen(Message):
        """The filer chose a box to go to."""

        def __init__(self, key: AddressKey) -> None:
            """Carry the chosen box's address."""
            super().__init__()
            self.key = key

    def __init__(self, *, id: str | None = None) -> None:
        """Start empty; :meth:`open` gives the panel its boxes."""
        super().__init__(id=id)
        self._mode = SearchMode.SEARCH
        self._entries: tuple[SearchEntry, ...] = ()
        self._hits: tuple[SearchEntry, ...] = ()

    @property
    def mode(self) -> SearchMode:
        """What the panel is open for."""
        return self._mode

    @property
    def hits(self) -> tuple[SearchEntry, ...]:
        """The boxes the current query finds."""
        return self._hits

    @override
    def compose(self) -> ComposeResult:
        """Lay out the prompt, the query line, the status and the hits."""
        yield Static(id="wb-search-prompt", markup=False)
        yield Input(id="wb-search-input")
        yield Static(id="wb-search-status", markup=False)
        yield OptionList(id="wb-search-results")

    def open(self, mode: SearchMode, entries: tuple[SearchEntry, ...]) -> None:
        """Show the panel empty for ``mode`` over ``entries`` and put the cursor in the query line."""
        self._mode = mode
        self._entries = entries
        self._hits = ()
        prompt = (
            "tui.modelo.workbench.search.prompt" if mode is SearchMode.SEARCH else "tui.modelo.workbench.go_to.prompt"
        )
        self.query_one("#wb-search-prompt", Static).update(tr(prompt))
        self.query_one("#wb-search-status", Static).update("")
        self.query_one("#wb-search-results", OptionList).clear_options()
        query_line = self.query_one("#wb-search-input", Input)
        query_line.value = ""
        query_line.focus()

    def _show_hits(self, query: str) -> None:
        results = self.query_one("#wb-search-results", OptionList)
        results.clear_options()
        status = self.query_one("#wb-search-status", Static)
        if self._mode is not SearchMode.SEARCH:
            return
        self._hits = search(self._entries, query)
        for index, hit in enumerate(self._hits):
            results.add_option(Option(Text(hit.text()), id=str(index)))
        if self._hits:
            results.highlighted = 0
        if not query.strip():
            status.update("")
        elif self._hits:
            status.update(tr("tui.modelo.workbench.search.count", count=len(self._hits)))
        else:
            status.update(tr("tui.modelo.workbench.search.empty", query=query.strip()))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Search again as the filer types."""
        event.stop()
        self._show_hits(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Go to the first hit, or to the box with the typed number."""
        event.stop()
        if self._mode is SearchMode.GO_TO:
            found = find_box(self._entries, event.value)
            if found is None:
                self.query_one("#wb-search-status", Static).update(
                    tr("tui.modelo.workbench.go_to.missing", box=event.value.strip())
                )
                return
            self.post_message(self.Chosen(found.key))
            return
        if self._hits:
            self.post_message(self.Chosen(self._hits[0].key))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Tell the workbench which hit is selected, so the help band explains it."""
        event.stop()
        index = int(event.option.id or "0")
        if 0 <= index < len(self._hits):
            self.post_message(self.Highlighted(self._hits[index].key))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Go to the hit the filer picked."""
        event.stop()
        index = int(event.option.id or "0")
        if 0 <= index < len(self._hits):
            self.post_message(self.Chosen(self._hits[index].key))

    def action_results(self) -> None:
        """Move from the query line down into the hits."""
        results = self.query_one("#wb-search-results", OptionList)
        if results.option_count:
            results.focus()
            if results.highlighted is None:
                results.highlighted = 0


__all__ = [
    "SearchEntry",
    "SearchMode",
    "WorkbenchSearchPanel",
    "find_box",
    "folded",
    "search",
    "search_entries",
]
