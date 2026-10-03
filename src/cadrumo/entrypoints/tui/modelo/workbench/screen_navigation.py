"""Navigation and contextual help for the Modelo workbench."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.actions import SkipAction
from textual.widgets import OptionList

from .....core.i18n.render import tr
from .casilla_list import CasillaList, CasillaListEntry, Density
from .navigator import checked_boxes, page_counts
from .page_items import page_items
from .screen_constants import (
    _FILTER_ORDER,
)
from .search import SearchMode, WorkbenchSearchPanel, search_entries
from .sorting import SortOrder, next_order
from .vocabulary import aeat_imported_on

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchNavigationMixin:
    """Own the navigation behavior for the modelo workbench."""

    def _show_page(self: ModeloWorkbenchScreen, index: int) -> None:
        if not self._pages:
            return
        self._page_index = max(0, min(len(self._pages) - 1, index))
        self._render_navigator()
        self._render_page()

    def action_page(self: ModeloWorkbenchScreen, delta: int) -> None:
        """Show the previous or next page, in form order."""
        self._sort = SortOrder.FORM
        self._show_page(self._page_index + delta)

    def action_cycle_filter(self: ModeloWorkbenchScreen) -> None:
        """Show all fields, then only what needs attention, then only the filer's own values."""
        position = _FILTER_ORDER.index(self._filter)
        self._filter = _FILTER_ORDER[(position + 1) % len(_FILTER_ORDER)]
        self._render_page()

    def action_cycle_sort(self: ModeloWorkbenchScreen) -> None:
        """Order the boxes as the form prints them, by box number, by amount, or what needs attention first."""
        self._sort = next_order(self._sort)
        self._render_page()

    def action_fold(self: ModeloWorkbenchScreen, direction: int) -> None:
        """Close (0), open (1) or flip (-1) the navigator page under its cursor, or the current page."""
        navigator = self.query_one("#wb-sections", OptionList)
        index = self._fold_page_index(navigator)
        if not self._pages or self.form is None:
            return
        page = self._pages[index]
        counts = page_counts(page, checked_boxes(self.form))
        self._navigator.toggle(
            page,
            current=index == self._page_index,
            counts=counts,
            open_=None if direction < 0 else bool(direction),
            applies=self._applies(index),
        )
        self._render_navigator()
        if self.focused is navigator:
            self._restore_fold_highlight(navigator, index)

    def _fold_page_index(self: ModeloWorkbenchScreen, navigator: OptionList) -> int:
        if self.focused is navigator and navigator.highlighted is not None:
            option_id = navigator.get_option_at_index(navigator.highlighted).id or ""
            page_text = option_id.partition(":")[2].partition(":")[0]
            if page_text.isdigit():
                return int(page_text)
        elif self.focused is not self.query_one(CasillaList):
            raise SkipAction
        return self._page_index

    @staticmethod
    def _restore_fold_highlight(navigator: OptionList, index: int) -> None:
        ids = [navigator.get_option_at_index(position).id for position in range(navigator.option_count)]
        target = f"page:{index}"
        if target in ids:
            navigator.highlighted = ids.index(target)

    def action_next_attention(self: ModeloWorkbenchScreen, direction: int) -> None:
        """Move to the next thing to do, carrying on to the next page that has one."""
        if self.focused is not self.query_one(CasillaList):
            raise SkipAction
        self._advance_attention(direction)

    def _advance_attention(self: ModeloWorkbenchScreen, direction: int) -> None:
        casilla_list = self.query_one(CasillaList)
        before = casilla_list.highlighted
        casilla_list.action_attention(direction)
        after = casilla_list.highlighted
        if after is not None and (before is None or after.key != before.key):
            return
        if self._sort is SortOrder.FORM and self._pages and self._advance_to_page_attention(casilla_list, direction):
            return
        if direction > 0:
            self._notice(tr("tui.modelo.workbench.browse.last_to_do", action=self._next_words))

    def _advance_to_page_attention(self: ModeloWorkbenchScreen, casilla_list: CasillaList, direction: int) -> bool:
        for index in self._attention_page_indices(direction):
            if not self._applies(index):
                continue
            targets = self._page_attention_targets(index)
            if not targets:
                continue
            self._show_page(index)
            casilla_list.focus_address(targets[0 if direction > 0 else -1].key)
            casilla_list.focus()
            return True
        return False

    def _attention_page_indices(self: ModeloWorkbenchScreen, direction: int) -> range:
        if direction > 0:
            return range(self._page_index + 1, len(self._pages))
        return range(self._page_index - 1, -1, -1)

    def _page_attention_targets(self: ModeloWorkbenchScreen, index: int) -> list[CasillaListEntry]:
        return [
            item
            for item in page_items(self._pages[index], staged=self._session.display(), mode=self._filter)
            if isinstance(item, CasillaListEntry) and item.needs_filer
        ]

    def action_search(self: ModeloWorkbenchScreen) -> None:
        """Search every page by box number or words."""
        self._open_search(SearchMode.SEARCH)

    def action_go_to(self: ModeloWorkbenchScreen) -> None:
        """Go straight to a box by its number."""
        self._open_search(SearchMode.GO_TO)

    def _open_search(self: ModeloWorkbenchScreen, mode: SearchMode) -> None:
        if not self._pages:
            return
        entries = search_entries(
            self._pages,
            staged=self._session.display(),
            language=self._language,
            recorded=self.recorded,
            aeat_imported=aeat_imported_on(self.form),
        )
        self.add_class("-searching")
        self.query_one(WorkbenchSearchPanel).open(mode, entries)

    def _close_search(self: ModeloWorkbenchScreen) -> None:
        self.remove_class("-searching")
        casilla_list = self.query_one(CasillaList)
        self._render_help(casilla_list.highlighted)
        casilla_list.focus()

    def on_workbench_search_panel_highlighted(
        self: ModeloWorkbenchScreen, message: WorkbenchSearchPanel.Highlighted
    ) -> None:
        """Explain in the help band the hit the filer is on, fetching its full help once."""
        staged = self._session.display()
        entry = next(
            (
                item
                for page in self._pages
                for item in page_items(page, staged=staged)
                if isinstance(item, CasillaListEntry) and item.key == message.key
            ),
            None,
        )
        if entry is None:
            return
        self._render_help(entry)
        self._ask_for_card(entry)

    def on_workbench_search_panel_chosen(self: ModeloWorkbenchScreen, message: WorkbenchSearchPanel.Chosen) -> None:
        """Go to the box the filer found."""
        self._close_search()
        self._go_to(message.key)

    def action_toggle_density(self: ModeloWorkbenchScreen) -> None:
        """Show fields on one line or two; the filer's choice then holds whatever the terminal's height."""
        casilla_list = self.query_one(CasillaList)
        density: Density = "compact" if casilla_list.density == "comfortable" else "comfortable"
        self._density_chosen = density
        casilla_list.set_density(density)
