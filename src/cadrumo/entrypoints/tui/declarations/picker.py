"""Keyboard-first Modelo and supported-period selection."""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from ....application.modelo.declaration_targets import DeclarationTarget
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ..components.theme import tokenised
from ..modelo.workbench.wording import modelo_title, period_words


class NewDeclarationPicker(ModalScreen[DeclarationTarget | None]):
    """Select a Modelo, then one of its registry-backed filing periods."""

    BINDINGS: ClassVar = [Binding("escape", "back", show=False)]
    DEFAULT_CSS = tokenised("""
    NewDeclarationPicker { align: center middle; }
    #declaration-picker {
        width: 100%; height: $cadrumo-modal-height;
        border: $cadrumo-radius-overlay $accent; background: $surface;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
    }
    #declaration-picker-table { height: 1fr; }
    #declaration-picker-hint { height: auto; }
    #declaration-picker-buttons { height: auto; }
    """)

    def __init__(
        self,
        targets: tuple[DeclarationTarget, ...],
        applicable: frozenset[str],
        *,
        preferred: DeclarationTarget | None = None,
        confirmation: bool = False,
    ) -> None:
        """Keep an immutable choice set and an optional due address."""
        super().__init__()
        self.targets = targets
        self.applicable = applicable
        self.preferred = preferred
        self.show_all = False
        self.modelo: str | None = preferred.modelo if confirmation and preferred is not None else None
        self.selected: DeclarationTarget | None = preferred if confirmation else None
        self.confirmation = confirmation
        self.visible_targets: tuple[DeclarationTarget, ...] = ()

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="declaration-picker"):
            yield Static(id="declaration-picker-title", markup=False)
            yield Static(id="declaration-picker-hint", markup=False)
            yield DataTable(id="declaration-picker-table", cursor_type="row", zebra_stripes=True)
            yield Static(id="declaration-picker-selection", markup=False)
            with Horizontal(id="declaration-picker-buttons"):
                yield Button(tr("tui.declarations.list.new.show_all"), id="declaration-picker-all")
                yield Button(tr("tui.declarations.list.new.create"), id="declaration-picker-create", disabled=True)
                yield Button(tr("tui.modelo.workbench.editor.cancel"), id="declaration-picker-cancel")

    def on_mount(self) -> None:
        """Populate the first step, or an explicit start confirmation."""
        self._populate()

    def _populate(self) -> None:
        table = self.query_one("#declaration-picker-table", DataTable)
        table.clear(columns=True)
        language = OutputLanguage(output_language())
        title = (
            "tui.declarations.list.new.choose_modelo"
            if self.modelo is None
            else "tui.declarations.list.new.choose_period"
        )
        self.query_one("#declaration-picker-title", Static).update(tr(title))
        hint = self.query_one("#declaration-picker-hint", Static)
        hint.display = self.modelo is not None and self.selected is None and not self.confirmation
        hint.update(tr("tui.declarations.list.new.period_selection_hint") if hint.display else "")
        self.query_one("#declaration-picker-all", Button).display = self.modelo is None and not self.confirmation
        # The first step has no filing address to create. Keep its two actions
        # within a narrow terminal even when Show all has a long translation.
        self.query_one("#declaration-picker-create", Button).display = self.modelo is not None
        if self.modelo is None:
            table.add_column(tr("tui.declarations.list.column.declaration"))
            model_numbers = sorted(
                {target.modelo for target in self.targets if self.show_all or target.modelo in self.applicable}
            )
            for modelo in model_numbers:
                table.add_row(modelo_title(modelo, language), key=modelo)
            if self.preferred is not None and self.preferred.modelo in model_numbers:
                table.move_cursor(row=model_numbers.index(self.preferred.modelo))
        else:
            table.add_column(tr("tui.declarations.list.column.period"))
            self.visible_targets = tuple(target for target in self.targets if target.modelo == self.modelo)
            for index, target in enumerate(self.visible_targets):
                table.add_row(period_words(target.period), key=str(index))
            if self.preferred in self.visible_targets:
                table.move_cursor(row=self.visible_targets.index(self.preferred))
            if self.confirmation:
                table.display = False
                self.query_one("#declaration-picker-selection", Static).update(
                    tr(
                        "tui.declarations.list.new.start_confirm",
                        modelo=modelo_title(self.modelo, language),
                        period=period_words(self.preferred.period) if self.preferred is not None else "",
                    )
                )
                self.query_one("#declaration-picker-create", Button).disabled = False
                self.query_one("#declaration-picker-cancel", Button).focus()
                return
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Advance the Modelo step or select a period for explicit creation."""
        key = event.row_key.value
        if key is None:
            return
        if self.modelo is None:
            self.modelo = key
            self._populate()
        else:
            self.selected = self.visible_targets[int(key)]
            self.query_one("#declaration-picker-hint", Static).display = False
            self.query_one("#declaration-picker-selection", Static).update(period_words(self.selected.period))
            self.query_one("#declaration-picker-create", Button).disabled = False
            self.query_one("#declaration-picker-create", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Accept only an admitted selected target."""
        if event.button.id == "declaration-picker-cancel":
            self.dismiss(None)
        elif event.button.id == "declaration-picker-all":
            self.show_all = not self.show_all
            self._populate()
        elif event.button.id == "declaration-picker-create" and self.selected is not None:
            self.dismiss(self.selected)

    def action_back(self) -> None:
        """Return from period to Modelo selection, or cancel."""
        if self.modelo is None or self.confirmation:
            self.dismiss(None)
        else:
            self.modelo = None
            self.selected = None
            self.query_one("#declaration-picker-create", Button).disabled = True
            self.query_one("#declaration-picker-selection", Static).update("")
            self._populate()
