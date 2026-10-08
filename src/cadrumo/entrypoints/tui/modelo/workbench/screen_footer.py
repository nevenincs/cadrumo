"""Footer rendering and key bindings for the Modelo workbench."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from rich.cells import cell_len
from textual.widgets import Static

from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.i18n.render import tr
from ...components.dialogs import ConfirmScreen
from .casilla_list import CasillaList
from .header import ChipLevel, StatusLine, attention_chips, status_line
from .keys import describe_bindings
from .progress import WorkbenchProgress
from .screen_constants import (
    _CHANGE_KEYS,
    _CLOSE_LOCALE_KEY,
    _FINDINGS_KEY,
    _FOOTER_KEY_GAP,
    _FOOTER_PRIORITY,
    _LEGEND_KEYS,
    _LIST_LOCALE_KEYS,
    _NARROW,
    _NEXT_KEYS,
    _PALETTE_FRAME,
    _RECORDED_ENTER_LOCALE_KEY,
    _SCREEN_LOCALE_KEYS,
    _SHORT,
)
from .screen_widgets import SymbolsPanel

if TYPE_CHECKING:
    from .screen import ModeloWorkbenchScreen


class WorkbenchFooterMixin:
    """Own the footer behavior for the modelo workbench."""

    def action_leave(self: ModeloWorkbenchScreen) -> None:
        """Close the open panel, or leave for where the workbench was opened from, asking first about staged changes."""
        if self._legend_level:
            self._legend_level = 0
            self._show_legend_level()
            return
        if self.has_class("-searching"):
            self._close_search()
            return
        if self._docked is not None:
            self._close_dock()
            return
        self._leave_then(lambda: self.dismiss(None))

    def _leave_then(self: ModeloWorkbenchScreen, leave: Callable[[], object]) -> None:
        if not self._session.dirty:
            leave()
            return

        def closed(discard: bool | None) -> None:
            if discard:
                self._session.discard()
                leave()

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.modelo.workbench.leave.title"),
                message=tr("tui.modelo.workbench.leave.message", count=len(self._session.changes)),
                confirm_label=tr("tui.modelo.workbench.leave.discard"),
                cancel_label=tr("tui.modelo.workbench.leave.stay"),
            ),
            closed,
        )

    def _status_line(self: ModeloWorkbenchScreen) -> StatusLine | None:
        """The header's result line, for a dialog that covers the header to repeat at its top."""
        form = self.form
        if form is None:
            return None
        return status_line(form, self._language, staged=len(self._session.changes), recorded=self.recorded)

    def _notice(self: ModeloWorkbenchScreen, message: str) -> None:
        self.query_one("#wb-notice", Static).update(message)

    def _edit_unavailable(self: ModeloWorkbenchScreen) -> None:
        if self.recorded:
            self._notice(tr("tui.modelo.workbench.filed.read_only"))
            return
        refusal = self._reader.edit_refusal()
        self._notice(refusal or tr("tui.modelo.workbench.editability.no_admission"))

    def _refresh_after_staging(self: ModeloWorkbenchScreen) -> None:
        self._render_header()
        self._render_progress()
        self._render_navigator()
        self._render_page()

    def _apply_width(self: ModeloWorkbenchScreen, width: int) -> None:
        self.set_class(width < _NARROW, "-narrow")

    def _apply_height(self: ModeloWorkbenchScreen, height: int) -> None:
        """On a short terminal show more boxes: one line each, a one-line help band that ``?`` expands."""
        short = 0 < height < _SHORT
        self.set_class(short, "-short")
        if self._density_chosen is None:
            self.query_one(CasillaList).set_density("compact" if short else "comfortable")

    def _width(self: ModeloWorkbenchScreen) -> int:
        return self.size.width or self.app.size.width

    def _key_label(self: ModeloWorkbenchScreen, key: str, translation_key: str) -> str:
        own = self._bindings.key_to_bindings.get(key)
        binding = own[0] if own else self.query_one(CasillaList).binding_for(key)
        display = key if binding is None else self.app.get_key_display(binding)
        return f"{display} {tr(translation_key)}"

    def _footer_keys(self: ModeloWorkbenchScreen, width: int) -> frozenset[str]:
        """The keys the footer can show at ``width``, most needed first, without running under the palette key.

        A declaration recorded as filed shows no key that would change it or
        lead to something left to do.
        """
        descriptions = {**self._list_locale_keys(), **_SCREEN_LOCALE_KEYS}
        budget = self._footer_budget(width, descriptions)
        hidden = self._hidden_keys()
        pinned = self._pinned_keys()
        return self._footer_visible_keys(descriptions, hidden, pinned, budget)

    def _footer_budget(self: ModeloWorkbenchScreen, width: int, descriptions: Mapping[str, str]) -> int:
        others = [
            active.binding
            for key, active in self.active_bindings.items()
            if active.binding.show and key not in descriptions
        ]
        return (
            width
            - self._palette_cost()
            - sum(
                cell_len(f"{self.app.get_key_display(binding)} {binding.description}") + _FOOTER_KEY_GAP
                for binding in others
            )
        )

    @staticmethod
    def _footer_key_order(pinned: tuple[str, ...]) -> tuple[str, ...]:
        return (*pinned, *(key for key in _FOOTER_PRIORITY if key not in pinned))

    def _footer_visible_keys(
        self: ModeloWorkbenchScreen,
        descriptions: Mapping[str, str],
        hidden: frozenset[str],
        pinned: tuple[str, ...],
        budget: int,
    ) -> frozenset[str]:
        shown: set[str] = set()
        for key in self._footer_key_order(pinned):
            if key in hidden:
                continue
            include, stop, cost = self._footer_key_decision(key, budget, pinned, descriptions)
            if stop:
                break
            if include:
                shown.add(key)
                budget -= cost
        return frozenset(shown)

    def _footer_key_decision(
        self: ModeloWorkbenchScreen, key: str, budget: int, pinned: tuple[str, ...], descriptions: Mapping[str, str]
    ) -> tuple[bool, bool, int]:
        cost = cell_len(self._key_label(key, descriptions[key])) + _FOOTER_KEY_GAP
        if cost > budget:
            return False, key not in pinned, 0
        return True, False, cost

    def _pinned_keys(self: ModeloWorkbenchScreen) -> tuple[str, ...]:
        """Keep Help and the named next action; fieldless content then needs Scroll and Back.

        F8 and urgent Issues follow those essential directions when no field
        can be selected; scalar pages retain their existing priority.
        """
        load = self._load
        fieldless = self.query_one(CasillaList).highlighted is None
        if load is None or self.recorded:
            return ("question_mark", "up", "escape") if fieldless else ()
        return self._active_pinned_keys(self._progress(load), fieldless, load.form)

    def _active_pinned_keys(
        self: ModeloWorkbenchScreen, progress: WorkbenchProgress, fieldless: bool, form: ModeloWorkForm
    ) -> tuple[str, ...]:
        named = _FINDINGS_KEY if progress.findings_lead else _NEXT_KEYS[progress.next_action]
        pinned = ["question_mark"]
        if named:
            pinned.append(self._footer_progress_key(named))
        if fieldless:
            pinned.extend(("up", "escape"))
        pinned.append("f8")
        if any(chip.level in {ChipLevel.BLOCKS, ChipLevel.MISSING} for chip in attention_chips(form, recorded=False)):
            pinned.append(_FINDINGS_KEY)
        kept: list[str] = []
        for key in pinned:
            if key in _FOOTER_PRIORITY and key not in kept:
                kept.append(key)
        return tuple(kept)

    @staticmethod
    def _footer_progress_key(named: str) -> str:
        if named.startswith("F") and named[1:].isdigit():
            return named.lower()
        return named

    def _hidden_keys(self: ModeloWorkbenchScreen) -> frozenset[str]:
        """Hide field actions without a selected field; read-only content keeps its scroll cue."""
        hidden: set[str] = set(_CHANGE_KEYS) if self.recorded else set()
        if self.query_one(CasillaList).highlighted is None:
            hidden.update(("enter", "s"))
        else:
            hidden.add("up")
        return frozenset(hidden)

    def _list_locale_keys(self: ModeloWorkbenchScreen) -> Mapping[str, str]:
        """What the list's keys say: Enter opens a box to read once the declaration is recorded as filed."""
        if self.recorded:
            return {**_LIST_LOCALE_KEYS, "enter": _RECORDED_ENTER_LOCALE_KEY}
        return _LIST_LOCALE_KEYS

    def _palette_cost(self: ModeloWorkbenchScreen) -> int:
        """The cells the footer keeps at its right edge for the command palette key, when it shows one."""
        app = self.app
        if not app.ENABLE_COMMAND_PALETTE:
            return 0
        active = self.active_bindings.get(app.COMMAND_PALETTE_BINDING)
        if active is None:
            return 0
        binding = active.binding
        return cell_len(f"{app.get_key_display(binding)} {binding.description}") + _PALETTE_FRAME

    def _describe_keys(self: ModeloWorkbenchScreen) -> None:
        if self._legend_level == 2:
            # The symbols panel has its own keys: close it, and scroll it.
            describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS, shown=_LEGEND_KEYS)
            describe_bindings(self._bindings.key_to_bindings, {"escape": _CLOSE_LOCALE_KEY}, shown=_LEGEND_KEYS)
            self.query_one(SymbolsPanel).describe_keys()
            self.refresh_bindings()
            return
        shown = self._footer_keys(self._width())
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS, shown=shown)
        self.query_one(CasillaList).describe_keys(self._list_locale_keys(), shown=shown)
        self.refresh_bindings()
