"""The installation area: every sessionless act the runtime serves, listed by family.

The list is the runtime's own act table. The area holds no session and needs
none, so the same screen opens from the sign-in screen, from first
registration and from the workbench.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....adapters.local_runtime.installation_client import open_installed_installation_client
from ....application.runtime.installation_requests import InstallationAct
from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1
from .act_screen import InstallationActScreen
from .acts import OfferedAct, offered_acts
from .door import InstallationClientOpener
from .texts import act_label, act_summary, family_label, worded_in


class InstallationScreen(AccountChromeScreen):
    """List the installation acts and open the one the person chooses."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        #installation-page { width: 100%; height: 1fr; overflow-x: hidden; }
        #installation-intro, #installation-notice, #installation-hint, #installation-summary {
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-space-1;
        }
        #installation-summary { margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0; }
        #installation-notice { color: $warning; }
        #installation-acts { width: 100%; }
        """
    )

    def __init__(
        self,
        *,
        open_client: InstallationClientOpener = open_installed_installation_client,
        on_records_changed: Callable[[], None] | None = None,
        notice: str | None = None,
        locale: str | None = None,
    ) -> None:
        """Bind the door acts are sent through.

        Args:
            open_client: Opens the connection each act is sent on.
            on_records_changed: Called when an act may have changed the
                installation's records, the profile set among them.
            notice: A line shown above the list, for a host that opened the
                area because something else could not be done.
            locale: The language of the page that opened the area, when that
                page chose its own; ``None`` for the language already on screen.
        """
        super().__init__()
        self._open_client = open_client
        self._on_records_changed = on_records_changed
        self._notice = notice
        self._locale = locale
        self._offered: dict[str, OfferedAct] = {offered.act.value: offered for offered in offered_acts()}

    @property
    def offered_acts(self) -> tuple[InstallationAct, ...]:
        """The acts this area lists, in the order it lists them."""
        return tuple(offered.act for offered in self._offered.values())

    @override
    def compose(self) -> ComposeResult:
        with worded_in(self._locale):
            title = tr("tui.installation.title")
            intro = tr("tui.installation.intro")
            hint = tr("tui.installation.list_hint")
        yield Static(title, classes="cadrumo-banner", markup=False)
        with ContentScroll(id="installation-page", classes="cadrumo-scroll"):
            if self._notice:
                yield Static(self._notice, id="installation-notice", markup=False)
            yield Static(intro, id="installation-intro", classes="cadrumo-subtle", markup=False)
            yield ContentDataTable[str](id="installation-acts", cursor_type="row", zebra_stripes=True)
            yield Static(id="installation-summary", markup=False)
            yield Static(hint, id="installation-hint", classes="cadrumo-note", markup=False)

    def on_mount(self) -> None:
        """List every offered act with its family and whether it changes records."""
        table = cast("DataTable[str]", self.query_one("#installation-acts", DataTable))
        with worded_in(self._locale):
            table.add_column(tr("tui.installation.column.family"))
            table.add_column(tr("tui.installation.column.act"))
            table.add_column(tr("tui.installation.column.effect"))
            reads, changes = tr("tui.installation.effect.reads"), tr("tui.installation.effect.changes")
            for key, offered in self._offered.items():
                table.add_row(
                    family_label(offered.family),
                    act_label(offered.act),
                    reads if offered.reads_only else changes,
                    key=key,
                )
        table.focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Say what the act under the cursor does; a table cell would cut the sentence short."""
        if event.data_table.id != "installation-acts" or event.row_key.value is None:
            return
        with worded_in(self._locale):
            summary = act_summary(InstallationAct(event.row_key.value))
        self.query_one("#installation-summary", Static).update(summary)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the chosen act."""
        if event.data_table.id != "installation-acts" or event.row_key.value is None:
            return
        self.open_act(InstallationAct(event.row_key.value))

    def open_act(self, act: InstallationAct) -> None:
        """Show one act's form over this list."""
        self.app.push_screen(
            InstallationActScreen(
                self._offered[act.value],
                open_client=self._open_client,
                on_records_changed=self._on_records_changed,
                locale=self._locale,
            )
        )

    def action_close(self) -> None:
        """Return to whatever opened the area."""
        self.dismiss(None)


def installation_screen_factory(context: TuiScreenContextV1, /) -> Screen[None]:
    """Build the installation area for an admitted workbench route."""
    del context
    return InstallationScreen()


__all__ = ["InstallationScreen", "installation_screen_factory"]
