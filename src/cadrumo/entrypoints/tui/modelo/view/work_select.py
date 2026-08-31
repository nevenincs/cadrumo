"""Read-only Textual work-unit picker preceding the canonical review.

This entrypoint projection accepts an already-resolved tuple of
:class:`~WorkUnit` records and lets the operator pick
one with the keyboard. It performs no repository read, no catalogue query,
and no lifecycle mutation: the CLI layer resolves the work-unit catalogue and
this screen only renders and selects from it, exactly as
``ModeloWorkReviewScreen`` renders an already-built ``ModeloWorkReview``
without consulting the application layer itself.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from .....core.i18n._render import tr
from .....domain.modelos.work_unit import WorkUnit
from ...components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised
from ...components.widgets import ContentDataTable, ContentScroll

_COLUMN_KEYS: tuple[str, ...] = ("modelo", "filing_year", "period", "name", "state")


def _row_values(unit: WorkUnit) -> tuple[str, ...]:
    """Render one work unit into the picker's stable text columns."""
    return (
        str(unit.modelo),
        str(unit.filing_year),
        unit.period.registry_token,
        unit.name,
        unit.state.value,
    )


class ModeloWorkSelectScreen(Screen[None]):
    """Keyboard-navigable picker over the resolved work-unit catalogue."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_select", ""),
        Binding("escape", "quit_select", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="modelo-select-header", classes="cadrumo-banner")
        with ContentScroll(id="modelo-select-body", classes="cadrumo-scroll"):
            yield ContentDataTable(id="modelo-select-table", cursor_type="row", zebra_stripes=True)
            yield Static(id="modelo-select-empty", classes="modelo-select-empty")

    def on_mount(self) -> None:
        """Populate the picker table from the already-resolved work units."""
        self.query_one("#modelo-select-header", Static).update(tr("flows.modelo_select.title"))
        table = self.query_one("#modelo-select-table", ContentDataTable)
        for column_key in _COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_select.column.{column_key}"), key=column_key)
        units = self.select_app.units
        for unit in units:
            table.add_row(*_row_values(unit), key=unit.work_unit_id)
        empty = self.query_one("#modelo-select-empty", Static)
        empty.display = not units
        if units:
            empty.update("")
            self.set_focus(table)
        else:
            empty.update(tr("flows.modelo_select.empty"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Exit the picker with the row the operator confirmed with Enter.

        ``DataTable`` owns the ``enter`` key itself (bound to
        ``select_cursor``, which raises this message) and never lets it bubble
        to a screen-level action binding, so the picker must react to the
        message rather than declare its own ``enter`` binding.
        """
        if event.row_key.value is not None:
            self.select_app.exit(event.row_key.value)

    def action_quit_select(self) -> None:
        """Exit the picker without choosing a work unit."""
        self.select_app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Toggle the shared presentation theme for the select host."""
        toggle_appearance(self.select_app)

    @property
    def select_app(self) -> ModeloWorkSelectApp:
        """Return the one owning application, refusing a foreign screen host."""
        return _require_select_app(self.app)


def _require_select_app(app: object) -> ModeloWorkSelectApp:
    """Narrow a screen host without leaving an unknown generic App type."""
    if not isinstance(app, ModeloWorkSelectApp):
        raise TypeError(
            f"{ModeloWorkSelectScreen.__name__} requires {ModeloWorkSelectApp.__name__}, got {type(app).__name__}",
        )
    return app


class ModeloWorkSelectApp(App[str | None]):
    """Standalone host for the canonical modelo work-unit picker.

    ``run()``/``run_async()`` returns the chosen ``work_unit_id`` (via
    ``exit(value)``), or ``None`` when the operator quits without choosing.
    """

    CSS = tokenised(
        BASE_CSS
        + """
    #modelo-select-body { width: 100%; height: 1fr; }
    #modelo-select-table { width: 100%; height: auto; background: $surface; }
    .modelo-select-empty { padding: $cadrumo-space-1 $cadrumo-gutter; }
    """
    )

    def __init__(self, units: tuple[WorkUnit, ...]) -> None:
        """Bind the one immutable work-unit tuple rendered by this host."""
        super().__init__()
        self.units = units

    def on_mount(self) -> None:
        """Install shared themes and open the canonical select screen."""
        install_cadrumo_themes(self)
        self.push_screen(ModeloWorkSelectScreen())


__all__ = ["ModeloWorkSelectApp", "ModeloWorkSelectScreen"]
