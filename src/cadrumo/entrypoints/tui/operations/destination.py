"""The Operations destination: every registered operation, listed, searched and run."""

from __future__ import annotations

import asyncio
from typing import ClassVar, Final, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.theme import BASE_CSS, tokenised
from ..navigation import TuiScreenContextV1
from .catalogue import OperationCatalogueSourceV1, OperationCatalogueV1
from .run_screen import OperationRunScreen

OPERATIONS_DESTINATION: Final = "workbench.operations"
OPERATION_FOCUS_KEY: Final = "operations.run"
"""The navigation focus that opens the destination on one named operation."""

_FAMILY_OPTION_PREFIX = "family:"


class OperationsCatalogueScreen(AccountChromeScreen):
    """List every registered operation under its family and open the one a person picks."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #operations-search { width: 100%; }
    #operations-status { height: auto; padding: $cadrumo-space-0 $cadrumo-space-1; }
    #operations-list { width: 100%; height: 1fr; }
    """)

    def __init__(
        self,
        client: RuntimeFrontendClient,
        source: OperationCatalogueSourceV1,
        *,
        focus_token: str | None = None,
    ) -> None:
        """Retain the admitted client, the catalogue door and the operation to open first."""
        super().__init__(id="operations-catalogue")
        self._client = client
        self._source = source
        self._focus_token = focus_token
        self._catalogue: OperationCatalogueV1 | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.operations.title"), classes="cadrumo-banner", markup=False)
        yield Input(placeholder=tr("tui.operations.search.placeholder"), id="operations-search")
        yield Static(tr("tui.operations.status.loading"), id="operations-status", markup=False)
        yield OptionList(id="operations-list", markup=False)

    def on_mount(self) -> None:
        """Compose the catalogue off the event loop; the registry is large."""
        self.run_worker(self._load(), group="operations-catalogue-load")

    async def _load(self) -> None:
        try:
            catalogue = await await_cancellation_complete(
                asyncio.to_thread(self._source.load), task_name="tui-operations-catalogue"
            )
        except Exception:  # a registry that cannot compose must not end the session
            self.query_one("#operations-status", Static).update(tr("tui.operations.status.unavailable"))
            return
        self._catalogue = catalogue
        self._show(self.query_one("#operations-search", Input).value)
        focus_token, self._focus_token = self._focus_token, None
        entry = None if focus_token is None else catalogue.entry_for_token(focus_token)
        if entry is not None:
            self.app.push_screen(OperationRunScreen(self._client, entry))

    def _show(self, query: str) -> None:
        catalogue = self._catalogue
        if catalogue is None:
            return
        listed = self.query_one("#operations-list", OptionList)
        listed.clear_options()
        shown = 0
        for family, entries in catalogue.grouped(query):
            listed.add_option(
                Option(f"{family} ({len(entries)})", id=f"{_FAMILY_OPTION_PREFIX}{family}", disabled=True)
            )
            for entry in entries:
                text = entry.definition_id if not entry.summary else f"{entry.definition_id}  {entry.summary}"
                listed.add_option(Option(f"  {text}", id=entry.definition_id))
            shown += len(entries)
        self.query_one("#operations-status", Static).update(
            tr("tui.operations.status.count", shown=shown, total=len(catalogue.entries))
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Narrow the list to the operations whose identity or description matches."""
        if event.input.id == "operations-search":
            self._show(event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Open the request form of the chosen operation."""
        catalogue = self._catalogue
        option_id = event.option.id
        if catalogue is None or option_id is None:
            return
        entry = catalogue.entry(option_id)
        if entry is not None:
            self.app.push_screen(OperationRunScreen(self._client, entry))

    def action_back(self) -> None:
        """Leave the destination."""
        self.dismiss(None)


class OperationsDestinationV1:
    """Open the Operations destination for one admitted session."""

    def __init__(self, client: RuntimeFrontendClient, source: OperationCatalogueSourceV1) -> None:
        """Retain the admitted client and the lazily composed catalogue."""
        self._client = client
        self._source = source

    @property
    def source(self) -> OperationCatalogueSourceV1:
        """Return the catalogue door every surface offering operations shares."""
        return self._source

    def __call__(self, context: TuiScreenContextV1, /) -> Screen[None]:
        """Build the destination, opened on the operation the navigation focus names when it names one."""
        if context.destination != OPERATIONS_DESTINATION:
            raise ValueError("the operations factory requires its exact destination")
        focus = context.focus
        focus_token = None if focus is None or focus.semantic_key != OPERATION_FOCUS_KEY else focus.restore_token
        return OperationsCatalogueScreen(self._client, self._source, focus_token=focus_token)


__all__ = [
    "OPERATIONS_DESTINATION",
    "OPERATION_FOCUS_KEY",
    "OperationsCatalogueScreen",
    "OperationsDestinationV1",
]
