"""Header, listing, and progress presentation for the Modelo workbench."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.cells import cell_len
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.work_form_models import (
    ModeloFormLayoutProvenance,
    ModeloFormResultDirection,
    ModeloWorkForm,
)
from .....core.i18n.render import tr
from .casilla_list import CasillaList, CasillaListEntry, CasillaListNote
from .grid import CasillaListRecords
from .header import (
    DeadlineView,
    FileView,
    ResultLine,
    ResultView,
    attention_chips,
    deadline_view,
    file_view,
    fit_identity,
    fit_result_line,
    result_view,
)
from .navigator import NavigatorRow, breadcrumb, checked_boxes, navigator_rows, section_of
from .page_items import WorkbenchFilter, page_items, page_of
from .progress import NextAction, fit_next_line, next_action_text, stepper_marks, stepper_text
from .screen_constants import (
    _CRUMB_SEPARATOR,
    _DEADLINE_TONE_CLASSES,
    _EMPTY_LOCALE_KEY,
    _EMPTY_NEXT_LOCALE_KEY,
    _FINDINGS_KEY,
    _GUTTERS,
    _NAV_MIN_LABEL,
    _NEXT_GAP,
    _NEXT_KEYS,
)
from .sorting import SORT_LOCALE_KEYS, SortOrder, sorted_items

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchPresentationMixin:
    """Implement header, listing, and progress presentation for the modelo workbench."""

    def _render_all(self: ModeloWorkbenchScreen) -> None:
        self._render_header()
        self._render_progress()
        self._render_navigator()
        self._render_page()

    def _render_header(self: ModeloWorkbenchScreen) -> None:
        form = self.form
        if form is None:
            return
        width = max(self._width() - _GUTTERS, 1)
        recorded = self.recorded
        deadline = deadline_view(form, self._language, recorded=recorded, width=width)
        identity = fit_identity(form, self._language, deadline, width)
        self.set_class(identity.stacked, "-identity-stacked")
        self.query_one("#wb-header", Static).update(identity.text)
        self._render_deadline(deadline)
        self._render_header_result(form, width, recorded)

    def _render_deadline(self: ModeloWorkbenchScreen, deadline: DeadlineView | None) -> None:
        deadline_widget = self.query_one("#wb-deadline", Static)
        deadline_widget.display = deadline is not None
        deadline_widget.update("" if deadline is None else deadline.text)
        for tone, css_class in _DEADLINE_TONE_CLASSES.items():
            deadline_widget.set_class(deadline is not None and deadline.tone is tone, css_class)

    def _render_header_result(self: ModeloWorkbenchScreen, form: ModeloWorkForm, width: int, recorded: bool) -> None:
        view = result_view(form, self._language, staged=len(self._session.changes), recorded=recorded)
        chips = attention_chips(form, recorded=recorded)
        file = file_view(form, self._language, recorded=recorded)
        file_text = None if file is None else file.text
        line = (
            ResultLine("", None, chips, file=file_text)
            if view is None
            else fit_result_line(view, chips, width, file=file_text)
        )
        self._render_result_text(form, line, recorded)
        self._render_result_marks(view, line, file)

    def _render_result_text(
        self: ModeloWorkbenchScreen, form: ModeloWorkForm, line: ResultLine, recorded: bool
    ) -> None:
        result = self.query_one("#wb-result", Static)
        result.update(line.result)
        result.display = bool(line.result)
        result.set_class(line.stale is not None, "-stale")
        # Colour only reinforces the words: a result to pay reads as a warning, as an error once the deadline passed.
        to_pay = form.result is not None and form.result.direction is ModeloFormResultDirection.TO_PAY and not recorded
        result.set_class(to_pay, "-to-pay")
        result.set_class(to_pay and form.deadline is not None and form.deadline.days_overdue is not None, "-overdue")

    def _render_result_marks(
        self: ModeloWorkbenchScreen, view: ResultView | None, line: ResultLine, file: FileView | None
    ) -> None:
        stale = self.query_one("#wb-stale", Static)
        stale.update(line.stale or "")
        stale.display = line.stale is not None
        file_widget = self.query_one("#wb-file", Static)
        file_widget.update(line.file or "")
        file_widget.display = line.file is not None
        # A file made from an earlier calculation must not be uploaded: it reads as a warning.
        file_widget.set_class(file is not None and file.out_of_date, "-out-of-date")
        chips_widget = self.query_one("#wb-chips", Static)
        chips_widget.update(line.chips_content())
        chips_widget.display = bool(line.chips)
        # A declaration with no result, no file and nothing to count gives the line back to the boxes.
        self.query_one("#wb-outcome").display = bool(line.result or line.stale or line.file or line.chips)
        # With no result beside them, or stacked below it, the first of the marks starts the line.
        self._position_result_marks(line, stale, file_widget, chips_widget)
        stale_marks = () if view is None or line.stale is None else view.marks
        self._drawn["header"] = (*stale_marks, *(chip.mark for chip in line.chips))

    def _position_result_marks(
        self: ModeloWorkbenchScreen, line: ResultLine, stale: Static, file_widget: Static, chips_widget: Static
    ) -> None:
        marks_lead = line.stacked or not line.result
        stale.set_class(marks_lead, "-leading")
        file_widget.set_class(marks_lead and line.stale is None, "-leading")
        chips_widget.set_class(marks_lead and line.stale is None and line.file is None, "-leading")
        self.set_class(line.stacked, "-outcome-stacked")

    def _render_progress(self: ModeloWorkbenchScreen) -> None:
        load = self._load
        if load is None:
            return
        progress = self._progress(load)
        stepper = stepper_text(progress)
        self.query_one("#wb-stepper", Static).update(stepper)
        self._drawn["stepper"] = stepper_marks(progress)
        key = _FINDINGS_KEY if progress.findings_lead else _NEXT_KEYS[progress.next_action]
        action = (
            tr("tui.modelo.workbench.apply_prerequisite.next")
            if self._active_apply_prerequisite() is not None
            else next_action_text(progress, self._language)
        )
        self._next_words = f"{action} [{key}]" if key else action
        width = max(self._width() - _GUTTERS, 1)
        line = fit_next_line(action, key, width)
        # Beside the stepper when it fits there, else on a line of its own: never wrapped.
        self.set_class(cell_len(line) > width - cell_len(stepper.plain) - _NEXT_GAP, "-next-below")
        next_widget = self.query_one("#wb-next", Static)
        next_widget.update(line)
        next_widget.set_class(progress.next_action is NextAction.CONFIRM, "-confirm")
        next_widget.set_class(progress.next_action is NextAction.RESOLVE, "-resolve")
        # The footer keeps the key the line now names.
        self._describe_keys()

    def _render_navigator(self: ModeloWorkbenchScreen) -> None:
        form = self.form
        if form is None or not self._pages:
            return
        if self.has_class("-narrow"):
            self._render_breadcrumb()
            return
        navigator = self.query_one("#wb-sections", OptionList)
        highlighted = navigator.highlighted
        kept = None if highlighted is None else navigator.get_option_at_index(highlighted).id
        label_width = max(navigator.scrollable_content_region.width, _NAV_MIN_LABEL)
        rows = navigator_rows(
            self._pages,
            current=self._page_index,
            state=self._navigator,
            checked=checked_boxes(form),
            width=label_width,
            show_attention=not self.recorded,
            inapplicable=self._inapplicable,
            not_applying=self._not_applying_text(),
        )
        self._replace_navigator_rows(navigator, rows, kept)

    def _replace_navigator_rows(
        self: ModeloWorkbenchScreen, navigator: OptionList, rows: tuple[NavigatorRow, ...], kept: str | None
    ) -> None:
        navigator.clear_options()
        for row in rows:
            navigator.add_option(Option(row.prompt, id=row.option_id))
        self._drawn["navigator"] = tuple(mark for row in rows for mark in row.marks)
        ids = [row.option_id for row in rows]
        if kept is not None and kept in ids:
            navigator.highlighted = ids.index(kept)

    def _render_breadcrumb(self: ModeloWorkbenchScreen) -> None:
        form = self.form
        if form is None or not self._pages or not self.has_class("-narrow"):
            return
        entry = self.query_one(CasillaList).highlighted
        current = self._page_index
        if self._sort is not SortOrder.FORM and entry is not None:
            target_page = page_of(self._pages, entry.key)
            if target_page is not None:
                current = target_page
        page = self._pages[current]
        section = None if entry is None else section_of(page, entry.key)
        line, marks = breadcrumb(
            self._pages,
            current=current,
            section=section,
            checked=checked_boxes(form),
            show_attention=not self.recorded,
            not_applying=None if self._applies(current) else self._not_applying_text(),
        )
        # The page title line is hidden here, so the crumb names a filter or an order that is not the default.
        for note in self._listing_notes(name_every_filter=False):
            line.append(f"{_CRUMB_SEPARATOR}{note}")
        self.query_one("#wb-crumb", Static).update(line)
        self._drawn["navigator"] = marks

    def _listing_notes(self: ModeloWorkbenchScreen, *, name_every_filter: bool) -> list[str]:
        """What the list shows beyond its page: an order other than the form's, the filter, and why it is empty.

        Without ``name_every_filter`` the filter is named only when it hides
        something, as the narrow crumb names it.
        """
        notes: list[str] = []
        if self._sort is not SortOrder.FORM:
            notes.append(tr(SORT_LOCALE_KEYS[self._sort]))
        if name_every_filter or self._filter is not WorkbenchFilter.ALL:
            notes.append(tr(f"tui.modelo.workbench.filter.{self._filter.value}"))
        empty = self._empty_listing_note()
        if empty is not None:
            notes.append(empty)
        return notes

    def _empty_listing_note(self: ModeloWorkbenchScreen) -> str | None:
        """Explain an empty view; saved records and an unknown record source are content too."""
        if any(
            isinstance(item, CasillaListEntry | CasillaListRecords)
            or (isinstance(item, CasillaListNote) and bool(item.column_casilla_ids))
            for item in self.query_one(CasillaList).items
        ):
            return None
        if self._sort is SortOrder.FORM:
            staged = self._session.display()
            count = len(self._pages)
            for step in range(1, count):
                index = (self._page_index + step) % count
                items = page_items(self._pages[index], staged=staged, mode=self._filter)
                if any(isinstance(item, CasillaListEntry) for item in items):
                    return tr(_EMPTY_NEXT_LOCALE_KEY, page=self._pages[index].heading.text)
        return tr(_EMPTY_LOCALE_KEY)

    def _render_page(self: ModeloWorkbenchScreen) -> None:
        if not self._pages:
            return
        form = self.form
        casilla_list = self.query_one(CasillaList)
        staged = self._session.display()
        notes: list[str] = []
        if self._sort is SortOrder.FORM:
            page = self._pages[self._page_index]
            title = page.heading.text
            notes.append(tr("tui.modelo.workbench.page_position", current=self._page_index + 1, total=len(self._pages)))
            if not self._applies(self._page_index):
                notes.append(self._not_applying_text())
            casilla_list.set_items(page_items(page, staged=staged, mode=self._filter), language=self._language)
        else:
            title = tr("tui.modelo.workbench.sort.all_pages")
            items = sorted_items(self._pages, order=self._sort, staged=staged, mode=self._filter)
            casilla_list.set_items(items, language=self._language)
        notes.extend(self._listing_notes(name_every_filter=True))
        if form is not None and form.layout_provenance is not ModeloFormLayoutProvenance.REVIEWED:
            notes.append(tr(f"tui.modelo.workbench.layout.{form.layout_provenance.value}"))
        self.query_one("#wb-page", Static).update(f"{title}   " + " · ".join(notes))
        self._render_breadcrumb()
        if casilla_list.highlighted is None:
            self._render_help(None)
