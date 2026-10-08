"""Help-band lifecycle and rendering for the Modelo workbench."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from rich.cells import cell_len
from textual.widgets import Static

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormField,
)
from .....application.overview.calendar import holiday_coverage_statement
from .....core.i18n.render import tr
from .....core.logging import get_logger
from ...components.cell_text import wrap_words
from .casilla_list import CasillaList
from .casilla_list_models import CasillaListEntry, CasillaListNote
from .grid import CasillaListRecords
from .header import (
    deadline_help,
)
from .issue_scale import blocks_marked
from .legend import legend_panel, more_text, on_screen_text
from .screen_constants import (
    _CLOSE_LOCALE_KEY,
    _GUTTERS,
    _NO_BREAK_SPACE,
)
from .screen_widgets import SymbolsPanel

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchHelpMixin:
    """Implement help-band lifecycle and rendering for the modelo workbench."""

    def on_casilla_list_highlighted(self: ModeloWorkbenchScreen, message: CasillaList.Highlighted) -> None:
        """Explain the casilla now under the cursor, then fetch its full help."""
        self._describe_keys()
        self._render_help(message.entry)
        self._render_breadcrumb()
        entry = message.entry
        if entry is not None:
            self._ask_for_card(entry)

    def _ask_for_card(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> None:
        """Fetch a box's full help off the event loop, unless it is already held."""
        if not isinstance(entry.field.address, ModeloFormCasillaAddressV1):
            return
        casilla_id = entry.field.address.casilla_id
        if (str(casilla_id), self._language) not in self._cards:
            self.run_worker(partial(self._fetch_card, entry), group="workbench-help", exclusive=True)

    def _held_card(self: ModeloWorkbenchScreen, field: ModeloFormField) -> ModeloCasillaHelpCardV1 | None:
        address = field.address
        if not isinstance(address, ModeloFormCasillaAddressV1):
            return None
        return self._cards.get((str(address.casilla_id), self._language))

    async def _card_for(self: ModeloWorkbenchScreen, field: ModeloFormField) -> ModeloCasillaHelpCardV1 | None:
        """A box's full help, read off the event loop once and then held; ``None`` for a binding input or a failure."""
        address = field.address
        if not isinstance(address, ModeloFormCasillaAddressV1):
            return None
        held = self._held_card(field)
        if held is not None:
            return held
        generation = self._help_generation
        language = self._language
        try:
            card = await asyncio.to_thread(self._reader.help_card, address.casilla_id, language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench help could not be assembled: %s", type(failure).__qualname__, exc_info=True
            )
            return None
        if generation != self._help_generation or language != self._language:
            return None
        self._cards[(str(address.casilla_id), language)] = card
        return card

    async def _fetch_card(self: ModeloWorkbenchScreen, entry: CasillaListEntry) -> None:
        if await self._card_for(entry.field) is None:
            return
        if self._explained is not None and self._explained.key == entry.key:
            self._render_help(self._explained)

    def _render_help(self: ModeloWorkbenchScreen, entry: CasillaListEntry | None) -> None:
        self._explained = entry
        band = self.query_one("#wb-help", Static)
        expanded = band.has_class("-expanded")
        lines = self._help_lines(entry, expanded)
        form = self.form
        if expanded and form is not None:
            shifted = deadline_help(form, self._language, recorded=self.recorded)
            if shifted is not None:
                lines.append(shifted)
            if not self.recorded and form.deadline is not None:
                lines.append(holiday_coverage_statement(form.deadline.holiday_coverage, None))
            lines.append(tr("tui.modelo.workbench.help.keys", keys=self._all_keys_text()))
        band.update(blocks_marked("\n".join(self._band_lines(band, lines))))

    def _help_lines(self: ModeloWorkbenchScreen, entry: CasillaListEntry | None, expanded: bool) -> list[str]:
        lines: list[str] = []
        if expanded:
            lines.extend((on_screen_text(self.box_marks, self.other_marks), more_text()))
        if entry is None:
            lines.append(self._empty_help_text())
        else:
            lines.extend(self._box_help(entry))
        return lines

    def _empty_help_text(self: ModeloWorkbenchScreen) -> str:
        items = self.query_one(CasillaList).items
        if any(isinstance(item, CasillaListRecords) for item in items):
            return tr("tui.modelo.workbench.grid.records_read_only")
        if any(isinstance(item, CasillaListNote) and item.column_casilla_ids for item in items):
            return tr("tui.modelo.workbench.grid.records_unknown")
        return tr("tui.modelo.workbench.help.empty")

    def _band_lines(self: ModeloWorkbenchScreen, band: Static, lines: list[str]) -> list[str]:
        """The band's lines, a line holding a no-break space broken here so it never breaks there.

        The terminal would break a line at any space, splitting "art. 71"; a
        line that holds a no-break space and does not fit is broken only at
        the other spaces. Every other line is left to wrap as it would.
        """
        width = band.content_region.width or max(self._width() - _GUTTERS, 1)
        shown: list[str] = []
        for line in lines:
            if _NO_BREAK_SPACE in line and cell_len(line) > width:
                shown.extend(wrap_words(line, width))
            else:
                shown.append(line)
        return shown

    def _rewrap_help(self: ModeloWorkbenchScreen) -> None:
        """Lay the help band out again for the width the terminal now has."""
        if self._pages and not self._legend_level:
            self._render_help(self.query_one(CasillaList).highlighted)

    def action_toggle_help(self: ModeloWorkbenchScreen) -> None:
        """Name the symbols on screen in a larger band, then open every symbol and key, then close it all."""
        self._legend_level = (self._legend_level + 1) % 3
        self._show_legend_level()

    def _show_legend_level(self: ModeloWorkbenchScreen) -> None:
        band = self.query_one("#wb-help", Static)
        band.set_class(self._legend_level == 1, "-expanded")
        panel_open = self._legend_level == 2
        if panel_open:
            text = legend_panel(
                self.box_marks,
                others=self.other_marks,
                keys=self._all_keys_text(),
                close=self._key_label("escape", _CLOSE_LOCALE_KEY),
            )
            self.query_one("#wb-legend-text", Static).update(text)
        self.set_class(panel_open, "-legend")
        self._describe_keys()
        if panel_open:
            self.query_one(SymbolsPanel).focus()
        else:
            self._render_help(self.query_one(CasillaList).highlighted)
            self.query_one(CasillaList).focus()
